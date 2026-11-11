"""FastAPI page listing AoE2 HD lobbies.

Run:  uv run uvicorn app:app --port 8000
"""
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aoe2lobby.lobby_info import describe

ROOT = Path(__file__).resolve().parent
LOBBIES = ROOT / "data" / "lobbies.json"


@asynccontextmanager
async def lifespan(_: FastAPI):
    proc = None
    if os.environ.get("AOE_START_COLLECTOR", "1") == "1":
        proc = subprocess.Popen([sys.executable, str(ROOT / "collector.py")], cwd=ROOT)
    try:
        yield
    finally:
        if proc and proc.poll() is None:
            proc.terminate()


app = FastAPI(title="AoE2 HD Lobbies", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/api/lobbies")
def lobbies():
    try:
        data = json.loads(LOBBIES.read_text(encoding="utf-8"))
        data["lobbies"] = sorted((describe(l) for l in data.get("lobbies", [])),
                                 key=lambda l: l["title"].lower())
        return JSONResponse(data)
    except FileNotFoundError:
        return JSONResponse({"updated": None, "error": "Waiting for first lobby list…", "lobbies": []})


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
