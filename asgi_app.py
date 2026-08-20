"""Streamlit ASGI entry: UI plus /health and /robots.txt for App Service."""

from pathlib import Path

import streamlit as st
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

ROOT = Path(__file__).resolve().parent
ROBOTS_PATH = ROOT / "static" / "robots.txt"
FALLBACK_ROBOTS = "User-agent: *\nAllow: /\n"


async def health(_request):
    return JSONResponse({"status": "ok"})


async def robots(_request):
    if ROBOTS_PATH.is_file():
        return FileResponse(ROBOTS_PATH, media_type="text/plain; charset=utf-8")
    return PlainTextResponse(FALLBACK_ROBOTS, media_type="text/plain")


app = st.App(
    str(ROOT / "app.py"),
    routes=[
        Route("/health", health),
        Route("/robots.txt", robots),
    ],
)
