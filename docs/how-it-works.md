---
title: How it works
nav_order: 3
---

# How it works
{: .no_toc }

1. TOC
{:toc}

---

## Architecture

The React interface sends a prompt and a list of models to the FastAPI backend. The runner starts one `asyncio` task per model, each with that model's conversation history, and pushes every event onto a queue that streams back to the browser as newline-delimited JSON.

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

## Request lifecycle

Each prompt follows the same lifecycle. Results arrive in the order the models finish, not the order they were selected.

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

## Project structure

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
│           ├── runner.py              concurrent fan-out and event streaming
│           └── state.py               per-model conversation memory
└── frontend/
    └── src/App.tsx                    model picker, streaming columns, Markdown and maths
```
