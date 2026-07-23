"""
AI-Medikelizar — Single-command launcher
=========================================
Run the entire project (backend API + frontend) with one command:

    python run.py

Opens http://localhost:8000 in your browser automatically.
"""

import os
import sys
import webbrowser

import uvicorn
from backend.main import app

# Reconfigure stdout to UTF-8 on Windows to prevent UnicodeEncodeError
# when printing non-ASCII characters to the terminal.
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Ignore if terminal doesn't support UTF-8

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print()
    print("  +------------------------------------------------+")
    print("  |        AI-Medikelizar -- Starting Up           |")
    print("  +------------------------------------------------+")
    print(f"  |  Open:  http://localhost:{port}                  |")
    print(f"  |  Press Ctrl+C to stop                          |")
    print("  +------------------------------------------------+")
    print()

    # Auto-open browser
    webbrowser.open(f"http://localhost:{port}", autoraise=False)

    # Start the server (string reference needed for reliable reload)
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
