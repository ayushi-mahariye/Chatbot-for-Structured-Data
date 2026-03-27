# 🤖 AI Assistant with RBAC & SQL Generation

> An enterprise-grade AI-powered conversational assistant with Role-Based Access Control (RBAC), dynamic SQL generation, multi-model AI support, and persistent database-backed conversations.

---

## 📌 Overview

This project is a **secure, multi-user AI assistant** that integrates large language models with a structured permission system. It supports role-based access control to manage what different users can query or access, generates SQL from natural language, and maintains persistent conversation history — all backed by a database layer.

---

## 🗂️ Project Structure

```
AI-RBAC-Assistant/
├── main (7).py            # Entry point — app initialization & API routing
├── ai_models.py           # AI model integrations & LLM abstraction layer
├── conversation.py        # Conversation history & context management
├── database.py            # Database connection, ORM models & queries
├── sql_generator.py       # Natural language → SQL query generation
├── rbac_service.py        # Core RBAC logic — roles, permissions, enforcement
├── rbac_service.py.new    # Updated/patched RBAC service (in-progress)
├── rbac_service_fixed.py  # Stable fixed version of RBAC service
├── apply_rbac_fix.py      # Migration/patch script to apply RBAC fixes
├── config.py              # App configuration & environment settings
├── setup.py               # Project setup & dependency installer
└── requirements.txt       # Python dependencies
```

---

## ✨ Features

- 🔐 **Role-Based Access Control (RBAC)** — Fine-grained permission management across users and roles
- 🧠 **Multi-Model AI Support** — Abstracted AI layer supporting multiple LLM providers via `ai_models.py`
- 💬 **Persistent Conversations** — Full conversation history stored and retrieved from the database
- 🗄️ **SQL Generation** — Convert natural language questions into executable SQL queries
- 🗃️ **Database Integration** — Structured data layer for users, roles, permissions, and conversations
- ⚙️ **Configurable Setup** — Centralized config and automated setup script for fast onboarding
- 🛠️ **RBAC Patching Support** — Version-controlled RBAC fixes with migration scripts

---

## 🔐 RBAC Architecture

The permission system is built around three core files:

| File | Purpose |
|---|---|
| `rbac_service.py` | Original RBAC service — role & permission definitions |
| `rbac_service.py.new` | In-progress updates to RBAC logic |
| `rbac_service_fixed.py` | Stable, production-ready RBAC service |
| `apply_rbac_fix.py` | Script to migrate from old to fixed RBAC |

### Role Hierarchy (Example)

```
Admin
 ├── Full access to all queries & AI models
 ├── Can manage users and roles
Manager
 ├── Can run SQL queries on permitted tables
 ├── Can view conversation history
User
 └── Basic AI conversation access only
```

---

## 🗄️ SQL Generation

The `sql_generator.py` module enables natural language to SQL conversion:

```python
# Example
user_query = "Show me all orders placed in the last 7 days"
# Generated SQL:
# SELECT * FROM orders WHERE created_at >= NOW() - INTERVAL '7 days';
```

Access is gated by RBAC — users can only generate SQL for tables their role permits.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- pip
- A running database (PostgreSQL / SQLite)
- An LLM API key (Anthropic, OpenAI, or similar)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ayushi-mahariye/<repo-name>.git
   cd <repo-name>
   ```

2. **Run setup**
   ```bash
   python setup.py
   ```

   Or install manually:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**

   Create a `.env` file:
   ```env
   AI_API_KEY=your_llm_api_key
   DATABASE_URL=postgresql://user:password@localhost/dbname
   SECRET_KEY=your_app_secret
   DEFAULT_ROLE=user
   ```

4. **Initialize the database**
   ```bash
   python database.py --init
   ```

5. **Apply RBAC fixes (if upgrading)**
   ```bash
   python apply_rbac_fix.py
   ```

6. **Start the application**
   ```bash
   python "main (7).py"
   ```

---

## ⚙️ Configuration

All settings live in `config.py`:

| Setting | Description |
|---|---|
| `AI_MODEL` | Default LLM model to use |
| `DATABASE_URL` | Database connection string |
| `RBAC_ENABLED` | Toggle RBAC enforcement on/off |
| `MAX_CONVERSATION_HISTORY` | Number of past messages to include in context |
| `SQL_GENERATION_ENABLED` | Enable/disable natural language SQL feature |
| `DEBUG` | Toggle debug mode |

---

## 💬 Conversation Management

`conversation.py` handles:
- Storing and retrieving full conversation threads per user
- Injecting conversation history into AI model context
- Clearing or archiving old sessions
- Role-aware context filtering (users only see their own history)

---

## 🧠 AI Models

`ai_models.py` provides a unified interface for multiple LLM providers:

```python
from ai_models import get_model_response

response = get_model_response(
    model="claude-3",
    messages=conversation_history,
    user_role="manager"
)
```

---

## 🛠️ API Usage

### Send a Message

```http
POST /chat
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "message": "Show me sales data for last quarter",
  "session_id": "abc123"
}
```

### Generate SQL

```http
POST /sql/generate
Authorization: Bearer <jwt_token>

{
  "query": "List all users who signed up this month"
}
```

**Response:**
```json
{
  "sql": "SELECT * FROM users WHERE created_at >= DATE_TRUNC('month', NOW());",
  "permitted": true
}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is open-source. See [LICENSE](LICENSE) for details.

---

## 👩‍💻 Author

**Ayushi Mahariye** — [@ayushi-mahariye](https://github.com/ayushi-mahariye)

---

> ⭐ Star this repo if you found it useful!
