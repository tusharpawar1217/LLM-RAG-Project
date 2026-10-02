#!/bin/bash

# AskDocs Production Deployment Script
# This script handles the complete deployment process for the AskDocs platform

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="askdocs"
BACKUP_DIR="./backups"
LOG_FILE="./deploy.log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}" | tee -a "$LOG_FILE"
}

check_requirements() {
    log "Checking deployment requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if environment file exists
    if [[ ! -f .env.prod ]]; then
        log_error "Production environment file (.env.prod) not found."
        log "Please copy .env.prod.example to .env.prod and configure it."
        exit 1
    fi
    
    log_success "Requirements check passed"
}

backup_database() {
    log "Creating database backup..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Generate backup filename with timestamp
    BACKUP_FILE="$BACKUP_DIR/askdocs_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    # Check if PostgreSQL container is running
    if docker-compose -f docker-compose.prod.yml ps postgres | grep -q "Up"; then
        # Create database backup
        docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U askdocs_user askdocs_prod > "$BACKUP_FILE"
        
        if [[ -f "$BACKUP_FILE" && -s "$BACKUP_FILE" ]]; then
            log_success "Database backup created: $BACKUP_FILE"
        else
            log_warning "Database backup may have failed or is empty"
        fi
    else
        log_warning "PostgreSQL container not running, skipping backup"
    fi
}

build_images() {
    log "Building production Docker images..."
    
    # Load environment variables
    source .env.prod
    
    # Build backend image
    log "Building backend image..."
    docker-compose -f docker-compose.prod.yml build backend
    
    # Build worker image
    log "Building worker image..."
    docker-compose -f docker-compose.prod.yml build worker
    
    # Build frontend image
    log "Building frontend image..."
    docker-compose -f docker-compose.prod.yml build frontend
    
    log_success "All images built successfully"
}

deploy_infrastructure() {
    log "Deploying infrastructure services..."
    
    # Start infrastructure services (databases, cache, etc.)
    docker-compose -f docker-compose.prod.yml up -d postgres redis qdrant traefik
    
    # Wait for services to be ready
    log "Waiting for infrastructure services to be ready..."
    
    # Wait for PostgreSQL
    until docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U askdocs_user -d askdocs_prod; do
        log "Waiting for PostgreSQL..."
        sleep 2
    done
    
    # Wait for Redis
    until docker-compose -f docker-compose.prod.yml exec redis redis-cli ping; do
        log "Waiting for Redis..."
        sleep 2
    done
    
    # Wait for Qdrant
    until curl -f http://localhost:6333/health &>/dev/null; do
        log "Waiting for Qdrant..."
        sleep 2
    done
    
    log_success "Infrastructure services are ready"
}

run_migrations() {
    log "Running database migrations..."
    
    # Run Alembic migrations
    docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
    
    # Initialize billing plans
    docker-compose -f docker-compose.prod.yml run --rm backend python app/db/init_billing.py
    
    log_success "Database migrations completed"
}

deploy_application() {
    log "Deploying application services..."
    
    # Start application services
    docker-compose -f docker-compose.prod.yml up -d backend worker frontend
    
    # Wait for services to be healthy
    log "Waiting for application services to be healthy..."
    
    # Wait for backend
    until curl -f http://localhost:8000/api/v1/health &>/dev/null; do
        log "Waiting for backend service..."
        sleep 5
    done
    
    # Wait for frontend
    until curl -f http://localhost:3000 &>/dev/null; do
        log "Waiting for frontend service..."
        sleep 5
    done
    
    log_success "Application services deployed successfully"
}

deploy_monitoring() {
    log "Deploying monitoring services..."
    
    # Start monitoring services
    docker-compose -f docker-compose.prod.yml up -d prometheus grafana loki promtail
    
    log_success "Monitoring services deployed"
}

