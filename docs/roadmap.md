---
title: Roadmap
nav_order: 6
---

# Roadmap

Chatting with several models at once, per-model memory, streaming with timings and errors, and the OpenRouter and Kong providers all work today.

Still to do:

- **Batch benchmark mode.** Run a JSONL benchmark across the models instead of one prompt at a time. The loader and question schema are already in `question_objects.py`.
- **LLM-judge grading.** Have a judge model mark each answer YES or NO and explain why, using the `JudgeResponse` schema that's already there.
- **Concurrency limit and per-user memory.** `MAX_CONCURRENT_EVALS` is read from the settings but not enforced yet, and conversation memory is one shared copy rather than one per user.
