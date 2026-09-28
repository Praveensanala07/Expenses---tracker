"""WSGI Entry point for production servers (Gunicorn, Waitress, uWSGI)."""
import os
import sys
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"Starting production server on http://{host}:{port} via Waitress WSGI...")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=6)
    except ImportError:
        print("Waitress not installed, falling back to standard server.")
        app.run(host=host, port=port, debug=False)
