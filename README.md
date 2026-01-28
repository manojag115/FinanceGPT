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

### 🤖 AI-Powered Financial Advisor
- **Smart Transaction Search**: Search your financial history using natural language queries
  - "How much did I spend on restaurants last year?"
  - "Show me all charges from United Airlines"
  - "Find my recurring subscriptions"
- **Personalized Recommendations**: Get AI-driven suggestions for saving money and optimizing rewards
- **Natural Language Queries**: Ask questions about your finances in plain English
- **Predictive Analytics**: Forecast future spending and identify potential savings

### 💳 Smart Credit Card Optimization
- **Rewards Analysis**: Analyze your spending patterns to find the best credit cards
  - "Which credit card should I use for restaurant purchases?"
  - "Am I using the right credit card for my spending?"
- **Category-Based Optimization**: Get recommendations based on merchants and categories
- **Multi-Card Strategy**: Optimize rewards across multiple credit cards

### 📈 Investment Portfolio Management
- **Real-Time Performance Tracking**: Monitor your investment returns with live market data
  - "How are my stocks performing today?"
  - "What's my portfolio return over the last year?"
  - "Show my month-over-month performance"
- **Yahoo Finance Integration**: Fetches real-time and historical stock prices
- **Cost Basis Tracking**: Calculate unrealized gains/losses across all holdings
- **Time-Based Analysis**: Week-over-week, month-over-month, quarterly, and yearly performance

### 🎯 Portfolio Allocation & Rebalancing
- **Asset Allocation Analysis**: Understand your portfolio composition (stocks/bonds/cash)
  - "Is my portfolio allocation correct?"
  - "How should I rebalance according to Bogleheads philosophy?"
- **Geographic Diversification**: Track US vs international exposure
- **Investment Philosophy Comparison**: Compare against established strategies
  - Bogleheads Conservative (40/50/10)
  - Bogleheads Moderate (60/35/5)
  - Bogleheads Aggressive (90/10/0)
  - Three-Fund Portfolio
- **Specific Rebalancing Recommendations**: Get dollar amounts for buying/selling
- **Alignment Score**: See how well your portfolio matches your target allocation (0-100)

### 💰 Tax Optimization
- **Tax Loss Harvesting**: Identify opportunities to reduce your tax liability
  - "Can I harvest any tax losses?"
  - "What positions should I sell for tax savings?"
- **Loss Identification**: Finds holdings with unrealized losses
- **Tax Savings Calculator**: Estimates tax benefits based on your tax bracket
- **Replacement Suggestions**: Recommends similar securities to avoid wash sales
- **Wash Sale Warnings**: Alerts about IRS rules and compliance

### 💳 Transaction & Spending Analysis
- **Multi-Account Aggregation**: Connect bank accounts, credit cards, and investment platforms via Plaid
- **Real-Time Tracking**: Monitor balances, transactions, and net worth in real-time
- **Subscription Detection**: Identify and track recurring payments automatically
  - "Check if I have any recurring subscriptions"
  - "What am I paying monthly?"
- **Category-Based Search**: Find transactions by category (restaurants, travel, etc.)
- **Merchant Search**: Search by merchant name with fuzzy matching

### 📊 Analytics & Reporting
- **Interactive Dashboards**: Visualize spending trends, income, and investments
- **Custom Reports**: Generate detailed financial reports and summaries
- **Budget Management**: Set and monitor budgets with smart alerts
- **Historical Comparisons**: Compare spending and performance across time periods

### 🔒 Security & Privacy
- **Bank-Level Encryption**: 256-bit SSL encryption for all data
- **Secure Authentication**: OAuth 2.0 and Google Sign-In support
- **Data Privacy**: Your financial data stays private and secure

### 🔗 Integrations
- **100+ Financial Institutions**: Banks, credit cards, investment platforms, crypto exchanges
- **Plaid Integration**: Secure connection to financial accounts
- **Yahoo Finance**: Real-time stock prices and historical market data
- **Real-Time Sync**: Automatic transaction updates
- **Manual Uploads**: Support for CSV files (bank statements, Fidelity positions, etc.)
- **Export Options**: Download your data anytime

