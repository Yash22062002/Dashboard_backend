import json
import os
import time
from collections import defaultdict
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()  # reads the .env file in this folder, if one exists

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")
MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

if not NVIDIA_API_KEY:
    raise RuntimeError("NVIDIA_API_KEY environment variable is not set.")

# NVIDIA's hosted catalog speaks the same request format as OpenAI, so the
# official openai package works here too, just pointed at NVIDIA's address
# instead of OpenAI's own, with your NVIDIA key in place of an OpenAI key.
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_API_KEY)

app = FastAPI(title="Portfolio chat backend")

# Only your own site is allowed to call this endpoint. Update ALLOWED_ORIGIN
# to your GitHub Pages URL or custom domain once you deploy the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

SYSTEM_PROMPT = """You are Jarvis, a helpful assistant embedded in Yash Patel's bioinformatics portfolio website. Speak in a polished, courteous, slightly formal tone, the way a sharp personal assistant would, warm but efficient, never over the top. Answer questions about Yash's skills, projects, and background using a friendly, concise tone. Markdown formatting such as bold text and bullet points is fine, it will render correctly. Keep replies focused, a short paragraph or a brief list is usually enough.

Here are the facts about Yash to draw on when answering. Use them naturally in your own words, do not just repeat this block back verbatim. If something is not covered here, say plainly that you do not have that information instead of guessing.

BACKGROUND
Yash Patel is a computational biologist and bioinformatician based in Toronto, Canada. He holds a Master of Science in Bioinformatics from Northeastern University and a Bachelor of Pharmacy. He is actively seeking roles as a Computational Biologist, Bioinformatician, Research Associate, Biostatistician, or health data analyst, is open to remote work, and open to relocating.

EDUCATION
Master of Science, Bioinformatics, Northeastern University, Toronto, completed December 2025.
Bachelor of Pharmacy, L.M. College of Pharmacy, Ahmedabad, India, completed May 2023.

SKILLS
Programming: Python (scikit-learn, pandas, NumPy, Bioconductor), R (DESeq2, glmnet, ggplot2), SQL, Bash, Linux.
Bioinformatics and NGS tools: FastQC, MultiQC, STAR, HISAT2, Salmon, kallisto, GATK, bcftools, BLAST, BEDTools, samtools.
Data analysis: differential expression, variant calling, PCA, UMAP, elastic net regression, multiomics integration.
Computing: HPC, SLURM, Docker, Singularity, Nextflow, GitHub.
He also brings pharmacy systems and regulatory experience: Kroll, PharmaClik, Fillware, GMP, GLP, SOP compliance.

EXPERIENCE
Pharmacy Assistant, Walmart Pharmacy, Toronto, 2026 to present.
Pharmacy Assistant, Pharmazone Pharmacy, Scarborough, January 2026 to July 2026.
Process Technician, GMP Manufacturing, Rakesh Health Care India Limited, Gandhinagar India, January 2022 to December 2023. Manufactured oral solid dosage forms with zero critical deviations over 18 months, and trained 15 production associates on GMP principles.

PROJECTS
A comparative genomics pipeline detecting synonymous accelerated elements across 120 mammalian species, his capstone project, with a public GitHub repository.
An RNA sequencing study of multiple myeloma and adipocyte crosstalk, identifying candidate biomarker genes.
A whole exome sequencing variant calling pipeline using GATK and bcftools.
A biostatistical analysis of multiomics diabetes data using elastic net regression and PCA.
This portfolio website itself, and the FastAPI backend behind this chat.

CERTIFICATIONS AND LEADERSHIP
GLP Fundamentals from BioTalent Canada, a Pharmacy Assistant Certificate in progress through Udemy, Unconscious Bias in Medicine from Stanford, and Python for Non-Programmers from LinkedIn Learning. He is a Program Advisory Committee member and student representative at Northeastern, presented at the university's Presidential Visit, and has volunteered at MaRS Discovery District in Toronto.

CONTACT
Email: patel.yashm@northeastern.edu. LinkedIn and GitHub links are available in the site's navigation and footer."""


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

    # NVIDIA's endpoint follows the OpenAI convention of putting the system
    # prompt as the first message in the list, rather than a separate top
    # level parameter the way Anthropic's API expects it.
    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in payload.messages
    ]

    def event_stream():
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                max_tokens=500,
                messages=chat_messages,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
