# -*- coding: utf-8 -*-
"""
AgentShield V3 - FastAPI 主入口
端口：8011

继承 ASF-BGT Framework + V2 AgentBehaviorGraph

The application is built by :func:`app.factory.build_app`, which mounts both
the ``/api/v3/*`` router and the standalone surface (``/api/evaluate`` and
friends).  This file used to define a second, independent FastAPI instance
with its own CORS policy and engine store; it is now just an entry point.
"""

import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.factory import build_app

app = build_app()
