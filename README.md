# FinanceGPT 💰

<div align="center">

**Your AI-Powered Personal Finance Assistant**

An intelligent financial management platform that helps you track spending, optimize rewards, analyze investments, and make smarter money decisions using AI.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

[Features](#features) • [Quick Start](#quick-start) • [Architecture](#architecture) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

---

## 🌟 Features

### 🤖 AI-Powered Insights
- **Smart Transaction Analysis**: Automatically categorize and analyze spending patterns
- **Personalized Recommendations**: Get AI-driven suggestions for saving money and optimizing rewards
- **Natural Language Queries**: Ask questions about your finances in plain English
- **Predictive Analytics**: Forecast future spending and identify potential savings

### 💳 Financial Management
- **Multi-Account Aggregation**: Connect bank accounts, credit cards, and investment platforms via Plaid
- **Real-Time Tracking**: Monitor balances, transactions, and net worth in real-time
- **Credit Card Optimization**: Find the best rewards cards based on your spending patterns
- **Subscription Detection**: Identify and track recurring payments

### 📊 Analytics & Reporting
- **Interactive Dashboards**: Visualize spending trends, income, and investments
- **Custom Reports**: Generate detailed financial reports and summaries
- **Portfolio Performance**: Track investment returns and analyze portfolio allocation
- **Budget Management**: Set and monitor budgets with smart alerts

### 🔒 Security & Privacy
- **Bank-Level Encryption**: 256-bit SSL encryption for all data
- **Secure Authentication**: OAuth 2.0 and Google Sign-In support
- **Data Privacy**: Your financial data stays private and secure

### 🔗 Integrations
- **100+ Financial Institutions**: Banks, credit cards, investment platforms, crypto exchanges
- **Plaid Integration**: Secure connection to financial accounts
- **Real-Time Sync**: Automatic transaction updates
- **Export Options**: Download your data anytime

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ and **pnpm**
- **Python** 3.11+
- **Docker** and **Docker Compose**
- **PostgreSQL** 15+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/FinanceGPT.git
   cd FinanceGPT
   ```

2. **Set up environment variables**
   ```bash
   # Copy example env files
   cp financegpt_web/.env.example financegpt_web/.env.local
   cp financegpt_backend/.env.example financegpt_backend/.env
   ```

3. **Start the services with Docker**
   ```bash
   docker-compose up -d
   ```

4. **Install frontend dependencies**
   ```bash
   cd financegpt_web
   pnpm install
   pnpm dev
   ```

5. **Install backend dependencies**
   ```bash
   cd ../financegpt_backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Start the backend**
   ```bash
   uvicorn main:app --reload
   ```

8. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## 🏗️ Architecture

### Tech Stack

#### Frontend (`financegpt_web/`)
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn/ui, Radix UI
- **State Management**: Jotai
- **Animations**: Framer Motion
- **Real-Time**: ElectricSQL

#### Backend (`financegpt_backend/`)
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **AI/ML**: LangChain, OpenAI GPT-4
- **Database**: PostgreSQL with SQLAlchemy
- **Task Queue**: Celery with Redis
- **Financial Data**: Plaid API
- **Authentication**: OAuth 2.0

#### Infrastructure
- **Database**: PostgreSQL 15
- **Cache**: Redis
- **Message Broker**: Redis (for Celery)
- **Container**: Docker & Docker Compose

### Project Structure

```
FinanceGPT/
├── financegpt_web/          # Next.js frontend application
│   ├── app/                 # App router pages
│   ├── components/          # React components
│   ├── lib/                 # Utilities and helpers
│   └── public/              # Static assets
├── financegpt_backend/      # FastAPI backend application
│   ├── app/
│   │   ├── agents/          # AI agents and tools
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── tasks/           # Celery tasks
│   │   └── utils/           # Utilities
│   └── alembic/             # Database migrations
├── financegpt_browser_extension/  # Browser extension
├── docker-compose.yml       # Docker services configuration
└── README.md               # This file
```

---

## 📖 Documentation

### Configuration

#### Plaid API Setup
1. Sign up for a [Plaid account](https://plaid.com/)
2. Get your API keys (Client ID and Secret)
3. Add to `financegpt_backend/.env`:
   ```env
   PLAID_CLIENT_ID=your_client_id
   PLAID_SECRET=your_secret
   PLAID_ENV=sandbox  # or development/production
   ```

#### OpenAI API Setup
1. Get your API key from [OpenAI](https://platform.openai.com/)
2. Add to `financegpt_backend/.env`:
   ```env
   OPENAI_API_KEY=your_api_key
   ```

#### Database Configuration
```env
DATABASE_URL=postgresql://user:password@localhost:5432/financegpt
```

### API Endpoints

#### Financial Data
- `GET /api/accounts` - List all connected accounts
- `GET /api/transactions` - Get transactions
- `POST /api/plaid/link-token` - Create Plaid Link token
- `POST /api/plaid/exchange-token` - Exchange public token

#### AI Features
- `POST /api/chat` - Chat with AI assistant
- `POST /api/analyze/spending` - Analyze spending patterns
- `POST /api/optimize/credit-card` - Get credit card recommendations
- `GET /api/insights` - Get personalized insights

---

## 🧪 Development

### Running Tests

**Frontend:**
```bash
cd financegpt_web
pnpm test
```

**Backend:**
```bash
cd financegpt_backend
pytest
```

### Code Quality

**Frontend:**
```bash
pnpm lint
pnpm type-check
```

**Backend:**
```bash
ruff check .
mypy .
```

### Database Migrations

**Create a new migration:**
```bash
cd financegpt_backend
alembic revision --autogenerate -m "Description"
```

**Apply migrations:**
```bash
alembic upgrade head
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Next.js](https://nextjs.org/), [FastAPI](https://fastapi.tiangolo.com/), and [LangChain](https://langchain.com/)
- Financial data powered by [Plaid](https://plaid.com/)
- AI capabilities powered by [OpenAI](https://openai.com/)

---

## 📧 Contact

For questions or support, please open an issue or contact us at support@financegpt.com

---

<div align="center">
Made with ❤️ by the FinanceGPT Team
</div>
