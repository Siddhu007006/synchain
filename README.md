# SynChain

> **Multi-agent supply chain intelligence platform**

SynChain is a supply chain decision intelligence platform. It simulates supply chain operations, creates digital replicas of real supply chains, forecasts future demand, detects risks through signals, and integrates real-world external data (news, weather, commodities, economics).

## Features

- **Demand forecast**: Predicts what demand will look like in 1, 3, 5 planning horizons
- **Risk assessment**: Determines supply risk level and operational risks
- **Inventory strategy**: Recommends how much to order and when
- **Warehouse selection**: Selects optimal warehouse (W1/W2/W3) based on capacity, cost, and stock
- **Logistics routing**: Plans optimal delivery routes
- **Confidence score**: Provides a trustworthiness score for recommendations
- **Natural language explanation**: Explains why a recommendation was made
- **Signal Intelligence**: Detects internal metrics and external events (weather, news, etc.) to adjust confidence and forecasts.
- **Multi-Tenant Auth**: Full authentication system with RBAC and organizational data isolation.

## Technology Stack

- **Backend**: FastAPI (Python 3.14), SQLite + SQLAlchemy 2.0, Alembic for migrations, Pytest
- **Frontend**: Next.js 16 (React), TypeScript, shadcn/ui + Radix UI, Recharts

## Getting Started

### Backend
1. `cd backend`
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment: Configure `.env` with `DATABASE_URL=sqlite:///./supply_chain.db`
4. Run migrations: `alembic upgrade head`
5. Start server: `uvicorn main:app --reload --port 8000`

### Frontend
1. `cd frontend`
2. Install dependencies: `npm install`
3. Start development server: `npm run dev`

## Documentation

For a comprehensive guide on the architecture, technical details, and the history of development phases, please refer to the documentation:

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Explains the multi-agent design and Digital Twin architecture.
- [PROJECT_GUIDE.md](./PROJECT_GUIDE.md) - A high-level overview of the whole project.

## Development

The backend features a robust testing suite. Run `pytest tests/ -v` to run the 400+ test cases covering agents, twin logic, forecasting, and signals.
