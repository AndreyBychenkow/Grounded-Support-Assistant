"""Веб-демо ассистента: чат + панель «почему бот ответил именно так».

Запуск:  python app.py            (http://0.0.0.0:8000)
         uvicorn app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core.assistant import reply

app = FastAPI(title="Shop Support Assistant — demo")
STATIC = Path(__file__).with_name("static") / "index.html"


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return STATIC.read_text(encoding="utf-8")


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    return reply(payload.message)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
