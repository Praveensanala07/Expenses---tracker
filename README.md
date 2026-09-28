# ExpenseFlow Pro — Full-Stack Expense Tracker & Financial Analytics

[![CI Pipeline](https://github.com/Praveensanala07/Expenses---tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Praveensanala07/Expenses---tracker/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/framework-Flask%203.x-black.svg)](https://flask.palletsprojects.com/)
[![Pandas](https://img.shields.io/badge/analytics-Pandas%202.x-150458.svg)](https://pandas.pydata.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ed.svg)](https://www.docker.com/)

A modern, production-grade financial tracking and expenditure analytics web application. Built with **Flask**, **Pandas**, and **SQLite (WAL mode)** on the backend, paired with an ultra-responsive, accessible, dark/light theme dashboard frontend.

---

## Key Features

- **Full Expense Lifecycle (CRUD)**: Create, view, edit (`PUT`), and delete transactions with strict input validation.
- **Analytical Insights via Pandas**: Automatic aggregation of total spending, transaction count, average per transaction, top category, monthly trajectory, and peak expenses.
- **Real-Time Search & Multi-Criteria Filtering**: Instant debounced search by title and notes, category filtering, and sorting (by date or amount, ascending/descending).
- **Interactive Visualizations**:
  - Dynamic spending breakdown bars by category with percentage calculations and transaction tallies.
  - Monthly spending timeline chart with interactive hover tooltips.
- **Multi-Currency Support**: Switch between **₹ INR**, **$ USD**, **€ EUR**, **£ GBP**, and **¥ JPY** with live client-side reformatting.
- **Data Portability (CSV Export)**: One-click export endpoint (`/api/expenses/export`) generating spreadsheet-compatible CSV files.
- **Dual Themes**: Polished Dark Mode and Light Mode with persistence in `localStorage`.
- **Production Architecture**:
  - Application Factory (`create_app`) pattern for clean environment configuration.
  - SQLite Write-Ahead Logging (WAL mode) for high-concurrency read/write operations without database lockups.
  - Hardened security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
  - Container health check endpoint (`/api/health`) for orchestration.
  - Dual WSGI support: **Waitress** for Windows and **Gunicorn** for Linux/Docker environments.
  - Automated CI pipeline with **GitHub Actions** and **pytest** suite.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend API** | Python 3.11+, Flask 3.1, Pandas 2.3 |
| **Database** | SQLite 3 with Write-Ahead Logging (WAL) and foreign keys |
| **Production WSGI** | Gunicorn (Linux/Containers), Waitress (Windows/Cross-platform) |
| **Frontend UI** | Semantic HTML5, Vanilla CSS3 (Custom Design System, Glassmorphism, CSS Grid), Vanilla ES6+ JavaScript |
| **DevOps & CI/CD** | Docker, Docker Compose, GitHub Actions, Pytest |

---

## Project Structure

```
├── app.py                  # Core Flask application factory, REST endpoints, analytics
├── wsgi.py                 # WSGI production server entry point
├── requirements.txt        # Production & development dependencies
├── .env.example            # Environment variables configuration template
├── Dockerfile              # Lean, multi-platform container image
├── docker-compose.yml      # Multi-container orchestration with persistent volume
├── Procfile                # Heroku / Render / Railway deployment definition
├── templates/
│   └── index.html          # Modern, responsive FinTech dashboard UI
├── tests/
│   ├── __init__.py
│   └── test_app.py         # Pytest automated unit and integration tests
└── .github/
    └── workflows/
        └── ci.yml          # GitHub Actions CI workflow
```

---

## Quick Start

### 1. Local Development

```bash
# Clone the repository
git clone https://github.com/Praveensanala07/Expenses---tracker.git
cd Expenses---tracker

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the development server
python app.py
```

Visit **http://127.0.0.1:5000** in your browser.

---

### 2. Running in Production with WSGI

#### Windows (Waitress):
```bash
python wsgi.py
```

#### Linux / macOS (Gunicorn):
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 "app:create_app()"
```

---

### 3. Docker & Docker Compose

Launch the complete application in a self-contained container with persistent data:

```bash
docker compose up --build -d
```

The app will be available on **http://localhost:5000**. The database is safely persisted in a named volume (`expense_data`).

To view logs:
```bash
docker compose logs -f
```

To stop:
```bash
docker compose down
```

---

## Environment Variables

Copy `.env.example` to `.env` and customize as needed:

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `production` | Environment mode (`production` or `development`) |
| `SECRET_KEY` | `prod-insecure-...` | Secret key used for cryptographic signing |
| `DATABASE_PATH` | `expenses.db` | Path to SQLite database file |
| `PORT` | `5000` | Port to bind server |
| `HOST` | `0.0.0.0` | Host interface to bind server |

---

## REST API Reference

### Health Check
- **`GET /api/health`**
  - **Response (200)**:
    ```json
    {
      "database": "connected",
      "record_count": 6,
      "status": "healthy",
      "timestamp": "2026-09-28T19:30:00.000000Z",
      "version": "1.0.0"
    }
    ```

### Expenses Endpoints
- **`GET /api/expenses`**
  - Query parameters:
    - `search` (string): Filter by title or notes keyword.
    - `category` (string): Filter by category name (e.g. `Food`, `Travel`).
    - `start_date` / `end_date` (YYYY-MM-DD): Date range filter.
    - `sort_by` (`date`, `amount`, `title`): Field to order by.
    - `order` (`asc`, `desc`): Sorting direction.
    - `limit` (int, default: 200) / `offset` (int, default: 0): Pagination.
  - **Response (200)**: Array of expense objects.

- **`POST /api/expenses`**
  - **Body**:
    ```json
    {
      "title": "Grocery Shopping",
      "amount": 1250.00,
      "category": "Food",
      "date": "2026-09-28",
      "notes": "Vegetables and dairy"
    }
    ```
  - **Response (201)**: Created expense object with generated ID.

- **`GET /api/expenses/<id>`**
  - **Response (200)**: Single expense object.
  - **Response (404)**: If ID is not found.

- **`PUT /api/expenses/<id>`**
  - **Body**: JSON payload with updated fields (`title`, `amount`, `category`, `date`, `notes`).
  - **Response (200)**: Updated expense object.

- **`DELETE /api/expenses/<id>`**
  - **Response (200)**: `{"message": "Expense deleted successfully", "id": 1}`.

### Analytics & Reports
- **`GET /api/summary`**
  - Aggregates dataset using Pandas.
  - **Response (200)**:
    ```json
    {
      "average": 46527.5,
      "by_category": { "Food": 665.0, "Shopping": 3500.0, "Study": 75000.0, "Travel": 200000.0 },
      "by_category_count": { "Food": 3, "Shopping": 1, "Study": 1, "Travel": 1 },
      "by_month": { "2026-09": 279165.0 },
      "count": 6,
      "highest_expense": {
        "amount": 200000.0,
        "category": "Travel",
        "date": "2026-09-28",
        "id": 3,
        "title": "bike"
      },
      "top_category": "Travel",
      "total": 279165.0
    }
    ```

- **`GET /api/expenses/export`**
  - Generates downloadable CSV spreadsheet stream (`Content-Disposition: attachment; filename=expenses_export_*.csv`).

---

## Testing

Run the automated test suite with pytest:

```bash
pytest -v
```

All 17 integration and unit tests validate validation rules, database persistence, analytics aggregation, and API behavior with 100% passing results.

---

## Deployment Guides

### Render / Railway / Heroku
The included `Procfile` and `requirements.txt` allow 1-click deployments:
- Set Build Command: `pip install -r requirements.txt gunicorn`
- Set Start Command: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 "app:create_app()"`
- Configure persistent disk on `/app/data` and point `DATABASE_PATH=/app/data/expenses.db`.

---

## License

This project is licensed under the [MIT License](LICENSE).
