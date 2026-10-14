---
title: API reference
nav_order: 5
---

# API reference

There are three routes, all under `/api`. With the backend running you can also try them from FastAPI's docs page at <http://localhost:8000/docs>.

## POST /api/chat-stream

Sends a prompt to the chosen models and streams back what happens.

```json
{ "prompt": "Explain attention in two sentences.", "models": ["GPT 4o", "Gemini 2.5 Pro"] }
```

You can leave out `models`. The backend then uses `ENABLED_MODELS`, or every model if that isn't set. An empty prompt gets a `400`.

The response is `application/x-ndjson`, one JSON event per line:

```json
{"event": "start", "count_prompts": 1, "models": ["GPT 4o", "Gemini 2.5 Pro"]}
{"event": "progress", "model": "GPT 4o", "prompt_index": 0, "prompt": "…", "status": "started"}
{"event": "result", "model": "GPT 4o", "prompt_index": 0, "prompt": "…", "response": "…", "error": null, "duration_ms": 2140}
{"event": "end"}
```

You get one `start`, then a `progress` for each model as its call begins, then one `result` per model as each finishes, and finally `end`. In a `result`, `error` is `null` when the call worked; when it didn't, `error` holds the message and `response` is empty. `prompt_index` counts the turns in that model's conversation, starting from `0`.

## POST /api/reset-memory

```json
{ "models": ["GPT 4o"] }
```

Clears the conversation history for those models. Leave out `models` to clear everyone's.

## POST /api/remove-models

```json
{ "models": ["Nova Premier"] }
```

Throws away those models' history and marks them as unused, so they start from scratch if you pick them again.