run_health_checks() {
    log "Running comprehensive health checks..."
    
    # Test API endpoints
    if curl -f http://localhost:8000/api/v1/health &>/dev/null; then
        log_success "Backend API health check passed"
    else
        log_error "Backend API health check failed"
        return 1
    fi
    
    # Test frontend
    if curl -f http://localhost:3000 &>/dev/null; then
        log_success "Frontend health check passed"
    else
        log_error "Frontend health check failed"
        return 1
    fi
    
    # Test database connectivity
    if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U askdocs_user -d askdocs_prod &>/dev/null; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
        return 1
    fi
    
    # Test Redis connectivity
    if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping &>/dev/null; then
        log_success "Redis connectivity check passed"
    else
        log_error "Redis connectivity check failed"
        return 1
    fi
    
    # Test Qdrant connectivity
    if curl -f http://localhost:6333/health &>/dev/null; then
        log_success "Qdrant connectivity check passed"
    else
        log_error "Qdrant connectivity check failed"
        return 1
    fi
    
    log_success "All health checks passed"
}

cleanup_old_images() {
    log "Cleaning up old Docker images..."
    
    # Remove dangling images
    docker image prune -f
    
    # Remove unused images (older than 7 days)
    docker image ls --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}" | \
        grep "$PROJECT_NAME" | \
        awk '$4 ~ /week|month/ {print $3}' | \
        xargs -r docker image rm -f
    
    log_success "Docker cleanup completed"
}

show_deployment_info() {
    log_success "🚀 AskDocs deployment completed successfully!"
    echo ""
    echo "📊 Service URLs:"
    echo "  • Frontend:    https://$DOMAIN"
    echo "  • API:         https://api.$DOMAIN"
    echo "  • Grafana:     https://grafana.$DOMAIN"
    echo "  • Prometheus:  https://prometheus.$DOMAIN"
    echo "  • Traefik:     https://traefik.$DOMAIN"
    echo ""
    echo "🐳 Container Status:"
    docker-compose -f docker-compose.prod.yml ps
    echo ""
    echo "📝 Next Steps:"
    echo "  1. Configure DNS records to point to this server"
    echo "  2. Set up Stripe webhooks in your Stripe dashboard"
    echo "  3. Configure monitoring alerts in Grafana"
    echo "  4. Test the complete user flow"
    echo "  5. Set up automated backups"
    echo ""
    echo "📚 Documentation: Check README.md for detailed configuration"
}

rollback() {
    log_warning "Rolling back deployment..."
    
    # Stop new services
    docker-compose -f docker-compose.prod.yml down
    
    # Restore database if backup exists
    LATEST_BACKUP=$(ls -t $BACKUP_DIR/*.sql 2>/dev/null | head -n1)
    if [[ -n "$LATEST_BACKUP" ]]; then
        log "Restoring database from $LATEST_BACKUP"
        docker-compose -f docker-compose.prod.yml up -d postgres
        sleep 10
        docker-compose -f docker-compose.prod.yml exec -T postgres psql -U askdocs_user -d askdocs_prod < "$LATEST_BACKUP"
    fi
    
    log_warning "Rollback completed"
}

# Main deployment function
main() {
    log "🚀 Starting AskDocs production deployment..."
    
    # Handle script arguments
    case "${1:-deploy}" in
        "deploy")
            check_requirements
            backup_database
            build_images
            deploy_infrastructure
            run_migrations
            deploy_application
            deploy_monitoring
            run_health_checks
            cleanup_old_images
            show_deployment_info
            ;;
        "rollback")
            rollback
            ;;
        "backup")
            backup_database
            ;;
        "health")
            run_health_checks
            ;;
        "logs")
            docker-compose -f docker-compose.prod.yml logs -f "${2:-}"
            ;;
        "status")
            docker-compose -f docker-compose.prod.yml ps
            ;;
        "update")
            log "Updating services..."
            docker-compose -f docker-compose.prod.yml pull
            docker-compose -f docker-compose.prod.yml up -d
            run_health_checks
            ;;
        *)
            echo "Usage: $0 {deploy|rollback|backup|health|logs|status|update}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Full production deployment (default)"
            echo "  rollback - Rollback to previous version"
            echo "  backup   - Create database backup"
            echo "  health   - Run health checks"
            echo "  logs     - View service logs"
            echo "  status   - Show service status"
            echo "  update   - Update services to latest images"
            exit 1
            ;;
    esac
}

# Trap errors and run rollback
trap 'log_error "Deployment failed! Check $LOG_FILE for details."; rollback' ERR

# Run main function
main "$@"