# FinSight 360: AI Analytics Assistant

## 1. System Architecture

The AI Analytics Assistant is designed as a standalone module integrated over the existing FinSight 360 data warehouse. It operates independently of the ETL and ML training pipelines, interacting strictly with the final serving layer in PostgreSQL.

### Core Components
*   **API Gateway (FastAPI)**: Serves REST endpoints (`/api/chat`, `/api/health`) for the React frontend.
*   **Intent Detector**: Classifies user queries into 9 defined business domains using deterministic Regex pattern matching as the primary filter, and LLM-based categorization as a fallback.
*   **SQL Generator**: Uses domain-specific contexts to map natural language to the `customer360` star schema (fact/dim tables, ML predictions, and views).
*   **SQL Validator (Security Layer)**: Rigorously analyzes generated SQL before execution to prevent SQL injection and unauthorized data access.
*   **Database Service**: Manages connections via SQLAlchemy `QueuePool`, enforces `READ ONLY` transaction isolation, and executes validated queries with strict statement timeouts.
*   **Recommendation Engine**: Synthesizes query results (particularly SHAP drivers and risk metrics) into actionable business strategies.
*   **Response Builder**: Formats the final payload, ensuring clear attribution for all data sources (Database, ML Prediction, SHAP Explanation, LLM Generated).

---

## 2. Security Posture

A primary requirement for the AI assistant is that it **MUST NOT** execute arbitrary or destructive SQL. This is enforced through multiple redundant layers of security:

1.  **Regex-Based Keyword Blocking**:
    The `SQLValidator` employs strict Regex checks to block any query containing destructive keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `EXEC`, etc.).
2.  **Schema and Table Whitelisting**:
    The validator parses the query to ensure only tables and views within the `customer360` schema are accessed. Queries attempting to access `pg_catalog`, `information_schema`, or other system/unauthorized schemas are immediately rejected.
3.  **Transaction-Level Enforcement**:
    The `DatabaseService` wraps every query execution with `SET TRANSACTION READ ONLY;`, ensuring that even if a mutating query bypasses the regex checks, the database engine will reject the transaction.
4.  **Automatic Row Limiting**:
    To prevent memory exhaustion and database lockups, all queries are intercepted and appended with a `LIMIT` clause (default 100) if they don't already possess an acceptable limit.
5.  **Role-Based Access Control (RBAC)**:
    While implemented at the application level, the production database user configured in `.env` should also be restricted to `SELECT` permissions strictly on the `customer360` schema.

---

## 3. Interview Defense / Design Decisions

### Q: Why use a Two-Tier Intent Detection system instead of relying purely on the LLM?
**Defense:** LLMs introduce latency and non-determinism. By placing a regex-based deterministic keyword matcher in front of the LLM, we resolve 80-90% of standard business queries (e.g., "What is the total revenue?", "Show me high risk customers") in under 5 milliseconds. The LLM is only invoked as a fallback for ambiguous or highly complex questions, significantly reducing API costs and improving user experience.

### Q: Why not use a standard LangChain SQLAgent?
**Defense:** LangChain SQLAgents often suffer from hallucination, schema confusion, and arbitrary query generation. In a financial/banking context, this introduces unacceptable security risks and data inaccuracy. Our pipeline pattern (`Request` → `IntentDetector` → `SQLGenerator` → `SQLValidator` → `DatabaseService` → `ResponseBuilder`) enforces deterministic control, strict security validation, and explicit source attribution that standard agents lack.

### Q: How do you handle Data Attribution?
**Defense:** The system explicitly categorizes returned insights. We map raw data to `Database` (e.g., total revenue), predictive models to `ML Prediction` (e.g., churn probability, CLV tier), SHAP feature mappings to `SHAP Explanation` (e.g., top risk drivers), and the final synthesized summary to `LLM Generated`. This prevents "black-box" answers and builds trust with banking analysts.

### Q: How does the system handle complex business logic like "Churn"?
**Defense:** The SQL generator is injected with strict schema metadata. When "churn" is detected, the LLM prompt provides explicit instructions on how to join `dim_customer` with `ml_churn_predictions` and `ml_customer_segments`, ensuring it utilizes the pre-computed ETL data rather than attempting to compute risk on the fly.

---

## 4. Technology Stack

*   **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic, Pytest.
*   **Frontend**: React (Vite), CSS (Glassmorphic Dark Theme), Fetch API.
*   **LLM Provider**: Google Gemini (via `google-genai` SDK), with fallback to OpenAI GPT-4o-mini.
*   **Database**: PostgreSQL (Integration with existing FinSight 360 Warehouse).