---

## 💬 Example Prompts

### Transaction Search & Analysis
```
"How much did I spend on restaurants last year?"
"Show me all United Airlines charges"
"Find transactions over $100 in the last month"
"What did I spend on groceries this week?"
"Show my Amazon purchases"
```

### Credit Card Optimization
```
"Which credit card should I use for restaurants?"
"Am I using the right credit card for gas purchases?"
"What's the best card for my travel spending?"
"Optimize my credit card usage"
```

### Investment Performance
```
"How are my stocks performing today?"
"What's my portfolio return over the last year?"
"Show my month-over-month investment performance"
"How much have my investments grown this quarter?"
"What's my total portfolio value?"
```

### Portfolio Allocation & Rebalancing
```
"Is my portfolio allocation correct?"
"How should I rebalance according to Bogleheads philosophy?"
"What's my exposure to international stocks?"
"Am I too heavily invested in US stocks?"
"Should I buy more bonds or stocks?"
"Compare my portfolio to a three-fund strategy"
```

### Tax Loss Harvesting
```
"Can I harvest any tax losses?"
"What stocks should I sell for tax losses?"
"How much can I save in taxes by tax loss harvesting?"
"Are there any positions with unrealized losses?"
"Show me tax optimization opportunities"
```

### Subscriptions & Recurring Payments
```
"Check if I have any recurring subscriptions"
"What subscriptions am I paying for?"
"Find all my monthly recurring charges"
"Which services am I subscribed to?"
```

### Financial Planning
```
"What's my net worth?"
"How much am I saving each month?"
"Show my spending trends over the last 3 months"
"What's my biggest expense category?"
```

---

## �️ AI Tools & Capabilities

FinanceGPT uses specialized AI tools to analyze your financial data and provide actionable insights:

### 1. **Transaction Search** (`search_transactions`)
- Searches through all your financial transactions using keywords and categories
- Supports both Plaid-connected accounts and manual CSV uploads
- Fuzzy merchant name matching for accurate results
- Date range filtering and category-based filtering
- Returns transaction summaries with totals and breakdowns

### 2. **Credit Card Optimizer** (`optimize_credit_card_usage`)
- Analyzes spending patterns to recommend optimal credit cards
- Matches merchant categories to card rewards programs
- Compares rewards rates across multiple cards
- Provides specific recommendations per spending category
- Supports both manual uploads and Plaid data

### 3. **Portfolio Performance** (`calculate_portfolio_performance`)
- Fetches real-time stock prices from Yahoo Finance
- Calculates returns over custom time periods (day, week, month, quarter, year)
- Compares current prices to historical prices for accurate performance
- Shows individual holding performance and total portfolio returns
- Supports both snapshot comparisons and live price lookups

### 4. **Portfolio Allocation Analyzer** (`analyze_portfolio_allocation`)
- Analyzes asset class distribution (stocks/bonds/cash)
- Calculates geographic exposure (US vs international)
- Compares portfolio to investment philosophies (Bogleheads, Three-Fund)
- Provides specific rebalancing recommendations with dollar amounts
- Gives alignment score (0-100) showing how close you are to target

### 5. **Tax Loss Harvesting** (`analyze_tax_loss_harvesting`)
- Identifies positions with unrealized losses
- Calculates potential tax savings based on your tax bracket
- Suggests replacement securities to avoid wash sales
- Provides sell/buy recommendations for tax optimization
- Warns about wash sale rules and compliance

### 6. **Subscription Finder** (`find_subscriptions`)
- Automatically detects recurring charges in your transaction history
- Identifies monthly, quarterly, and annual subscriptions
- Calculates total subscription costs
- Helps you find forgotten or unused subscriptions

### 7. **Knowledge Base Search** (`search_knowledge_base`)
- Searches across all your uploaded financial documents
- Vector-based semantic search for accurate results
- Supports PDFs, CSVs, bank statements, and investment reports
- Context-aware retrieval for answering complex questions

---

## �🚀 Quick Start

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
