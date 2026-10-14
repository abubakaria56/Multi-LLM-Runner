---
title: Configuration
nav_order: 4
---

# Configuration
{: .no_toc }

1. TOC
{:toc}

---

## Backend

Backend settings live in `backend/.env` ([example](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/backend/.env.example)).

| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` or `kong` sends every model to that provider; `auto` routes per model | `kong` |
| `OPENROUTER_API_KEY` | OpenRouter API key | required for `openrouter` |
| `OPENROUTER_API_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `KONG_API_KEY` · `API_GATEWAY_KEY` · `AUTH_TOKEN` | Kong gateway credentials | required for `kong` |
| `KONG_API_BASE_URL` | Kong gateway endpoint | required for `kong` |
| `ENABLED_MODELS` | Comma-separated default models when the client selects none | all models |

## Frontend

The frontend reads `VITE_API_BASE_URL` ([example](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/frontend/.env.example)) and defaults to `http://localhost:8000`.

## Supported models

Models are defined in [`backend/app/models/llm_provider.py`](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/backend/app/models/llm_provider.py), one map per provider.

| Display name | OpenRouter ID |
|---|---|
| DeepSeek R1 New | `deepseek/deepseek-r1-0528` |
| DeepSeek R1 | `deepseek/deepseek-r1` |
| Sonnet 3.7 | `anthropic/claude-3.7-sonnet` *(retired on OpenRouter; swap in a current Claude ID)* |
| GPT 4o | `openai/gpt-4o-2024-08-06` |
| Nova Premier | `amazon/nova-premier-v1` |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` |
| Gemini 2.5 Pro | `google/gemini-2.5-pro` |

## Adding a model

Add its display name and provider ID to the maps in `llm_provider.py`, and to `ALL_MODELS` in [`frontend/src/App.tsx`](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/frontend/src/App.tsx).
