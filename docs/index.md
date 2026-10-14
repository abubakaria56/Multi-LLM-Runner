---
title: Home
nav_order: 1
permalink: /
---

# Multi-LLM Runner

Multi-LLM Runner sends the same prompt to several language models at once and shows their answers next to each other.

The usual way to compare models is to paste one prompt into a handful of chat windows and keep track of which answer came from where. Here you pick the models, type the prompt once, and each answer appears in its own column when that model finishes, along with how long it took. Every model also keeps its own conversation, so you can ask follow-up questions and see how the models hold up over several turns, not just the first one.

![The Multi-LLM Runner page: model picker, prompt box, Run and Reset memory buttons]({{ '/screenshot.png' | relative_url }})

## What it does

- Calls the selected models at the same time, so one slow model doesn't hold up the others.
- Streams each answer to the page as soon as it's ready.
- Keeps a separate chat history for each model. You can reset all of them or only some.
- Shows the response time for every answer. If a model fails, its error shows up in its own column and the rest carry on.
- Retries on timeouts, rate limits and malformed responses, and strips `<think>` blocks out of reasoning models' answers.
- Works with OpenRouter or a Kong-style LLM gateway, chosen with one environment variable.
- Renders Markdown, code and LaTeX in the answers.

The backend is FastAPI on Python 3.11, and the frontend is React with TypeScript and Vite.

To run it yourself, start with [Getting started]({% link getting-started.md %}). [How it works]({% link how-it-works.md %}) explains how a request moves through the backend, and the routes are in the [API reference]({% link api.md %}). Next on the list is a batch mode that runs a benchmark file across models and grades the answers with an LLM judge; see the [roadmap]({% link roadmap.md %}).
