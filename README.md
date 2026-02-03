# FinanceGPT 💰

<div align="center">

<img src="financegpt.png" alt="FinanceGPT Logo" width="180" />

### Your AI-Powered Personal CPA

**Connect bank accounts • Upload tax forms • Get instant insights**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

[Quick Start](#-quick-start) • [Features](#-features) • [Example Prompts](#-example-prompts) • [Privacy](#-privacy-first-design) • [Contributing](#-contributing)

</div>

---

## 🚀 Quick Start

Choose your preferred setup method:

### Option 1: All-in-One Docker (Easiest)

```bash
# Clone and run with a single container
git clone https://github.com/yourusername/FinanceGPT.git
cd FinanceGPT

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your OPENAI_API_KEY, PLAID_CLIENT_ID, PLAID_SECRET

# Start FinanceGPT
docker compose -f docker-compose.quickstart.yml up -d
```

🎉 **Open http://localhost:3000** — You're done!

---

### Option 2: Local Development (macOS)

```bash
# Clone the repository
git clone https://github.com/yourusername/FinanceGPT.git
cd FinanceGPT

# Start infrastructure (PostgreSQL, Redis)
docker compose up -d db redis electric

# Run the dev script (opens 3 terminal tabs automatically)
chmod +x dev.sh
./dev.sh
```

This starts:
- 🔧 **Backend API** on http://localhost:8000
- 🔄 **Celery Worker** for background tasks
- 🌐 **Frontend** on http://localhost:3000

---

### Option 3: Full Docker Stack

```bash
# Clone the repository
git clone https://github.com/yourusername/FinanceGPT.git
cd FinanceGPT

# Configure environment
cp financegpt_backend/.env.example financegpt_backend/.env
# Edit .env with your API keys

# Build and run all services
docker compose up -d --build

# View logs
docker compose logs -f
```

---

## 🔐 Privacy-First Design

Your financial data is sensitive. FinanceGPT is built with privacy as a core principle:

| Feature | How It Protects You |
|---------|---------------------|
| **🔒 PII Masking** | SSN and EIN are **masked before any LLM call** (`123-45-6789` → `XXX-XX-XXXX`). Your tax forms never expose sensitive IDs. |
| **🏠 Self-Hostable** | Run entirely on your own hardware. Your data never leaves your machine. |
| **🤖 BYO Model** | Use your own LLM (OpenAI, Anthropic, or **local Ollama**). No vendor lock-in. |
| **🔐 Local Processing** | Sensitive field extraction (SSN, EIN) happens locally—not via cloud APIs. |
| **🗄️ Your Database** | All data stored in your PostgreSQL instance. Export or delete anytime. |
| **🚫 No Telemetry** | Zero tracking, zero analytics, zero data collection. |

```python
# Example: How we handle your W2
raw_text = "SSN: 123-45-6789, Wages: $183,000"
masked_text = mask_pii_in_text(raw_text)  
# → "SSN: XXX-XX-XXXX, Wages: $183,000"
# Only masked_text is sent to the LLM
```

---

## 💬 Example Prompts

Just ask questions in plain English. FinanceGPT understands context.

### 💰 Income & Tax Questions
```
"How much did I earn in 2024?"
"What was my total federal tax withheld?"
"Will I get a tax refund this year?"
"Show me my W2 summary"
"What state taxes did I pay?"
```

### 📊 Spending Analysis
```
"How much did I spend on restaurants last month?"
"What are my recurring subscriptions?"
"Find all Amazon purchases over $100"
"What's my biggest expense category?"
"Show spending trends for the last 3 months"
```

### 💳 Credit Card Optimization
```
"Which card should I use for groceries?"
"Am I using the right credit card for travel?"
"How much rewards am I missing out on?"
"Optimize my credit card usage"
```

### 📈 Investment Portfolio
```
"How are my stocks performing today?"
"What's my portfolio return this year?"
"Is my allocation correct for my age?"
"Should I rebalance according to Bogleheads?"
"Can I harvest any tax losses?"
```

### 🏦 Account Overview
```
"What's my net worth?"
"Show all my account balances"
"How much do I have in savings?"
"What's my monthly cash flow?"
```

---

## 🌟 Features

### 🤖 AI-Powered Financial Advisor
- **Natural Language Queries**: Ask questions about your finances in plain English
- **Smart Transaction Search**: "How much did I spend on restaurants last year?"
- **Personalized Recommendations**: AI-driven suggestions for saving money
- **Tax Form Analysis**: Upload W2s, 1099s and get instant summaries

### 💳 Smart Credit Card Optimization
- **Rewards Maximization**: Get the best card for each purchase category
- **Spending Pattern Analysis**: Identify where you're leaving money on the table
- **Multi-Card Strategy**: Optimize rewards across all your cards

### 📈 Investment Portfolio Management
- **Real-Time Performance**: Track returns with live Yahoo Finance data
- **Time-Based Analysis**: WoW, MoM, QoQ, YoY performance tracking
- **Tax Loss Harvesting**: Find opportunities to reduce your tax bill
- **Rebalancing Recommendations**: Compare to Bogleheads, Three-Fund Portfolio

### 📋 Tax Document Processing
- **Supported Forms**: W2, 1099-INT, 1099-DIV, 1099-B, 1099-MISC, 1095-C
- **LLM-Powered Extraction**: Accurate parsing with structured output
- **Tax Estimate**: Calculate potential refund or amount owed
- **State Tax Support**: Extracts state wages and withholdings

### 💰 Transaction & Spending Analysis
- **100+ Financial Institutions**: Connect via Plaid
- **Subscription Detection**: Find forgotten recurring charges
- **Category Analysis**: Understand where your money goes
- **Historical Comparisons**: Compare spending across time periods

---

## 🏗️ Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 15, TypeScript, Tailwind | Modern web UI with server components |
| **Backend** | FastAPI, Python 3.11+ | Async API with auto-generated docs |
| **Database** | PostgreSQL + pgvector | Relational + vector search |
| **Task Queue** | Celery + Redis | Background document processing |
| **AI** | LiteLLM | Provider-agnostic (OpenAI, Anthropic, Ollama) |
| **Banking** | Plaid API | 100+ financial institution connections |
| **Auth** | Better Auth | OAuth 2.0, Google Sign-In |

### Project Structure

```
FinanceGPT/
├── financegpt_web/          # Next.js frontend
│   ├── app/                 # App router pages
│   ├── components/          # React components
│   └── lib/                 # Utilities
├── financegpt_backend/      # FastAPI backend
│   ├── app/
│   │   ├── agents/          # AI agents and tools
│   │   ├── parsers/         # Tax form parsers
│   │   ├── routes/          # API endpoints
│   │   └── tasks/           # Celery tasks
│   └── alembic/             # Database migrations
├── docker-compose.yml       # Full stack deployment
├── docker-compose.quickstart.yml  # All-in-one container
└── dev.sh                   # Local development script
```

---

## 📖 Configuration

### Required Environment Variables

```env
# LLM Provider (choose one)
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY=sk-ant-...
# or GOOGLE_API_KEY=AIza...

# Plaid (for bank connections)
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_secret
PLAID_ENV=sandbox

# Security
SECRET_KEY=your-random-secret-key
```

### Optional Configuration

```env
# Document Processing
UNSTRUCTURED_API_KEY=...     # For PDF parsing
ETL_SERVICE=DOCLING          # Or UNSTRUCTURED

# Voice Features
TTS_SERVICE=local/kokoro
STT_SERVICE=local/base
```

---

## 🧪 Development

### Running Tests

```bash
# Backend
cd financegpt_backend && pytest

# Frontend  
cd financegpt_web && pnpm test
```

### Database Migrations

```bash
cd financegpt_backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md).

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

- Built on [SurfSense](https://github.com/MODSetter/SurfSense), an open-source NotebookLM alternative
- Financial data powered by [Plaid](https://plaid.com/)
- AI capabilities via [LiteLLM](https://github.com/BerriAI/litellm)

---

<div align="center">

Made with ❤️ for anyone who's ever stared at a W2 wondering what it all means.

**[⬆ Back to Top](#financegpt-)**

</div>
