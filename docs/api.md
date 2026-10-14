---
title: API reference
nav_order: 5
---

# API reference
{: .no_toc }

All routes are under `/api`. When the backend is running, interactive docs are served at <http://localhost:8000/docs>.
{: .fs-5 .fw-300 }

1. TOC
{:toc}

---

## `POST /api/chat-stream`

Sends one prompt to the selected models and streams their results.

```json
{ "prompt": "Explain attention in two sentences.", "models": ["GPT 4o", "Gemini 2.5 Pro"] }
```

`models` is optional; when it is omitted, the models in `ENABLED_MODELS` are used, or every model if that is unset. An empty `prompt` returns `400`.

The response is `application/x-ndjson`, one event per line:

```json
{"event": "start", "count_prompts": 1, "models": ["GPT 4o", "Gemini 2.5 Pro"]}
{"event": "progress", "model": "GPT 4o", "prompt_index": 0, "prompt": "…", "status": "started"}
{"event": "result", "model": "GPT 4o", "prompt_index": 0, "prompt": "…", "response": "…", "error": null, "duration_ms": 2140}
{"event": "end"}
```

Every selected model produces exactly one `result`: `error` is `null` on success, and `response` is empty on failure. `prompt_index` is the turn number in that model's conversation, starting at `0`.

| Event | Fields | When |
|---|---|---|
| `start` | `count_prompts`, `models` | Once, before any model is called |
| `progress` | `model`, `prompt_index`, `prompt`, `status` | When a model's call starts |
| `result` | `model`, `prompt_index`, `prompt`, `response`, `error`, `duration_ms` | When a model finishes or fails |
| `end` | none | Once, after every model has reported its `result` |

## `POST /api/reset-memory`

```json
{ "models": ["GPT 4o"] }
```

Clears those models' conversation history. Omit `models` to clear all.

## `POST /api/remove-models`

```json
{ "models": ["Nova Premier"] }
```

Drops those models' history and marks them unused, so they start fresh if selected again.
