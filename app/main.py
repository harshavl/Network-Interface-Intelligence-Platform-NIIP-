"""
Application entry point.

Usage:
    python -m app.main

For production, prefer gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
"""

from app import create_app
from app.core import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    app.run(
        host=settings.host,
        port=settings.port,
        debug=settings.flask_debug,
        use_reloader=settings.flask_debug,
    )


if __name__ == "__main__":
    main()
