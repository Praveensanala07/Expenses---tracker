"""Expense Tracker: a small full stack app.
Frontend (HTML/JS) <-> Flask REST API <-> SQLite database, plus Pandas for the summary."""
import sqlite3
import pandas as pd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB = "expenses.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  # lets us read rows like dictionaries
    return conn


# Create the table the first time the app starts
with get_db() as conn:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS expenses (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT NOT NULL,
               amount REAL NOT NULL,
               category TEXT NOT NULL,
               date TEXT NOT NULL)"""
    )


@app.get("/")
def home():
    return render_template("index.html")


# READ: get all expenses (newest first)
@app.get("/api/expenses")
def list_expenses():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


# CREATE: add a new expense
@app.post("/api/expenses")
def add_expense():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    category = str(data.get("category", "")).strip()
    date = str(data.get("date", "")).strip()
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify(error="Amount must be a number"), 400

    if not title or not category or not date:
        return jsonify(error="Title, category and date are required"), 400
    if amount <= 0:
        return jsonify(error="Amount must be greater than 0"), 400

    with get_db() as conn:
        conn.execute("INSERT INTO expenses (title, amount, category, date) VALUES (?, ?, ?, ?)",
                     (title, amount, category, date))
    return jsonify(message="Expense added"), 201


# DELETE: remove an expense by its id
@app.delete("/api/expenses/<int:expense_id>")
def delete_expense(expense_id):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return jsonify(message="Deleted")


# SUMMARY: use Pandas to total spending by category and by month
@app.get("/api/summary")
def summary():
    with get_db() as conn:
        df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if df.empty:
        return jsonify(total=0, by_category={}, by_month={}, top_category=None)

    df["month"] = df["date"].str[:7]  # "2026-09-28" -> "2026-09"
    by_category = df.groupby("category")["amount"].sum().round(2).sort_values(ascending=False)
    by_month = df.groupby("month")["amount"].sum().round(2).sort_index()
    return jsonify(total=round(float(df["amount"].sum()), 2),
                   by_category=by_category.to_dict(),
                   by_month=by_month.to_dict(),
                   top_category=by_category.idxmax())


if __name__ == "__main__":
    app.run(debug=True)
