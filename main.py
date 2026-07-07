import json
import os
import time
from collections import defaultdict
from typing import List

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()  # reads the .env file in this folder, if one exists

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI(title="Portfolio chat backend")

# Only your own site is allowed to call this endpoint. Update ALLOWED_ORIGIN
# to your GitHub Pages URL or custom domain once you deploy the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

SYSTEM_PROMPT = (
    "You are Jarvis, a helpful assistant embedded in Yash Patel's "
    "bioinformatics portfolio website. Speak in a polished, courteous, "
    "slightly formal tone, the way a sharp personal assistant would, warm "
    "but efficient, never over the top. Answer questions about Yash's "
    "skills, projects, and background using a friendly, concise tone. "
    "Markdown formatting such as bold text and bullet points is fine, it "
    "will render correctly. Keep replies focused, a short paragraph or a "
    "brief list is usually enough. If you do not know an answer, say so "
    "plainly instead of guessing."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


# Small in memory rate limiter, per process, per visitor IP. This is fine
# for a personal portfolio. If traffic grows, move this to Redis so it
# works across multiple server instances.
_hits = defaultdict(list)
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 10 * 60


def check_rate_limit(ip: str):
    now = time.time()
    window_start = now - RATE_WINDOW_SECONDS
    _hits[ip] = [t for t in _hits[ip] if t > window_start]
    if len(_hits[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests, please try again later.",
        )
    _hits[ip].append(now)


@app.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    anthropic_messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    def event_stream():
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=anthropic_messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
