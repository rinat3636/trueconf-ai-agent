# TrueConf AI Agent

Corporate AI agent for TrueConf with knowledge base, sales analytics, and admin-controlled training.

## Features

- **Knowledge Base**: Upload PDF, DOCX, XLSX, CSV, TXT documents. AI extracts and indexes knowledge automatically.
- **AI Chat**: Employees ask questions, AI answers from the knowledge base only.
- **Sales Analytics**: Upload sales reports (XLS/XLSX/CSV), get automated analysis of managers, clients, products.
- **AI Training**: Admin corrects AI answers, sets corporate rules, moderates new knowledge.
- **Admin Panel**: Web interface for managing knowledge, training, moderation, analytics, monitoring.
- **TrueConf Integration**: Bot stub ready for connection (requires TrueConf Server API credentials).

## Architecture

```
backend/          Python FastAPI backend
  app/
    api/          REST API endpoints
    core/         Config, DB, security
    models/       SQLAlchemy models
    schemas/      Pydantic schemas
    services/     Business logic (LLM, knowledge, analytics)
frontend/         React admin panel (Vite)
  src/
    components/   Shared components
    pages/        Page views
    services/     API client
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- AI Tunnel API key (https://aitunnel.ru)

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env and set AITUNNEL_API_KEY

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### Default Login

- Username: `admin`
- Password: `admin123`

## Docker

```bash
cp backend/.env.example backend/.env
# Edit backend/.env

docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

## API Endpoints

### Auth
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Register user
- `GET /api/auth/me` - Current user
- `GET /api/auth/users` - List users (admin)

### Chat
- `POST /api/chat/ask` - Ask AI a question
- `POST /api/chat/feedback` - Submit feedback
- `GET /api/chat/history` - Chat history

### Knowledge
- `POST /api/knowledge/documents/upload` - Upload document
- `GET /api/knowledge/documents` - List documents
- `DELETE /api/knowledge/documents/{id}` - Delete document
- `GET /api/knowledge/items` - List knowledge items
- `POST /api/knowledge/items` - Create knowledge item
- `PUT /api/knowledge/items/{id}` - Update knowledge item
- `DELETE /api/knowledge/items/{id}` - Delete knowledge item

### Training
- `GET /api/knowledge/rules` - List corporate rules
- `POST /api/knowledge/rules` - Create rule
- `DELETE /api/knowledge/rules/{id}` - Delete rule
- `GET /api/knowledge/corrections` - List corrections
- `POST /api/knowledge/corrections` - Create correction

### Moderation
- `GET /api/knowledge/moderation` - Moderation queue
- `POST /api/knowledge/moderation/{id}/action` - Approve/reject

### Analytics
- `POST /api/analytics/reports/upload` - Upload sales report
- `GET /api/analytics/reports` - List reports
- `GET /api/analytics/reports/{id}/analytics` - Report analytics
- `GET /api/analytics/reports/{id}/managers` - Manager analysis
- `GET /api/analytics/reports/{id}/clients` - Client analysis
- `GET /api/analytics/reports/{id}/recommendations` - AI recommendations
- `POST /api/analytics/ask` - Ask about sales data

### Monitoring
- `GET /api/monitoring/stats` - System statistics

## LLM Configuration

Uses [AI Tunnel](https://aitunnel.ru) as OpenAI-compatible API provider.

Recommended models:
- **Chat**: `gpt-4.1-mini` (good balance of quality/cost)
- **Analysis**: `gpt-4.1-mini`
- **Embeddings**: `text-embedding-3-small`

For lower costs, use `gpt-4.1-nano` or `deepseek-v4-flash`.

## TrueConf Integration

The TrueConf bot module is prepared at `backend/app/services/trueconf_bot.py`.
Set `TRUECONF_API_URL`, `TRUECONF_API_KEY`, and `TRUECONF_BOT_ID` in `.env` when ready.
