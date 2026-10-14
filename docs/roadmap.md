---
title: Roadmap
nav_order: 6
---

# Roadmap

| Status | Item |
|---|---|
| ✅ Done | Concurrent multi-model chat with per-model memory |
| ✅ Done | Streaming results with per-model latency and errors |
| ✅ Done | OpenRouter and Kong gateway providers |
| Planned | **Batch benchmark mode:** run a JSONL benchmark across models (loader and schema already in `question_objects.py`) |
| Planned | **LLM-judge grading:** score each answer YES/NO with reasoning, using the `JudgeResponse` schema |
| Planned | Enforce `MAX_CONCURRENT_EVALS` and per-client conversation memory (memory is currently held in process and shared) |
