"""Automated Test Suite for Expense Tracker Web Application.
Tests API endpoints, validations, database isolation, and analytics calculations.
"""

import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def app_instance():
    """Create a temporary test database and configured Flask test application."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": db_path,
        "SECRET_KEY": "test-secret-key"
    })

    yield app

    os.close(db_fd)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture
def client(app_instance):
    """Return a Flask test client."""
    return app_instance.test_client()


def test_health_check(client):
    """Verify production health check returns healthy status code 200."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
    assert "timestamp" in data


def test_home_page(client):
    """Verify home page loads successfully with HTML content."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"ExpenseFlow" in res.data
    assert b"<!DOCTYPE html>" in res.data


def test_security_headers(client):
    """Verify critical HTTP security headers are present in response."""
    res = client.get("/")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in res.headers.get("Referrer-Policy")


def test_empty_summary(client):
    """Verify summary returns zeroes and empty structures on clean database."""
    res = client.get("/api/summary")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 0.0
    assert data["count"] == 0
    assert data["average"] == 0.0
    assert data["by_category"] == {}
    assert data["top_category"] is None


def test_add_expense_success(client):
    """Verify creating a valid expense returns 201 Created and saves data."""
    payload = {
        "title": "Groceries at supermarket",
        "amount": 1450.50,
        "category": "Food",
        "date": "2026-09-28",
        "notes": "Weekly produce and snacks"
    }
    res = client.post("/api/expenses", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["message"] == "Expense added successfully"
    assert data["expense"]["title"] == "Groceries at supermarket"
    assert data["expense"]["amount"] == 1450.50
    assert data["expense"]["category"] == "Food"
    assert data["expense"]["date"] == "2026-09-28"
    assert data["expense"]["notes"] == "Weekly produce and snacks"
    assert "id" in data["expense"]


@pytest.mark.parametrize("invalid_payload,expected_err", [
    ({"title": "", "amount": 100, "category": "Food", "date": "2026-09-28"}, "Title is required"),
    ({"title": "Test", "amount": 0, "category": "Food", "date": "2026-09-28"}, "Amount must be greater than 0"),
    ({"title": "Test", "amount": -50, "category": "Food", "date": "2026-09-28"}, "Amount must be greater than 0"),
    ({"title": "Test", "amount": "abc", "category": "Food", "date": "2026-09-28"}, "Amount must be a valid number"),
    ({"title": "Test", "amount": 100, "category": "", "date": "2026-09-28"}, "Category is required"),
    ({"title": "Test", "amount": 100, "category": "Food", "date": "invalid-date"}, "Date is required and must follow YYYY-MM-DD format"),
])
def test_add_expense_validation_errors(client, invalid_payload, expected_err):
    """Verify input validation handles invalid fields with status 400."""
    res = client.post("/api/expenses", json=invalid_payload)
    assert res.status_code == 400
    data = res.get_json()
    assert expected_err in data["error"]


def test_update_expense(client):
    """Verify PUT updates an existing expense record."""
    # Create
    create_res = client.post("/api/expenses", json={
        "title": "Train Ticket",
        "amount": 420.0,
        "category": "Travel",
        "date": "2026-09-28",
        "notes": "Initial booking"
    })
    expense_id = create_res.get_json()["expense"]["id"]

    # Update
    update_res = client.put(f"/api/expenses/{expense_id}", json={
        "title": "Express Train Ticket",
        "amount": 550.0,
        "category": "Travel",
        "date": "2026-09-29",
        "notes": "Upgraded to AC tier"
    })
    assert update_res.status_code == 200
    updated_data = update_res.get_json()["expense"]
    assert updated_data["title"] == "Express Train Ticket"
    assert updated_data["amount"] == 550.0

    # Retrieve and verify persistence
    get_res = client.get(f"/api/expenses/{expense_id}")
    assert get_res.status_code == 200
    assert get_res.get_json()["title"] == "Express Train Ticket"


def test_update_nonexistent_expense(client):
    """Verify updating a non-existent expense returns 404."""
    res = client.put("/api/expenses/9999", json={
        "title": "Non-existent",
        "amount": 10.0,
        "category": "Other",
        "date": "2026-09-28"
    })
    assert res.status_code == 404


def test_delete_expense(client):
    """Verify deleting an expense removes it from database."""
    create_res = client.post("/api/expenses", json={
        "title": "Coffee",
        "amount": 150.0,
        "category": "Food",
        "date": "2026-09-28"
    })
    expense_id = create_res.get_json()["expense"]["id"]

    del_res = client.delete(f"/api/expenses/{expense_id}")
    assert del_res.status_code == 200

    get_res = client.get(f"/api/expenses/{expense_id}")
    assert get_res.status_code == 404


def test_filtering_and_search(client):
    """Verify list_expenses endpoint correctly filters by category and search keyword."""
    client.post("/api/expenses", json={"title": "Flight to Delhi", "amount": 5000, "category": "Travel", "date": "2026-09-20"})
    client.post("/api/expenses", json={"title": "Team Dinner", "amount": 2500, "category": "Food", "date": "2026-09-22"})
    client.post("/api/expenses", json={"title": "Hotel Stay Delhi", "amount": 4000, "category": "Travel", "date": "2026-09-21"})

    # Search filter
    search_res = client.get("/api/expenses?search=Delhi")
    assert search_res.status_code == 200
    search_items = search_res.get_json()
    assert len(search_items) == 2

    # Category filter
    cat_res = client.get("/api/expenses?category=Food")
    assert cat_res.status_code == 200
    cat_items = cat_res.get_json()
    assert len(cat_items) == 1
    assert cat_items[0]["title"] == "Team Dinner"


def test_pandas_summary_analytics(client):
    """Verify Pandas statistical aggregation computes totals, averages, and group sums."""
    client.post("/api/expenses", json={"title": "Dinner", "amount": 1000, "category": "Food", "date": "2026-08-15"})
    client.post("/api/expenses", json={"title": "Groceries", "amount": 2000, "category": "Food", "date": "2026-09-10"})
    client.post("/api/expenses", json={"title": "Gas Bill", "amount": 3000, "category": "Bills", "date": "2026-09-15"})

    res = client.get("/api/summary")
    assert res.status_code == 200
    s = res.get_json()

    assert s["total"] == 6000.0
    assert s["count"] == 3
    assert s["average"] == 2000.0
    assert s["by_category"]["Food"] == 3000.0
    assert s["by_category"]["Bills"] == 3000.0
    assert s["by_month"]["2026-08"] == 1000.0
    assert s["by_month"]["2026-09"] == 5000.0
    assert s["highest_expense"]["amount"] == 3000.0
    assert s["highest_expense"]["title"] == "Gas Bill"


def test_export_csv(client):
    """Verify CSV export endpoint serves valid formatted CSV file."""
    client.post("/api/expenses", json={
        "title": "Book purchase",
        "amount": 799.0,
        "category": "Study",
        "date": "2026-09-25",
        "notes": "Data science handbook"
    })

    res = client.get("/api/expenses/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("Content-Type")
    assert "attachment; filename=" in res.headers.get("Content-Disposition")
    text = res.data.decode("utf-8")
    assert "Date,Title,Category,Amount,Notes" in text
    assert "Book purchase" in text
    assert "799.00" in text
