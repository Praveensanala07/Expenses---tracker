# Expense Tracker (Full Stack + Data Summary)

A simple web app to record daily expenses, delete them, and see where your money goes.

## Tech stack
Python, Flask (backend REST API), SQLite (SQL database), Pandas (data summary), HTML, CSS, JavaScript (frontend)

## How to run
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## How it works (in simple words)
1. You fill the form in the browser. JavaScript sends the data to the Flask server (a POST request).
2. Flask checks the data (amount must be a number above 0, no empty fields) and saves it in SQLite.
3. The page asks the server for all expenses (GET) and shows them in a table.
4. For the summary, Pandas reads the table, groups it by category and month, and adds up the amounts.
5. Delete sends a DELETE request for that expense id.

## API
| Method | Endpoint | What it does |
|---|---|---|
| GET | `/api/expenses` | List all expenses |
| POST | `/api/expenses` | Add an expense |
| DELETE | `/api/expenses/<id>` | Delete an expense |
| GET | `/api/summary` | Totals by category and month (Pandas) |

## Files
- `app.py`: backend, database and API
- `templates/index.html`: the web page
- `requirements.txt`: libraries to install

## Ideas to extend
Edit expenses, monthly budget alerts, user login, export to CSV, deploy on Render or Railway.
