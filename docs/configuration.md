---
title: Configuration
nav_order: 4
---

# Configuration

The backend reads its settings from `backend/.env`. The [example file](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/backend/.env.example) has every option in it.

| Variable | What it's for | Default |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` or `kong` sends every model to that provider; `auto` picks per model | `kong` (the example file sets `openrouter`) |
| `OPENROUTER_API_KEY` | Your OpenRouter key | needed for `openrouter` |
| `OPENROUTER_API_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `KONG_API_KEY`, `API_GATEWAY_KEY`, `AUTH_TOKEN` | Kong gateway credentials | needed for `kong` |
| `KONG_API_BASE_URL` | Kong gateway endpoint | needed for `kong` |
| `ENABLED_MODELS` | Comma-separated models to run when none are selected | every model |

The frontend only has one setting, `VITE_API_BASE_URL`, which points it at the backend. It defaults to `http://localhost:8000`.

## Models

The models live in [`backend/app/models/llm_provider.py`](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/backend/app/models/llm_provider.py), in one map per provider. These are the OpenRouter ones:

| Name in the app | OpenRouter ID |
|---|---|
| DeepSeek R1 New | `deepseek/deepseek-r1-0528` |
| DeepSeek R1 | `deepseek/deepseek-r1` |
| Sonnet 3.7 | `anthropic/claude-3.7-sonnet` |
| GPT 4o | `openai/gpt-4o-2024-08-06` |
| Nova Premier | `amazon/nova-premier-v1` |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` |
| Gemini 2.5 Pro | `google/gemini-2.5-pro` |

OpenRouter has retired Claude 3.7 Sonnet, so swap in a current Claude ID if you want a Claude model.

To add a model, put its name and provider ID in those maps, then add the same name to `ALL_MODELS` in [`frontend/src/App.tsx`](https://github.com/abubakaria56/Multi-LLM-Runner/blob/main/frontend/src/App.tsx) so it shows up in the picker.
