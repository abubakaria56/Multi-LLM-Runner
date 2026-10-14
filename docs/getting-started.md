---
title: Getting started
nav_order: 2
---

# Getting started
{: .no_toc }

1. TOC
{:toc}

---

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- An [OpenRouter API key](https://openrouter.ai/keys)

## Get the code

```bash
git clone https://github.com/abubakaria56/Multi-LLM-Runner.git
cd Multi-LLM-Runner
```

## 1. Start the backend

```bash
cd backend
cp .env.example .env          # set OPENROUTER_API_KEY
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Interactive API docs are served at <http://localhost:8000/docs>.

## 2. Start the frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

To type-check and build for production, run `npm run build`.

## 3. Run a prompt

Open <http://localhost:5173>, select models (or none, to run them all), type a prompt and press **Run**.

Each model's answer appears in its own column as soon as that model finishes, with its response time. Follow-up prompts continue each model's own conversation; **Reset memory** clears it.

Next, see [Configuration]({% link configuration.md %}) to choose a provider and the default models.
