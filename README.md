# 🤖 AskDocs - Production-Grade Multi-Tenant RAG SaaS

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

**A complete production-ready RAG platform that enables businesses to upload documents and get AI-powered answers with verified citations, billing system, and comprehensive monitoring.**

[Demo](#demo--testing) • [Features](#key-features) • [Quick Start](#quick-start) • [API Docs](#api-documentation) • [Deploy](#production-deployment)

</div>

---

## 🎯 **What is AskDocs?**

AskDocs is a **production-grade, multi-tenant SaaS platform** where businesses can:
- 📄 Upload documents (PDF, DOCX, TXT, MD)
- 🤖 Get AI-powered answers with citations
- 🔍 Search across all documents with hybrid search
- 💬 Embed chat widgets on websites
- � Manage billing and subscriptions
- �📊 Monitor usage and performance with observability
- 🏢 Manage multiple tenants with strict data isolation

## ✨ **Key Features**

<table>
<tr>
<td width="33%">

### 🚀 **Smart RAG Pipeline**
- **Multi-format ingestion** (PDF, DOCX, MD, TXT)
- **Hybrid search** (Vector + BM25 + RRF)
- **Multi-provider LLM** (OpenAI + Anthropic)
- **Citation verification** with confidence scoring
- **Human handoff** detection

</td>
<td width="33%">

### 🏢 **Enterprise Ready**
- **Multi-tenant isolation** (strict data separation)
- **Role-based access** (Owner/Admin/Member)
- **API key management** with scopes
- **Billing & subscriptions** (Stripe integration)
- **Usage tracking** with plan enforcement

</td>
<td width="33%">

### 🔧 **Production Architecture**
- **Async FastAPI** backend
- **PostgreSQL + Redis** data layer
- **Qdrant** vector database
- **ARQ** background processing
- **Next.js** frontend dashboard


</td>
</tr>
</table>

## 🏗️ **System Architecture**

```mermaid
graph TB
    subgraph "🌐 Client Layer"
        W[💬 Chat Widget]
        D[📊 Dashboard UI]
        API[🔧 API Clients]
    end
    
    subgraph "🚪 API Gateway & Middleware"
        FASTAPI[⚡ FastAPI Server]
        AUTH[🔐 Authentication]
        TENANT[🏢 Multi-Tenant Context]
        RATE[⏰ Rate Limiting]
        BILLING[💳 Billing Enforcement]
    end
    
    subgraph "⚙️ Core Services"
        DOC[📄 Document Service]
        QUERY[🔍 Query Service]
        GEN[🤖 Generation Service]
        BILL[💰 Billing Service]
    end
    
    subgraph "🔄 Processing Pipeline"
        PARSE[📝 Document Parsers]
        CHUNK[✂️ Text Chunking]
        EMBED[🧠 Embeddings]
        QUEUE[📤 Job Queue]
    end
    
    subgraph "🔍 Search Engine"
        VECTOR[(🎯 Vector Store)]
        BM25[📊 BM25 Index]
        FUSION[⚡ RRF Fusion]
    end
    
    subgraph "💾 Data Layer"
        PG[(🐘 PostgreSQL)]
        REDIS[(🔴 Redis)]
    end
    
    subgraph "📊 Observability"
        PROM[📈 Prometheus]
        GRAF[📊 Grafana]
        ALERT[🚨 Alerting]
    end
    
    W --> FASTAPI
    D --> FASTAPI
    API --> FASTAPI
    
    FASTAPI --> AUTH --> TENANT --> RATE --> BILLING
    BILLING --> DOC & QUERY & GEN & BILL
    
    DOC --> QUEUE --> PARSE --> CHUNK --> EMBED
    EMBED --> VECTOR & BM25
    
    QUERY --> VECTOR & BM25
    VECTOR --> FUSION
    BM25 --> FUSION
    FUSION --> GEN
    
    DOC --> PG
    QUERY --> PG
    BILL --> PG
    QUEUE --> REDIS
    RATE --> REDIS
    
    FASTAPI --> PROM --> GRAF --> ALERT
```

## 🚀 **Quick Start**

### **Prerequisites**
- Docker and Docker Compose
- OpenAI API key
- (Optional) Stripe API keys for billing

### **1. Clone & Setup**
```bash
git clone https://github.com/yourusername/askdocs.git
cd askdocs

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys
```

### **2. Start Services**
```bash
# Start all services with Docker
docker compose up -d

# Wait for services to be ready (takes ~30 seconds)
docker compose logs -f
```

### **3. Initialize Database**
```bash
# Run database migrations
docker compose exec backend alembic upgrade head

# Initialize billing plans (optional)
docker compose exec backend python app/db/init_billing.py
```

### **4. Verify Setup**
```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check frontend
curl http://localhost:3000
```

**🎉 That's it!**
- **Backend API:** http://localhost:8000
- **Frontend Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs

## 📋 **Current Status & Modules**

<table>
<tr>
<td width="50%">

### ✅ **Completed Modules**

**🏗️ Module 1: Core Infrastructure**
- FastAPI with async SQLAlchemy
- PostgreSQL + Redis + Docker setup
- Structured logging & error handling
- Health checks & middleware

**🔐 Module 2: Authentication & Multi-Tenancy**
- JWT authentication system
- Multi-tenant data isolation
- Role-based access control (RBAC)
- API key management with scopes

**📄 Module 3: Document Ingestion**
- Multi-format parsers (PDF/DOCX/TXT/MD)
- Chunking strategies with overlap
- OpenAI embeddings integration
- Background processing with ARQ

**🔍 Module 4: Retrieval & Generation**
- Hybrid search (Vector + BM25)
- Reciprocal Rank Fusion (RRF)
- Multi-provider LLM integration
- Citation verification system

**💻 Module 5: Frontend Dashboard**
- Next.js 15 + TypeScript + Tailwind
- Document management interface
- Interactive chat with citations
- Analytics dashboard

**💬 Module 6: Chat Widget**
- Embeddable JavaScript widget
- Real-time streaming responses
- Custom branding per tenant
- Website integration examples

**💳 Module 7: Billing System**
- Stripe integration with webhooks
- Usage-based pricing models
- Plan limits enforcement
- Billing dashboard & customer portal

**📊 Module 8: Advanced Features & Observability**
- Prometheus metrics collection
- Health monitoring & alerting
- Advanced caching system
- Performance optimization

</td>
<td width="50%">

### 🚀 **Production Ready Features**

**🔒 Security & Compliance**
- Multi-tenant data isolation
- JWT + API key authentication
- Rate limiting & DDoS protection
- Input validation & sanitization
- CORS configuration

**💰 Billing & Monetization**
- Stripe payment processing
- Subscription management
- Usage tracking & limits
- Plan enforcement middleware
- Cost calculation engine

**� Monitoring & Observability**
- Prometheus metrics collection
- Grafana dashboards
- Health check endpoints
- Performance monitoring
- Error tracking with Sentry

**🚀 Scalability & Performance**
- Redis caching system
- Background job processing
- Database connection pooling
- CDN-ready static assets
- Horizontal scaling support

**🔧 DevOps & Deployment**
- Docker containerization
- Production Docker compose
- Automated deployment scripts
- Database migrations
- Environment configuration

</td>
</tr>
</table>

## 🧪 **Demo & Testing**

### **Try the System**

```bash
# Register tenant
curl -X POST "http://localhost:8000/api/v1/tenants/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "owner_email": "owner@company.com",
    "owner_password": "secure123",
    "owner_full_name": "Owner Name"
  }'

# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "owner@company.com", "password": "secure123"}'

# Upload document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@your_document.pdf"

# Ask question
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key points in the document?"}'

# Check billing status
curl -X GET "http://localhost:8000/api/v1/billing/subscription" \
  -H "Authorization: Bearer <token>"
```

### **Run Comprehensive Demos**

```bash
cd askdocs/backend

# Run all system demos
python demo_complete.py

# Run billing system demo
python demo_billing.py

# Run specific tests
make test                  # All tests
make test-auth            # Authentication tests
make test-billing         # Billing system tests
make test-isolation       # Multi-tenant security tests
```

## 🛠️ **Tech Stack**

<table>
<tr>
<td width="50%">

### **Backend**
- **Framework:** FastAPI (async)
- **Language:** Python 3.11+
- **Database:** PostgreSQL + SQLAlchemy
- **Cache:** Redis + ARQ jobs
- **Vector DB:** Qdrant
- **Search:** BM25 + OpenAI embeddings
- **LLM:** OpenAI GPT-4o + Claude
- **Auth:** JWT + API keys
- **Billing:** Stripe API
- **Monitoring:** Prometheus + Grafana

</td>
<td width="50%">

### **Frontend**
- **Framework:** Next.js 15 + App Router
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **UI:** Headless UI + Heroicons
- **State:** Zustand
- **Forms:** React Hook Form
- **HTTP:** Axios with interceptors
- **Notifications:** React Hot Toast
- **Charts:** Recharts

</td>
</tr>
</table>

## 🔒 **Security Features**

- ✅ **Multi-tenant data isolation** - Strict separation at DB level
- ✅ **Role-based access control** - Owner/Admin/Member permissions  
- ✅ **JWT authentication** - Secure token-based auth
- ✅ **API key management** - Scoped keys with expiration
- ✅ **Rate limiting** - Per-tenant request limits
- ✅ **Input validation** - Pydantic models with sanitization
- ✅ **SQL injection prevention** - SQLAlchemy ORM protection
- ✅ **CORS configuration** - Secure cross-origin requests
- ✅ **Billing security** - Stripe webhook verification

## 💳 **Billing & Pricing**

<table>
<tr>
<td width="25%">

### **Free Plan**
- 10 documents
- 50 queries/month
- 100MB storage
- 1 API key
- 1 team member

</td>
<td width="25%">

### **Starter Plan**
*$29/month*
- 100 documents
- 1,000 queries/month
- 1GB storage
- 5 API keys
- 3 team members

</td>
<td width="25%">

### **Professional**
*$99/month*
- 1,000 documents
- 10,000 queries/month
- 10GB storage
- 20 API keys
- 10 team members

</td>
<td width="25%">

### **Enterprise**
*$299/month*
- Unlimited documents
- 100,000 queries/month
- 100GB storage
- Unlimited API keys
- 50 team members

</td>
</tr>
</table>

## 📚 **API Documentation**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tenants/` | POST | Register new tenant |
| `/api/v1/auth/login` | POST | User login |
| `/api/v1/documents/upload` | POST | Upload documents |
| `/api/v1/query/` | POST | Ask questions |
| `/api/v1/billing/subscription` | GET | Get billing info |
| `/api/v1/billing/checkout` | POST | Create checkout session |
| `/api/v1/monitoring/health` | GET | System health |
| `/api/v1/monitoring/metrics` | GET | Prometheus metrics |

**📖 Full API docs:** http://localhost:8000/docs

## 🚀 **Production Deployment**

### **Automated Deployment**

```bash
# Copy production environment
cp .env.prod.example .env.prod
# Edit .env.prod with your production values

# Deploy with automated script
./deploy.sh deploy
```

### **Manual Deployment**

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# Initialize database
docker-compose -f docker-compose.prod.yml exec backend python app/db/init_billing.py

# Check health
./deploy.sh health
```

### **Railway (Cloud Deployment)**
```bash
railway login
railway project create askdocs
railway add postgresql redis
railway deploy
```

### **Environment Variables**

Key production environment variables:

```bash
# Domain & URLs
DOMAIN=yourdomain.com
FRONTEND_URL=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com

# Database & Cache
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0

# Authentication
JWT_SECRET=your_very_secure_jwt_secret

# OpenAI
OPENAI_API_KEY=sk-your_openai_api_key

# Stripe Billing
STRIPE_SECRET_KEY=sk_live_your_stripe_secret
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable

# SSL/TLS
ACME_EMAIL=your_email@yourdomain.com
```

## 📊 **Monitoring & Observability**

- **Health Checks:** `/api/v1/monitoring/health`
- **Metrics:** Prometheus format at `/api/v1/monitoring/metrics/prometheus`
- **Dashboards:** Grafana at `https://grafana.yourdomain.com`
- **Alerts:** System alerts via email/Slack
- **Logs:** Structured logging with correlation IDs

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run tests: `make test`
5. Submit pull request

## 📝 **License**

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 **Support**

- 🐛 **Issues:** [GitHub Issues](https://github.com/tusharpawar1217/LLM-RAG-Project/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/tusharpawar1217/LLM-RAG-Project/discussions)
- 📧 **Email:** support@askdocs.com

---

<div align="center">

**⭐ Star this repository if you find it useful!**

Built with ❤️ for the AI community

</div>
