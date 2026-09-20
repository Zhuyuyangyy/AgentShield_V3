# -*- coding: utf-8 -*-
"""AgentShield V3 - standalone entry point (port 8090).

The application itself lives in :mod:`app.factory` so that this file and
``app/main.py`` build the *same* FastAPI instance -- previously each kept its
own app object, middleware and engine store.

Run with::

    python backend/app.py                 # from the repo root
    uvicorn app.main:app --port 8011      # /api/v3 surface + standalone
"""

from app.factory import build_app

app = build_app()


if __name__ == "__main__":
    import uvicorn

    # Pass the app object directly.  uvicorn.run("app:app") would resolve the
    # string "app" against sys.path, and from inside backend/ that finds the
    # *package* app/ instead of this module -- "Attribute 'app' not found".
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8090,
        reload=False,
        log_level="info",
    )
