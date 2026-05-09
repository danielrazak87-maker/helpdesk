"""
WSGI entry point for the Helpdesk application.

Used by gunicorn (production) and compatible with any WSGI server.

Usage:
    gunicorn wsgi:application

    # With explicit module path from the helpdesk/ directory:
    gunicorn wsgi:application --bind 0.0.0.0:8000 --workers 4

    # Or via the startup script:
    ./start.sh
"""

import os
import sys

# Ensure the project root is on the path so 'from app import create_app' works.
_project_dir = os.path.dirname(os.path.abspath(__file__))
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

from app import create_app

application = create_app()
