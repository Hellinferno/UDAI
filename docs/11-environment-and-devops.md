# 11 — Environment & DevOps
## AI Investment Banking Analyst Agent (AIBAA)

---

## 1. Overview

This document covers all environment configurations, tooling, local development setup, and deployment procedures for AIBAA. Since v1 runs locally + Google Colab, there is no cloud infrastructure to configure — but the setup must be deterministic and repeatable.

---

## 2. Development Environments

| Environment | Purpose | Infrastructure |
|---|---|---|
| `local` | Daily development + testing | Local machine + Colab |
| `colab` | LLM inference | Google Colab (T4/A100 GPU) |
| `staging` (v2) | Pre-production testing | TBD (Render / Railway) |
| `production` (v3) | Live user deployment | TBD (AWS / GCP) |

---

## 3. System Requirements

### Developer Machine
| Component | Minimum | Recommended |
|---|---|---|
| OS | macOS 13 / Ubuntu 22.04 / Windows 11 + WSL2 | macOS 14 / Ubuntu 24.04 |
| RAM | 8 GB | 16 GB |
| Disk | 10 GB free | 20 GB free |
| Python | 3.11+ | 3.11.6 |
| Node.js | 18+ | 20 LTS |
| pnpm | 8+ | 8.11.0 |
| Git | 2.40+ | Latest |

### Google Colab
| Component | Free Tier | Pro Tier (Recommended) |
|---|---|---|
| GPU | NVIDIA T4 (15 GB VRAM) | NVIDIA A100 (40 GB VRAM) |
| RAM | 12 GB | 25 GB |
| Storage | 100 GB (ephemeral) | 100 GB |
| Session Limit | ~12 hours | ~24 hours |

> **Recommendation:** Colab Pro ($10/month) is strongly recommended for running Llama-3-8B with Unsloth. Free tier may experience OOM errors.

---

## 4. Local Development Setup

### 4.1 One-Time Setup

```bash
# Clone the repository
git clone https://github.com/your-org/aibaa.git
cd aibaa

# Copy environment variables
cp .env.example .env
# Edit .env with your values (see section 5 below)

# Install Python dependencies (backend)
cd apps/api
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install Node dependencies (frontend)
cd ../../apps/web
npm install -g pnpm             # if not already installed
pnpm install

# Return to root
cd ../..
```

### 4.2 Starting the Full Stack

**Terminal 1 — Backend:**
```bash
cd apps/api
source venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd apps/web
pnpm dev
# App available at http://localhost:3000
```

**Terminal 3 — Colab (via browser):**
1. Open `colab/notebooks/03_start_inference_server.ipynb` in Google Colab
2. Run all cells
3. Copy the ngrok URL output (e.g., `https://abc123.ngrok.io`)
4. Paste into `apps/api/.env` as `LLM_ENDPOINT_URL`
5. Or: update via the Settings page in the UI

---

## 5. Environment Variables

### `apps/api/.env`

```bash
# ============================================================
# AIBAA — Backend Environment Variables
# ============================================================

# Application
APP_ENV=local
APP_PORT=8000
APP_HOST=0.0.0.0
LOG_LEVEL=INFO

# LLM Inference (Colab)
LLM_ENDPOINT_URL=https://abc123.ngrok.io    # Update after each Colab session
LLM_MODEL_NAME=llama3-8b-ib-analyst
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.2
LLM_REQUEST_TIMEOUT_SECONDS=300             # 5 minutes max

# File Storage
UPLOAD_DIR=./uploads                         # Local directory for uploaded files
OUTPUT_DIR=./outputs                         # Local directory for generated files
MAX_UPLOAD_SIZE_MB=50

# Agent Settings
HALLUCINATION_GUARD_ENABLED=true
AGENT_MAX_RETRIES=2
AGENT_STEP_TIMEOUT_SECONDS=60

# Security (v1 — no auth)
# AUTH_SECRET=  (deferred to v2)

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### `apps/web/.env`

```bash
# ============================================================
# AIBAA — Frontend Environment Variables
# ============================================================

VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=AIBAA
VITE_APP_VERSION=1.0.0
VITE_DISCLAIMER_TEXT=This document is an AI-generated draft for informational purposes only and does not constitute financial, legal, or investment advice.
```

### `.env.example` (committed to repo)

```bash
# Copy this file to apps/api/.env and apps/web/.env
# Fill in your values

# Backend
APP_ENV=local
LLM_ENDPOINT_URL=https://your-ngrok-url.ngrok.io
LLM_MODEL_NAME=llama3-8b-ib-analyst
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

> `.env` files are in `.gitignore`. Never commit real values.

---

## 6. Google Colab Setup

### 6.1 Colab Notebook: Environment Setup (`01_environment_setup.ipynb`)

