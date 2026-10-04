"""
User service for managing user operations within tenants.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthorizationError, ResourceAlreadyExistsError, ResourceNotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import Tenant, User
from app.schemas.user import UserCreate, UserUpdate

logger = get_logger(__name__)


class UserService:
    """Service for user management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, tenant: Tenant, user_data: UserCreate, created_by: User) -> User:
        """
        Create a new user within a tenant.
        
        Args:
            tenant: Tenant to create user in
            user_data: User creation data
            created_by: User creating this user (for authorization)
            
        Returns:
            Created user
            
        Raises:
            AuthorizationError: If creator lacks permission
            ResourceAlreadyExistsError: If email already exists in tenant
        """
        # Check if creator has permission to add users
        if created_by.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to create users")
        
        # Check if email already exists in tenant
        existing_user = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == user_data.email,
            )
        )
        if existing_user.scalar_one_or_none():
            raise ResourceAlreadyExistsError("User", user_data.email)
        
        # Validate role assignment
        if user_data.role == "owner" and created_by.role != "owner":
            raise AuthorizationError("Only owners can create other owners")
        
        # Create user
        user = User(
            tenant_id=tenant.id,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(
            "User created",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            email=user_data.email,
            role=user_data.role,
            created_by=str(created_by.id),
        )
        
        return user
    
    async def get_user_by_id(self, tenant: Tenant, user_id: UUID) -> User:
        """
        Get user by ID within tenant (enforces tenant isolation).
        
        Args:
            tenant: Tenant context
            user_id: User ID
            
        Returns:
            User
            
        Raises:
            ResourceNotFoundError: If user not found in tenant
        """
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant.id,  # Enforce tenant isolation
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ResourceNotFoundError("User", str(user_id))
        
        return user
    
    async def get_user_by_email(self, tenant: Tenant, email: str) -> User:
        """
        Get user by email within tenant.
        
        Args:
            tenant: Tenant context
            email: User email
            
        Returns:
            User
            
        Raises:
            ResourceNotFoundError: If user not found in tenant
        """
        stmt = select(User).where(
            User.email == email,
            User.tenant_id == tenant.id,  # Enforce tenant isolation
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ResourceNotFoundError("User", email)
        
        return user
    
    async def update_user(
        self, 
        user: User, 
        update_data: UserUpdate, 
        updated_by: User
    ) -> User:
        """
        Update user information.
        
        Args:
            user: User to update
            update_data: Update data
            updated_by: User performing the update
            
        Returns:
            Updated user
            
        Raises:
            AuthorizationError: If updater lacks permission
        """
        # Check permissions
        if updated_by.id != user.id:  # Not updating self
            if updated_by.role not in ("owner", "admin"):
                raise AuthorizationError("Insufficient permissions to update users")
            
            # Role changes require specific permissions
            if update_data.role and update_data.role != user.role:
                if update_data.role == "owner" and updated_by.role != "owner":
                    raise AuthorizationError("Only owners can promote to owner role")
                if user.role == "owner" and updated_by.role != "owner":
                    raise AuthorizationError("Only owners can demote other owners")
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(
            "User updated",
            user_id=str(user.id),
            updated_by=str(updated_by.id),
            changes=list(update_dict.keys()),
        )
        
        return user
    
    async def deactivate_user(self, user: User, deactivated_by: User) -> User:
        """
        Deactivate a user.
        
        Args:
            user: User to deactivate
            deactivated_by: User performing the deactivation
            
        Returns:
            Updated user
            
        Raises:
            AuthorizationError: If deactivator lacks permission
        """
        # Check permissions
        if deactivated_by.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to deactivate users")
        
        if user.role == "owner" and deactivated_by.role != "owner":
            raise AuthorizationError("Only owners can deactivate other owners")
        
        # Prevent self-deactivation of the last owner
        if user.role == "owner" and deactivated_by.id == user.id:
            # Count other active owners
            other_owners = await self.db.execute(
                select(User).where(
                    User.tenant_id == user.tenant_id,
                    User.role == "owner",
                    User.is_active == True,
                    User.id != user.id,
                )
            )
            if not other_owners.scalars().first():
                raise AuthorizationError("Cannot deactivate the last owner")
        
        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(
            "User deactivated",
            user_id=str(user.id),
            deactivated_by=str(deactivated_by.id),
        )
        
        return user
    
    async def list_tenant_users(
        self, 
        tenant: Tenant, 
        requesting_user: User,
        include_inactive: bool = False
    ) -> list[User]:
        """
        List all users in a tenant.
        
        Args:
            tenant: Tenant
            requesting_user: User making the request
            include_inactive: Whether to include inactive users
            
        Returns:
            List of users
            
        Raises:
            AuthorizationError: If user lacks permission
        """
        # Check permissions
        if requesting_user.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to list users")
        
        # Build query
        conditions = [User.tenant_id == tenant.id]
        if not include_inactive:
            conditions.append(User.is_active == True)
        
        stmt = select(User).where(*conditions).order_by(User.created_at)
        result = await self.db.execute(stmt)
        
        return list(result.scalars().all())

