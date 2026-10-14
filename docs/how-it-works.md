---
title: How it works
nav_order: 3
---

# How it works

When you click **Run**, the frontend sends the prompt and the selected models to `POST /api/chat-stream`. The backend starts one asyncio task per model. Each task adds the prompt to that model's history, calls the model with the whole history, and puts the result on a shared queue. The endpoint reads from that queue and writes each event to the response as one line of JSON, which is how the page can show an answer the moment its model is done.

```mermaid
flowchart LR
    UI["React UI<br/>(Vite + TypeScript)"] -- "POST /api/chat-stream" --> API["FastAPI"]
    API --> R["Runner<br/>one asyncio task per model"]
    R --> M1["Model A"]
    R --> M2["Model B"]
    R --> M3["Model C"]
    M1 & M2 & M3 --> Q[("Event queue")]
    Q -- "NDJSON stream" --> UI
    R <--> S[("Per-model<br/>conversation memory")]
```

Here is one request with two models. Model B answers first, so its result reaches the browser first:

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI
    participant A as Model A
    participant B as Model B
    UI->>API: POST /api/chat-stream {prompt, models}
    API-->>UI: start {models}
    par in parallel
        API->>A: chat history + prompt
        API->>B: chat history + prompt
    end
    API-->>UI: progress (A started), progress (B started)
    B-->>API: answer
    API-->>UI: result (B, response, duration_ms)
    A-->>API: answer
    API-->>UI: result (A, response, duration_ms)
    API-->>UI: end
```

Conversation history lives in memory in the backend process (`services/state.py`). Everyone using the same backend shares it, and it's gone when the server restarts.

## Where things are

```
Multi-LLM-Runner/
├── backend/
│   └── app/
│       ├── main.py                    FastAPI app and CORS
│       ├── api.py                     HTTP routes
│       ├── core/settings.py           environment settings
│       ├── models/llm_provider.py     OpenRouter and Kong clients, retries, routing
│       ├── models/question_objects.py benchmark loader and LLM-judge schema
│       └── services/
│           ├── runner.py              runs the models and streams the events
│           └── state.py               per-model conversation memory
└── frontend/
    └── src/App.tsx                    model picker, answer columns, Markdown and maths
```
