# Worknoon AI Customer Support Agent

![Build](https://img.shields.io/badge/docker-compose_ready-0d9488?style=for-the-badge)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge)
![Frontend](https://img.shields.io/badge/frontend-Next.js_16-111827?style=for-the-badge)
![Agent](https://img.shields.io/badge/agent-raw_tool_loop-14b8a6?style=for-the-badge)
![Policy](https://img.shields.io/badge/refund_logic-deterministic-22c55e?style=for-the-badge)

> A finished, fully containerized AI customer support product that processes, denies, or escalates e-commerce refunds with a clean customer chat UI and a live admin reasoning dashboard.

![Console — APPROVED refund with live agent trace](docs/assets/console-screenshot.png)

Welcome to the Worknoon AI Engineering Challenge deliverable! This repository contains a complete, production-ready vertical slice of an AI Customer Support Agent. Instead of building a fragile, thin wrapper around an LLM, this project implements a **deterministic-backend with a generative-frontend** architecture. 

The Large Language Model (LLM) is used purely for semantic extraction and empathetic response formatting, while a hard-coded Python policy engine retains absolute authority over the actual business logic. This eliminates hallucinatory approvals and prompt injection vulnerabilities, ensuring the system operates exactly as a corporate enterprise requires.

---

## 🚀 How to Run the Application (Setup & API Keys)

The assignment requires the application to boot instantly with a single command and clearly explain how to provide an API key. We have designed this process to be foolproof.

### 1. Provide an API Key
The application requires an LLM to process natural language. We support **OpenAI** (as requested), as well as Gemini and Groq via a custom adapter pattern. 

First, copy the example environment file:
```bash
cp .env.example .env
```

Open `.env` in your text editor. To use OpenAI, configure it like this:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini  # Optional: defaults to gpt-4o-mini
```

*(Note: If you do not have an OpenAI key on hand, you can also use Gemini (`LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`) or Groq. If no keys are provided, the system gracefully falls back to an offline, regex-based heuristic extractor so the application remains fully testable.)*

### 2. Single-Command Boot
With your `.env` configured, launch the entire stack (Frontend, API, Agent, and Database):
```bash
docker-compose up --build
```
This single command builds the containers, auto-generates the SQLite database, seeds it with 15 synthetic CRM profiles and 31 orders, and starts the services.

### 3. Open the Dashboard
Once the terminal shows both containers are running, open your browser:
- **Support Console UI**: [http://localhost:3000](http://localhost:3000)
- **Backend Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

*(If ports 3000 or 8000 are occupied on your machine, simply add `API_PORT=8010`, `FRONTEND_PORT=3010`, `FRONTEND_ORIGIN=http://localhost:3010`, and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8010` to your `.env` file and run `docker-compose up --build`)*

---

## 🧠 Architectural Overview of the Agent Loop

To fulfill the requirement of clean system architecture, we intentionally avoided heavy, opaque orchestration frameworks like CrewAI or LangGraph. Instead, the agent loop is implemented as a **raw function-calling pipeline**. This "zero-magic" approach guarantees 100% observability and strict state management.

![Agent loop diagram](docs/assets/agent-loop.png)

When a customer submits a refund request via the UI, the FastAPI backend routes the message through an explicit, 8-stage pipeline (`backend/app/agent/runner.py`):

1. **Intake & Context Binding**: The system receives the message and binds the customer's email to the current conversation session.
2. **Lexical Safety Scan**: Before the LLM ever sees the prompt, a security guardrail (`guardrails.py`) scans the text against 35 known prompt-injection attack vectors (e.g., "ignore previous instructions", "override policy").
3. **Structured Extraction (The LLM Layer)**: The OpenAI/Gemini model is invoked with a strict JSON schema. Its *only* job is to comprehend the natural language and extract the `order_id`, `customer_email`, `reason`, and `sentiment`. It does not make decisions.
4. **Dynamic Tool Execution**: Using the extracted JSON, the Python backend executes local tool functions. It queries the synthetic SQLite CRM to retrieve the exact order details and the customer's fraud-risk profile.
5. **Deterministic Policy Engine (The Brains)**: The fetched data is fed into a mathematical Python rule engine (`policy.py`). The engine evaluates the data against 10 hard-coded corporate rules (e.g., *Is it past 30 days? Is it final sale? Is the customer high risk?*).
6. **Backend Decision Lock**: The engine computes the final outcome (`APPROVED`, `DENIED`, or `ESCALATED`) and permanently locks this decision into the SQLite database.
7. **Response Composition (The LLM Layer)**: The LLM is invoked a second time. It is handed the *locked decision* and the factual reasons, and is instructed to draft a polite, empathetic response to the customer. **The LLM cannot override the locked decision.**
8. **Live Trace Stream (SSE)**: Throughout steps 1-7, the backend emits granular, structured JSON events via Server-Sent Events (SSE). The Next.js frontend consumes this stream, rendering the live reasoning timeline in the Admin Dashboard.

---

## 🖼️ UI Gallery: Evaluator Scenarios

The assignment asks to evaluate how the agent handles edge cases, policy violations, and aggressive injections. The Next.js frontend includes quick-test buttons to instantly demonstrate these exact scenarios. 

*All screenshots below are real, verified browser captures of the live application running on `localhost`.*

**1. Initial State — Ready for a refund case**
![Initial state](docs/assets/screenshot-initial.png)

**2. APPROVED — Clean refund (Triggers Rule R9)**
*(Valid order, within 30 days, under $500, not final sale)*
![APPROVED](docs/assets/console-screenshot.png)

**3. DENIED — Policy Violation: Final Sale (Triggers Rule R2)**
*(The policy engine detects the `final_sale` boolean in the CRM and denies it)*
![DENIED](docs/assets/screenshot-denied.png)

**4. ESCALATED — Edge Case: High Value (Triggers Rule R4)**
*(Orders over $500 must be escalated to a human manager)*
![ESCALATED - Value](docs/assets/screenshot-escalated.png)

**5. ESCALATED — Edge Case: High Fraud Risk (Triggers Rule R10)**
*(The CRM flags this user as HIGH risk; the agent safely escalates rather than approving)*
![ESCALATED - Fraud](docs/assets/screenshot-fraud.png)

**6. DENIED — Agent Resilience: Prompt Injection Blocked**
*(The user attempts to force an approval using an "ignore previous instructions" jailbreak. The lexical scanner catches it, flags it in amber on the trace timeline, and the backend lock enforces the true policy.)*
![INJECTION BLOCKED](docs/assets/screenshot-injection.png)

---

## 📊 Synthetic CRM & Data Model

To ensure the system works out-of-the-box without requiring access to an external company database, the FastAPI `lifespan` event automatically boots an embedded SQLite database.

![Data model diagram](docs/assets/data-model.svg)

The database is seeded with `synthetic_crm.json`, which contains:
- **15 Customer Profiles**: Ranging from loyal Gold-tier customers to new accounts flagged with a `HIGH` fraud risk.
- **31 Order Histories**: Specifically crafted to trigger every possible policy edge case (orders over 30 days old, final sale items, digital goods, high-value electronics, and pending shipments).

When the agent executes its dynamic tools, it performs actual SQLAlchemy ORM queries against this relational data, proving the end-to-end integration of the system.

---

## 🛠️ Tech Stack & Verification

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend** | Next.js 16 (App Router) & React 19 | Provides a robust SPA with dark monochrome glassmorphic styling, utilizing native Server-Sent Events for the trace timeline. |
| **Backend** | FastAPI (Python 3.12) | High-performance, async-first API layer. Ideal for AI workloads due to native Pydantic v2 validation. |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-dependency relational database, perfect for a containerized assignment deliverable. |
| **LLM Orchestration** | Custom Raw Function Loop | Ensures maximum observability, clean separation of concerns, and prevents framework bloat. |
| **Containerization**| Docker Compose | Guarantees the exact same execution environment for the evaluation team. |

### Verifying the System
The system architecture and logic are physically tested and proven by a robust Pytest suite. To verify the system's resilience yourself while the containers are running, execute:
```bash
docker-compose exec backend pytest
```
This will run 56 automated unit tests inside the backend container to validate the 10 policy rules, test the 35-pattern injection scanner, and ensure the LLM extractor handles malformed data gracefully.

---
*Built for the Worknoon AI Engineer Evaluation - June 2026*
