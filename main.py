import os
import time
from collections import defaultdict
from typing import List

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
    "You are a helpful assistant embedded in Yash Patel's bioinformatics "
    "portfolio website. Answer questions about his skills, projects, and "
    "background using a friendly, concise tone. Reply in plain conversational "
    "sentences only, do not use markdown formatting such as asterisks, bullet "
    "points, or headers, since your replies are shown in a small chat bubble, "
    "not a formatted document. Keep replies to two or three sentences unless "
    "the visitor clearly wants more detail. If you do not know an answer, say "
    "so plainly instead of guessing."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


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


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": m.role, "content": m.content} for m in payload.messages],
        )
        reply_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

    return ChatResponse(reply=reply_text)


@app.get("/health")
async def health():
    return {"status": "ok"}
