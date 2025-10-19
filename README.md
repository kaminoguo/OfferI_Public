# OfferI - AI-Powered Study Abroad Platform

> 🎓 Intelligent study abroad consultation powered by AI and MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue.svg)](https://modelcontextprotocol.io)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)](https://fastapi.tiangolo.com/)

## 📖 Overview

**OfferI** is a comprehensive AI-powered platform that helps students find their perfect study abroad program. It combines a modern web application with MCP (Model Context Protocol) integration to provide personalized recommendations from a database of 93,716+ Master's programs worldwide.

### 🌟 Key Features

- **💳 Simple Pricing**: Pay-per-use model ($6 per consultation)
- **🤖 AI-Powered**: Leverages Claude/GPT for intelligent matching
- **📊 Comprehensive Database**: 93,716 Master's programs globally
- **🔒 Secure Payments**: Stripe integration with webhook verification
- **🎯 Personalized Reports**: Custom PDF reports based on student profile
- **🌐 Modern Stack**: Next.js 15 + FastAPI + PostgreSQL + Redis
- **🔧 MCP Integration**: Direct access for AI assistants

## 🏗️ Architecture

```
┌─────────────────┐
│   Next.js 15    │  Frontend (React, TypeScript, Clerk Auth)
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│    FastAPI      │  Backend (Python, async)
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼──┐  ┌───▼────┐ ┌──▼──┐
│ Stripe│ │Redis│  │Postgres│ │ MCP │
│Payment│ │Queue│  │Database│ │ DB  │
└───────┘ └─────┘  └────────┘ └─────┘
```

## 🚀 Tech Stack

### Frontend
- **Framework**: Next.js 15.5.6 with App Router
- **Language**: TypeScript
- **UI**: React 19, Tailwind CSS
- **Auth**: Clerk (social login + email)
- **Payments**: Stripe Checkout
- **State**: React Hooks

### Backend
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.11+
- **Database**: PostgreSQL (payments), SQLite (programs)
- **Queue**: Redis
- **ORM**: SQLAlchemy
- **PDF**: WeasyPrint
- **Logging**: Loguru

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (production)
- **Deployment**: DigitalOcean / AWS
- **MCP**: FastMCP for AI integration

## 📂 Project Structure

```
OfferI/
├── frontend/                 # Next.js application
│   ├── app/                 # App router pages
│   ├── components/          # React components
│   │   ├── Chat.tsx        # Main consultation interface
│   │   ├── PaymentModal.tsx # Stripe checkout
│   │   └── FormModal.tsx   # User background form
│   ├── lib/                # Utilities & API client
│   └── package.json
│
├── backend/                 # FastAPI application
│   ├── api/
│   │   ├── server.py       # Main FastAPI app
│   │   ├── routes/
│   │   │   └── payment.py  # Stripe payment routes
│   │   └── models.py       # Pydantic models
│   ├── database.py         # SQLAlchemy models
│   ├── workers/            # Background job processing
│   ├── utils/              # Helper functions
│   ├── templates/          # Report templates
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── packages/mcp/           # MCP server for AI
    ├── server_http.py      # MCP HTTP/SSE server
    └── requirements.txt
```

## 🔧 Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional but recommended)

### Environment Variables

Create `.env` files for both frontend and backend:

**Frontend (`.env.local`):**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000

# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx
```

**Backend (`.env`):**
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/offeri

# Stripe
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Frontend URL
FRONTEND_URL=http://localhost:3000

# Redis
REDIS_URL=redis://localhost:6379
```

### Local Development

**Option 1: Docker (Recommended)**
```bash
# Start all services
cd backend
docker-compose up -d

# Start frontend
cd frontend
npm install
npm run dev

# Visit http://localhost:3000
```

**Option 2: Manual Setup**
```bash
# Terminal 1: Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev

# Terminal 3: MCP Server (optional)
cd packages/mcp
pip install -r requirements.txt
python server_http.py --transport sse --port 8081
```

## 💡 Features Walkthrough

### 1. User Flow

```
1. User visits website
2. Clicks "Start Consultation ($6)"
3. Redirected to Stripe Checkout
4. After payment, returns with payment_id
5. Fills out background form
6. AI processes and generates report (10-15 min)
7. Downloads personalized PDF report
```

### 2. Payment System

- **Model**: Pay-per-use ($6 per consultation)
- **Processing**: Stripe Checkout with webhooks
- **Database**: PostgreSQL tracks payment status
- **Retry Logic**: Failed reports allow free retry

### 3. Report Generation

- **Input**: User background (unstructured text)
- **Processing**: Claude analyzes + queries MCP database
- **Output**: Professional PDF with 30 program recommendations
- **Sections**:
  - Top tier programs (reach)
  - Matched programs (target)
  - Safety programs (backup)
  - Detailed analysis for each

### 4. MCP Integration

The MCP server provides:
- `search_programs()` - Filter by country/university/budget
- `get_program_details()` - Full program information
- `get_statistics()` - Database overview
- 93,716 programs across 150+ countries

## 🔐 Security

- ✅ All API keys in environment variables
- ✅ Clerk authentication with secure sessions
- ✅ Stripe webhook signature verification
- ✅ HTTPS in production
- ✅ CORS configured for specific origins
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ Input validation (Pydantic models)

## 📊 Database Schema

### Payment Table
```sql
CREATE TABLE payments (
    id VARCHAR PRIMARY KEY,              -- Stripe session ID
    user_id VARCHAR NOT NULL,            -- Clerk user ID
    amount FLOAT DEFAULT 6.00,
    status VARCHAR,                      -- paid/delivered/pending_retry/refunded
    job_id VARCHAR,                      -- Background job ID
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Programs Database (SQLite)
- 93,716 Master's programs
- 13 structured fields per program
- Optimized for MCP queries

## 🚢 Deployment

### Using Docker Compose

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# Includes:
# - FastAPI backend
# - PostgreSQL database
# - Redis queue
# - Nginx reverse proxy
```

### Manual Deployment

1. Set up PostgreSQL and Redis
2. Configure environment variables
3. Build frontend: `npm run build`
4. Run backend: `uvicorn api.server:app --host 0.0.0.0`
5. Serve frontend: `npm start`
6. Configure Nginx reverse proxy

## 🤝 Contributing

This is a showcase/portfolio project. The code demonstrates:
- Modern full-stack architecture
- Payment integration best practices
- AI/LLM integration patterns
- Clean code structure
- Production-ready deployment

Feel free to fork and adapt for your own projects!

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

## 📞 Contact

- **Author**: [@kaminoguo](https://github.com/kaminoguo)
- **Email**: Lyrica2333@gmail.com
- **MCP Server**: [github.com/kaminoguo/OfferI_MCP](https://github.com/kaminoguo/OfferI_MCP)

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Frontend powered by [Next.js](https://nextjs.org/)
- Auth by [Clerk](https://clerk.com/)
- Payments via [Stripe](https://stripe.com/)
- MCP protocol by [Anthropic](https://modelcontextprotocol.io)

---

**⚠️ Note**: This repository excludes crawler implementation and database files for security. The MCP server and API demonstrate the architecture and code quality.

**Built with ❤️ for international students**
