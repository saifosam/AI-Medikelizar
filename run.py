"""
AI-Medikelizar — Single-command launcher
=========================================
Run the entire project (backend API + frontend) with one command:

    python run.py

Opens http://localhost:8000 in your browser automatically.
"""

import os
import webbrowser

import uvicorn
from backend.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print()
    print("  +------------------------------------------------+")
    print("  |        AI-Medikelizar -- Starting Up           |")
    print("  +------------------------------------------------+")
    print(f"  |  Open:  http://localhost:{port}                   |")
    print(f"  |  Press Ctrl+C to stop                        |")
    print("  +------------------------------------------------+")
    print()

    # Auto-open browser
    webbrowser.open(f"http://localhost:{port}", autoraise=False)

    # Start the server
    uvicorn.run(app, host=host, port=port, reload=True)
