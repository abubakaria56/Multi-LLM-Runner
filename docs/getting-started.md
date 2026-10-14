---
title: Getting started
nav_order: 2
---

# Getting started

You'll need Python 3.11 or newer with [uv](https://docs.astral.sh/uv/), Node.js 20 or newer, and an [OpenRouter API key](https://openrouter.ai/keys).

```bash
git clone https://github.com/abubakaria56/Multi-LLM-Runner.git
cd Multi-LLM-Runner
```

## Backend

Copy the example settings file and paste your OpenRouter key into it. It's already set up to use OpenRouter.

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

FastAPI's interactive docs are then at <http://localhost:8000/docs>, which is a quick way to check the backend is up.

## Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, pick a few models (or leave them all unselected to use every model), type a prompt and click **Run**. Follow-up prompts continue the same conversations, and **Reset memory** starts them over.

To use the Kong gateway instead, or to change which models run by default, see [Configuration]({% link configuration.md %}).
