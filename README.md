# Portfolio chat backend

A small FastAPI service with one endpoint, `/chat`, that holds your Claude
API key on the server and forwards messages from the floating widget to the
Claude API. This exists because GitHub Pages only serves static files and
cannot hold a secret, so the key can never live in the React app itself.

## Run it locally

Do these one at a time, not as one pasted block, step 4 is you actually
opening a file and typing into it, not a terminal command.

1. Move into the folder and create a virtual environment.
   ```bash
   cd backend
   python -m venv venv
   ```
2. Activate it. The command differs by OS.

   macOS or Linux:
   ```bash
   source venv/bin/activate
   ```
   Windows, Command Prompt:
   ```bash
   venv\Scripts\activate.bat
   ```
   Windows, PowerShell:
   ```bash
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   venv\Scripts\Activate.ps1
   ```
   Your terminal prompt should now start with `(venv)`, that's your
   confirmation it worked.
3. Install the dependencies.
   ```bash
   pip install -r requirements.txt
   ```
4. Create your real config file and edit it.
   ```bash
   cp .env.example .env
   ```
   Open `.env` in your editor and replace the placeholder with your real
   Anthropic key, then save the file. The app loads this automatically,
   no extra terminal step needed for that part.
5. Start the server.
   ```bash
   uvicorn main:app --reload --port 8000
   ```

If it starts without an error about a missing `ANTHROPIC_API_KEY`, it
worked. Leave this terminal window open and running, it needs to stay
active while you test.

Test it from a second terminal window, without closing the first:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What does Yash work on?"}]}'
```

If that returns a reply, the backend is working end to end.

## Deploy it to Render, free tier

1. Push the `backend` folder to its own GitHub repository (a separate repo
   from your portfolio frontend keeps deploys independent).
2. In the Render dashboard, choose New, Web Service, and connect that repo.
3. Render will detect `render.yaml`. Confirm the build command
   `pip install -r requirements.txt` and start command
   `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Under Environment, add `ANTHROPIC_API_KEY` as a secret value, and set
   `ALLOWED_ORIGIN` to your future GitHub Pages URL, for example
   `https://yourusername.github.io`.
5. Deploy. Render gives you a URL like
   `https://portfolio-chat-backend.onrender.com`.
6. Test the deployed endpoint the same way as above, swapping in that URL.
7. Put that URL into your frontend's `VITE_CHAT_API_URL`.

Free tier services on Render spin down after inactivity, so the first
message after a quiet period can take a few seconds while it wakes up.
That is expected, not a bug.

## Alternatives to Render

Railway and Fly.io both work the same way: a Python web service, one
environment variable for the API key, one for the allowed origin. Pick
whichever you find easiest to navigate, the code here does not change.

## Optional, keeping the service from spinning down

Render's free tier spins a web service down after 15 minutes without
traffic, and spins it back up on the very next plain HTTP request, no real
browser session required, unlike Streamlit Community Cloud. If you want
this backend to always respond instantly instead of taking thirty to sixty
seconds on the first message after a quiet stretch, a workflow is already
included at `.github/workflows/keep-awake.yml`. It pings `/health` every
ten minutes using a plain curl request, well under Render's fifteen
minute idle window.

To use it, edit that file and replace the placeholder URL with your real
Render service URL, then push it to this repo. If you'd rather keep
things simple and let the occasional cold start happen, just delete the
file, nothing else depends on it.

Render's free tier includes 750 instance hours per workspace per month,
enough to run one service continuously all month. If you add other free
Render services under the same workspace later, that hour budget is
shared across all of them, worth checking the dashboard occasionally.

## Before you consider this done

- Set a hard spending limit on your Anthropic console. This key is shared
  with your Streamlit dashboard, so a ceiling protects both projects.
- Confirm `ALLOWED_ORIGIN` matches your real deployed frontend URL exactly,
  including `https://` and no trailing slash.
- Watch the Render logs the first day it is live, to catch anything odd
  early.
