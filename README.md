# Portfolio Chat Backend

A small FastAPI service that powers Jarvis, the AI assistant on
[Yash Patel's bioinformatics portfolio](https://yash22062002.github.io/Yashpatel_portfolio/).
It holds the Anthropic API key server side and streams responses back to
the widget, since a static site on GitHub Pages has nowhere secure to
keep a secret.

## How it works

The frontend sends the conversation so far to a single `/chat` endpoint.
This service attaches a system prompt describing Yash's background,
skills, and projects, forwards the request to Claude, and streams the
reply back as it is generated. A per IP rate limiter protects the
endpoint from abuse, and CORS is restricted to the live portfolio's
origin.

## Tech stack

- FastAPI and Uvicorn
- Anthropic's Claude API (Haiku), via the official Python SDK
- Deployed to Render, free tier

## Running it locally

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # add your own Anthropic key
uvicorn main:app --reload --port 8000
```

Test it:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What does Yash work on?"}]}'
```

A successful reply confirms the service is working end to end.

## Deployment

Configuration lives in `render.yaml`; Render reads the build and start
commands from it directly. The only manual step is adding
`ANTHROPIC_API_KEY` as a secret environment variable in the Render
dashboard, since secrets are deliberately never committed to the
repository.

A scheduled GitHub Action (`.github/workflows/keep-awake.yml`) pings the
health endpoint every ten minutes to prevent Render's free tier from
spinning the service down during periods of inactivity. Note that on the
free tier, the first request after a quiet period can still take up to a
minute to respond, that is expected behavior, not a bug.

## Related repositories

- Frontend: [Yashpatel_portfolio](https://github.com/Yash22062002/Yashpatel_portfolio)

Built by [Yash Patel](https://www.linkedin.com/in/yash-patel-network).
