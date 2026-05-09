"""
Development runner (Flask built-in dev server).

For production, use gunicorn via:
    ./start.sh              # foreground
    ./start.sh --daemon     # background daemon
    systemctl start helpdesk  # systemd service
"""

import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    if not debug:
        import warnings
        warnings.warn(
            "Running Flask dev server with FLASK_ENV=production. "
            "Use './start.sh' or 'systemctl start helpdesk' for production.",
            RuntimeWarning
        )
    app.run(debug=debug, host='0.0.0.0', port=5000)
