---
title: Home
layout: home
nav_order: 1
description: Send one prompt to several language models in parallel and compare their answers side by side.
permalink: /
---

# Multi-LLM Runner
{: .fs-9 }

Ask once. Compare every model.
{: .fs-6 .fw-300 }

Send one prompt to several large language models in parallel and watch their answers stream in side by side, each with its own conversation memory and response time.
{: .fs-5 .fw-300 }

[Get started]({% link getting-started.md %}){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/abubakaria56/Multi-LLM-Runner){: .btn .fs-5 .mb-4 .mb-md-0 }

![Multi-LLM Runner interface: model picker, prompt box, Run and Reset memory buttons]({{ '/screenshot.png' | relative_url }})

---

## Why

Comparing language models usually means pasting the same prompt into several chat windows, losing track of which model said what, and guessing at speed. Multi-LLM Runner makes that comparison a single action: one prompt goes to every selected model at the same moment, and each answer arrives in its own column as soon as that model finishes. Follow-up prompts keep each model's own conversation history, so multi-turn behaviour can be compared too.

It was built as a lightweight workbench for evaluating models side by side, and as the foundation for a batch benchmark runner with an LLM judge (see the [roadmap]({% link roadmap.md %})).

## Features

| Feature | What it does |
|---|---|
| ⚡ **Concurrent fan-out** | Every selected model is called in parallel with `asyncio`; a slow model never blocks a fast one. |
| 📡 **Live streaming** | Results stream to the browser as newline-delimited JSON the moment each model finishes. |
| 🧠 **Per-model memory** | Each model keeps its own multi-turn history; reset it for all models or a chosen subset. |
| ⏱️ **Latency and errors per model** | Every answer carries its response time; a failing model reports its own error without stopping the others. |
| 🔁 **Resilient calls** | Exponential-backoff retries on timeouts, rate limits and malformed responses; `<think>` reasoning blocks are stripped from answers. |
| 🔌 **Two providers** | Serve models through [OpenRouter](https://openrouter.ai) or a Kong-style LLM gateway, switched with one environment variable. |
| 📝 **Rich rendering** | GitHub-flavoured Markdown, syntax-highlighted code and KaTeX maths, sanitised before display. |

## Built with

Python 3.11+ · FastAPI · React 19 · TypeScript 5 · Vite 7 · OpenRouter
