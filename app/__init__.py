"""Network Interface Intelligence Platform — application package.

The Flask `create_app` factory lives in `app.factory` and is re-exported
here lazily so that submodules (the ML engines, the CLI, the data
loaders) can be imported without pulling in Flask, flask-cors, and the
rest of the web stack.
"""

from __future__ import annotations

__version__ = "1.0.0"


def create_app(*args, **kwargs):
    """Lazy proxy to `app.factory.create_app`."""
    from app.factory import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["create_app", "__version__"]
