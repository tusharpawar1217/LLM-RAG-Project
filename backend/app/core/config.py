"""
Application configuration using pydantic-settings.
All config is loaded from environment variables with validation.
"""

from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AskDocs"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_VERSION: str = "v1"
    SECRET_KEY: str = Field(..., min_length=32)

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is valid."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 50

    # Qdrant
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_PREFIX: str = "askdocs_tenant_"

    # OpenAI
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    OPENAI_EMBEDDING_BATCH_SIZE: int = 100

    # LLM Configuration
    PRIMARY_LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    PRIMARY_LLM_MODEL: str = "gpt-4o-mini"
    FALLBACK_LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    FALLBACK_LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 60

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Retrieval
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 200
    CHUNKING_STRATEGY: Literal["recursive", "markdown"] = "recursive"
    TOP_K_DENSE: int = 10
    TOP_K_SPARSE: int = 10
    TOP_K_FINAL: int = 5
    RRF_K: int = 60
    ENABLE_RERANKER: bool = False
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    # Citation Verification
    CITATION_CONFIDENCE_THRESHOLD: float = 0.7
    VERIFICATION_USE_LLM_JUDGE: bool = True

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"]
    )
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # API Keys
    API_KEY_PREFIX: str = "ask_"
    API_KEY_LENGTH: int = 32

    # Billing
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_STARTER: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_ENTERPRISE: str = ""

    # Razorpay (alternative)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # Plans & Limits
    TRIAL_DURATION_DAYS: int = 14
    STARTER_MAX_DOCUMENTS: int = 50
    STARTER_MAX_MESSAGES: int = 1000
    PRO_MAX_DOCUMENTS: int = 500
    PRO_MAX_MESSAGES: int = 10000
    ENTERPRISE_MAX_DOCUMENTS: int = 10000
    ENTERPRISE_MAX_MESSAGES: int = 100000

    # Worker
    ARQ_WORKER_CONCURRENCY: int = 10
    ARQ_MAX_JOBS: int = 100
    UPLOAD_DIR: str = "/tmp/askdocs/uploads"

    # Observability
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@askdocs.ai"

    # Widget
    WIDGET_CDN_URL: str = "http://localhost:8000/static/widget"
    WIDGET_DEFAULT_PRIMARY_COLOR: str = "#3b82f6"
    WIDGET_DEFAULT_BOT_NAME: str = "Support Bot"

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.APP_ENV == "development"

    def get_plan_limits(self, tier: str) -> dict[str, int]:
        """Get limits for a subscription tier."""
        limits = {
            "starter": {
                "max_documents": self.STARTER_MAX_DOCUMENTS,
                "max_messages": self.STARTER_MAX_MESSAGES,
            },
            "pro": {
                "max_documents": self.PRO_MAX_DOCUMENTS,
                "max_messages": self.PRO_MAX_MESSAGES,
            },
            "enterprise": {
                "max_documents": self.ENTERPRISE_MAX_DOCUMENTS,
                "max_messages": self.ENTERPRISE_MAX_MESSAGES,
            },
        }
        return limits.get(tier, limits["starter"])


# Global settings instance
settings = Settings()


