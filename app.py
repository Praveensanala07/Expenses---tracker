"""Expense Tracker: Production-grade Full Stack Web Application.
Frontend (Modern UI) <-> Flask REST API <-> SQLite (WAL-enabled) + Pandas Analytics.
"""

import csv
import io
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
from flask import Flask, Response, g, jsonify, render_template, request

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("expense-tracker")

# Supported categories with display metadata
VALID_CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Study",
    "Health",
    "Entertainment",
    "Work",
    "Other"
]

ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_db_path(app_config: Dict[str, Any]) -> str:
    """Resolve database path from configuration or environment variable."""
    return app_config.get("DATABASE_PATH") or os.environ.get("DATABASE_PATH", "expenses.db")


def get_db(db_path: str):
    """Retrieve or create SQLite connection for the current Flask application context."""
    if "db" not in g:
        # Ensure parent directory exists if a path with directories is supplied
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        g.db = sqlite3.connect(db_path, timeout=10.0)
        g.db.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) for concurrent read/write and foreign keys
        try:
            g.db.execute("PRAGMA journal_mode=WAL;")
            g.db.execute("PRAGMA foreign_keys=ON;")
        except sqlite3.OperationalError:
            pass
    return g.db


def close_db(e=None):
    """Close the database connection on context teardown."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path: str):
    """Initialize SQLite database tables and apply backward-compatible schema migrations."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS expenses (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   title TEXT NOT NULL,
                   amount REAL NOT NULL,
                   category TEXT NOT NULL,
                   date TEXT NOT NULL,
                   notes TEXT DEFAULT ''
               )"""
        )
        # Migrate schema safely if notes column does not exist in legacy database
        cursor = conn.execute("PRAGMA table_info(expenses)")
        columns = [row[1] for row in cursor.fetchall()]
        if "notes" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN notes TEXT DEFAULT ''")
        conn.commit()


def validate_expense_payload(data: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Strict input validation for expense creation and updates."""
    if not isinstance(data, dict):
        return None, "Invalid JSON payload"

    title = str(data.get("title", "")).strip()
    category = str(data.get("category", "")).strip()
    date_str = str(data.get("date", "")).strip()
    notes = str(data.get("notes", "")).strip()

    if not title:
        return None, "Title is required"
    if len(title) > 100:
        return None, "Title must be 100 characters or less"

    if not category:
        return None, "Category is required"
    if len(category) > 50:
        return None, "Category must be 50 characters or less"

    if not date_str or not ISO_DATE_REGEX.match(date_str):
        return None, "Date is required and must follow YYYY-MM-DD format"
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None, "Invalid calendar date provided"

    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return None, "Amount must be a valid number"

    if amount <= 0:
        return None, "Amount must be greater than 0"
    if amount > 1_000_000_000:
        return None, "Amount exceeds reasonable threshold"

    amount = round(amount, 2)

    return {
        "title": title,
        "amount": amount,
        "category": category,
        "date": date_str,
        "notes": notes[:500]  # Cap notes length to 500 chars
    }, None


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for Flask app."""
    app = Flask(__name__)

    # Default production configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "prod-insecure-secret-key-change-me"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "expenses.db"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB max request payload
    )

    if test_config:
        app.config.update(test_config)

    db_path = get_db_path(app.config)
    init_db(db_path)

    # Register teardown
    app.teardown_appcontext(close_db)

    # Security Headers Middleware
    @app.after_request
    def set_security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Web Dashboard Route
    @app.get("/")
    def home():
        return render_template("index.html")

    # Health Check API
    @app.get("/api/health")
    def health_check():
        try:
            conn = get_db(db_path)
            row = conn.execute("SELECT COUNT(*) as count FROM expenses").fetchone()
            total_count = row["count"] if row else 0
            return jsonify(
                status="healthy",
                version="1.0.0",
                timestamp=datetime.now(timezone.utc).isoformat(),
                database="connected",
                record_count=total_count
            ), 200
        except Exception as ex:
            logger.error("Health check failed: %s", ex)
            return jsonify(status="unhealthy", error=str(ex)), 500

    # READ: List expenses with query filters & pagination
    @app.get("/api/expenses")
    def list_expenses():
        category = request.args.get("category", "").strip()
        search = request.args.get("search", "").strip()
        start_date = request.args.get("start_date", "").strip()
        end_date = request.args.get("end_date", "").strip()
        sort_by = request.args.get("sort_by", "date").strip().lower()
        order = request.args.get("order", "desc").strip().lower()

        try:
            limit = min(int(request.args.get("limit", 200)), 1000)
            offset = max(int(request.args.get("offset", 0)), 0)
        except ValueError:
            limit = 200
            offset = 0

        # Whitelist valid sort columns to prevent SQL injection
        sort_column_map = {
            "date": "date",
            "amount": "amount",
            "title": "title",
            "id": "id",
            "category": "category"
        }
        sort_col = sort_column_map.get(sort_by, "date")
        sort_dir = "ASC" if order == "asc" else "DESC"

        conditions = []
        params = []

        if category and category.lower() != "all":
            conditions.append("LOWER(category) = LOWER(?)")
            params.append(category)

        if search:
            conditions.append("(title LIKE ? OR notes LIKE ?)")
            params.append(f"%{search}%")
            params.append(f"%{search}%")

        if start_date and ISO_DATE_REGEX.match(start_date):
            conditions.append("date >= ?")
            params.append(start_date)

        if end_date and ISO_DATE_REGEX.match(end_date):
            conditions.append("date <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM expenses {where_clause} ORDER BY {sort_col} {sort_dir}, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = get_db(db_path)
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows]), 200

    # READ: Get single expense
    @app.get("/api/expenses/<int:expense_id>")
    def get_expense(expense_id: int):
        conn = get_db(db_path)
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if not row:
            return jsonify(error="Expense not found"), 404
        return jsonify(dict(row)), 200

    # CREATE: Add a new expense
    @app.post("/api/expenses")
    def add_expense():
        data = request.get_json(silent=True) or {}
        validated, err = validate_expense_payload(data)
        if err:
            return jsonify(error=err), 400

        conn = get_db(db_path)
        cursor = conn.execute(
            "INSERT INTO expenses (title, amount, category, date, notes) VALUES (?, ?, ?, ?, ?)",
            (validated["title"], validated["amount"], validated["category"], validated["date"], validated["notes"])
        )
        conn.commit()
        new_id = cursor.lastrowid
        logger.info("Added expense ID %s: %s (Rs %s)", new_id, validated["title"], validated["amount"])
        return jsonify(
            message="Expense added successfully",
            expense={
                "id": new_id,
                **validated
            }
        ), 201

    # UPDATE: Update an existing expense
    @app.put("/api/expenses/<int:expense_id>")
    def update_expense(expense_id: int):
        conn = get_db(db_path)
        existing = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if not existing:
            return jsonify(error="Expense not found"), 404

        data = request.get_json(silent=True) or {}
        validated, err = validate_expense_payload(data)
        if err:
            return jsonify(error=err), 400

        conn.execute(
            """UPDATE expenses
               SET title = ?, amount = ?, category = ?, date = ?, notes = ?
               WHERE id = ?""",
            (validated["title"], validated["amount"], validated["category"], validated["date"], validated["notes"], expense_id)
        )
        conn.commit()
        logger.info("Updated expense ID %s", expense_id)
        return jsonify(
            message="Expense updated successfully",
            expense={"id": expense_id, **validated}
        ), 200

    # DELETE: Remove an expense by its ID
    @app.delete("/api/expenses/<int:expense_id>")
    def delete_expense(expense_id: int):
        conn = get_db(db_path)
        existing = conn.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if not existing:
            return jsonify(error="Expense not found"), 404

        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        logger.info("Deleted expense ID %s", expense_id)
        return jsonify(message="Expense deleted successfully", id=expense_id), 200

    # SUMMARY: Analytical aggregation using Pandas
    @app.get("/api/summary")
    def summary():
        conn = get_db(db_path)
        df = pd.read_sql_query("SELECT * FROM expenses", conn)

        if df.empty:
            return jsonify(
                total=0.0,
                count=0,
                average=0.0,
                by_category={},
                by_category_count={},
                by_month={},
                top_category=None,
                highest_expense=None
            ), 200

        # Data cleaning and enrichment
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        df["month"] = df["date"].astype(str).str.slice(0, 7)  # YYYY-MM

        total_spent = round(float(df["amount"].sum()), 2)
        total_count = int(len(df))
        average_spent = round(float(df["amount"].mean()), 2) if total_count > 0 else 0.0

        # Group by category (Amount and Count)
        cat_group = df.groupby("category")
        by_category_sum = cat_group["amount"].sum().round(2).sort_values(ascending=False)
        by_category_count = cat_group["id"].count().sort_values(ascending=False)

        # Group by month chronologically
        by_month = df.groupby("month")["amount"].sum().round(2).sort_index()

        top_category = str(by_category_sum.idxmax()) if not by_category_sum.empty else None

        # Highest expense record
        max_idx = df["amount"].idxmax()
        highest_row = df.loc[max_idx]
        highest_expense = {
            "id": int(highest_row["id"]),
            "title": str(highest_row["title"]),
            "amount": round(float(highest_row["amount"]), 2),
            "category": str(highest_row["category"]),
            "date": str(highest_row["date"])
        }

        return jsonify(
            total=total_spent,
            count=total_count,
            average=average_spent,
            by_category=by_category_sum.to_dict(),
            by_category_count=by_category_count.to_dict(),
            by_month=by_month.to_dict(),
            top_category=top_category,
            highest_expense=highest_expense
        ), 200

    # CSV EXPORT: Download expenses as standard spreadsheet CSV
    @app.get("/api/expenses/export")
    def export_csv():
        conn = get_db(db_path)
        rows = conn.execute("SELECT date, title, category, amount, notes FROM expenses ORDER BY date DESC, id DESC").fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Title", "Category", "Amount", "Notes"])
        for r in rows:
            writer.writerow([r["date"], r["title"], r["category"], f"{r['amount']:.2f}", r["notes"] or ""])

        csv_content = output.getvalue()
        output.close()

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"expenses_export_{timestamp}.csv"

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # Generic Error Handlers for API
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request"), 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Resource not found"), 404
        return render_template("index.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("Internal Server Error: %s", e)
        return jsonify(error="Internal server error occurred"), 500

    return app


# Default application instance for WSGI runners and development
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