```python
# Cell 1: Install dependencies
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install fastapi uvicorn pyngrok nest-asyncio

# Cell 2: Verify GPU
import torch
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
```

### 6.2 Colab Notebook: Load Model (`02_load_model.ipynb`)

```python
# Cell 1: Load model with Unsloth 4-bit quantization
from unsloth import FastLanguageModel
import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Meta-Llama-3-8B-Instruct",  # Base model
    # OR: your fine-tuned LoRA model path after training
    max_seq_length = 4096,
    dtype = None,          # Auto-detect: float16 on T4, bfloat16 on A100
    load_in_4bit = True,   # Reduces VRAM from ~16GB to ~6GB
)

FastLanguageModel.for_inference(model)
print("Model loaded successfully!")
```

### 6.3 Colab Notebook: Start Inference Server (`03_start_inference_server.ipynb`)

```python
# Cell 1: Import and configure
import nest_asyncio
nest_asyncio.apply()

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from pyngrok import ngrok

app = FastAPI()

class GenerateRequest(BaseModel):
    prompt: str
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.2

@app.get("/health")
def health():
    return {"status": "healthy", "model_loaded": True, "model_name": "llama3-8b-ib-analyst"}

@app.post("/generate")
async def generate(request: GenerateRequest):
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            do_sample=True,
        )
    
    completion = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    
    return {
        "completion": completion,
        "tokens_used": {
            "prompt": inputs.input_ids.shape[1],
            "completion": len(outputs[0]) - inputs.input_ids.shape[1],
            "total": len(outputs[0])
        },
        "model": "llama3-8b-ib-analyst"
    }

# Cell 2: Start ngrok + uvicorn
ngrok_tunnel = ngrok.connect(8001)
print(f"\n🚀 Inference server live at: {ngrok_tunnel.public_url}")
print("📋 Copy this URL into your .env as LLM_ENDPOINT_URL\n")

uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

## 7. Makefile Commands

```makefile
# Root Makefile
.PHONY: help install dev test lint clean

help:
	@echo "AIBAA Development Commands"
	@echo "  make install    — Install all dependencies"
	@echo "  make dev        — Start backend + frontend in dev mode"
	@echo "  make test       — Run all tests"
	@echo "  make lint       — Run all linters"
	@echo "  make clean      — Remove build artifacts and temp files"

install:
	cd apps/api && pip install -r requirements.txt -r requirements-dev.txt
	cd apps/web && pnpm install

dev-backend:
	cd apps/api && source venv/bin/activate && uvicorn src.main:app --reload --port 8000

dev-frontend:
	cd apps/web && pnpm dev

test:
	cd apps/api && pytest tests/ -v --cov=src --cov-report=term-missing
	cd apps/web && pnpm test

lint:
	cd apps/api && ruff check . && ruff format --check .
	cd apps/web && pnpm lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf apps/api/uploads/* apps/api/outputs/*
	cd apps/web && rm -rf dist node_modules/.cache
```

---

## 8. CI/CD Pipeline (v1 — Local Only)

Since v1 is deployed locally (no cloud hosting), CI/CD is limited to **pre-commit hooks** and **GitHub Actions** (for automated testing on push).

### 8.1 Pre-Commit Hooks (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.55.0
    hooks:
      - id: eslint
        files: \.[jt]sx?$
        types: [file]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-json
      - id: check-yaml
      - id: no-commit-to-branch
        args: [--branch, main]
```

### 8.2 GitHub Actions (`.github/workflows/test.yml`)

```yaml
name: Test Suite

on:
  push:
    branches: [main, develop, 'feat/*']
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd apps/api
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Lint
        run: cd apps/api && ruff check .
      - name: Test
        run: cd apps/api && pytest tests/ -v --cov=src --cov-fail-under=75

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install pnpm
        run: npm install -g pnpm
      - name: Install dependencies
        run: cd apps/web && pnpm install
      - name: Lint
        run: cd apps/web && pnpm lint
      - name: Test
        run: cd apps/web && pnpm test -- --run
```

---

## 9. Directory Cleanup Policy

Because v1 stores files locally, a cleanup script prevents disk exhaustion:

```python
# apps/api/src/utils/cleanup.py
import os
import time
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
MAX_AGE_HOURS = 24  # Clean files older than 24 hours

def cleanup_old_files():
    """Remove uploaded and output files older than MAX_AGE_HOURS."""
    now = time.time()
    cutoff = now - (MAX_AGE_HOURS * 3600)
    
    cleaned = 0
    for directory in [UPLOAD_DIR, OUTPUT_DIR]:
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                cleaned += 1
    
    return cleaned
```

---

## 10. Logging Configuration

```python
# apps/api/src/utils/logging_config.py
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

# Usage: Every agent run logs at INFO level
# Reasoning steps: DEBUG level
# Errors: ERROR level with full traceback
```

---

*End of Document — 11-environment-and-devops.md*
