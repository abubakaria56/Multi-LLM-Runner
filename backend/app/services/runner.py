# backend/app/services/runner.py
import asyncio
import time
from typing import Any, Dict, List, AsyncIterator, Optional

from ..models.llm_provider import KongLLM, Message
from ..core.settings import settings
from .state import get_memory, reset_memory_if_first_time, mark_used


async def run_models_stream_concurrent_prompt(
    prompt_text: str,
    *,
    model_names: Optional[List[str]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    # Use selected models if provided, else default to all
    all_default = list(KongLLM.model_name_map.keys())
    models_to_run = model_names or settings.enabled_models or all_default

    # If a model is chosen "at this point" for the first time, start with blank memory
    reset_memory_if_first_time(models_to_run)

    # Tell client what's coming
    yield {"event": "start", "count_prompts": 1, "models": models_to_run}

    event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()

    async def model_worker(model_display_name: str) -> None:
        memory = get_memory(model_display_name)
        turn_index = sum(1 for m in memory if m.role == "user")

        await event_queue.put(
            {
                "event": "progress",
                "model": model_display_name,
                "prompt_index": turn_index,
                "prompt": prompt_text,
                "status": "started",
            }
        )

        started_at = time.perf_counter()
        try:
            # 1) add user -> memory
            memory.append(Message(role="user", content=prompt_text))

            # 2) call model with full memory
            async with KongLLM(model_display_name) as model:
                assistant_reply = await model.chat_complete(messages=memory)

            # 3) add assistant -> memory
            memory.append(Message(role="assistant", content=assistant_reply.content))
            # mark this model as "now used"
            mark_used(model_display_name)

            duration_ms = int((time.perf_counter() - started_at) * 1000)
            await event_queue.put(
                {
                    "event": "result",
                    "model": model_display_name,
                    "prompt_index": turn_index,
                    "prompt": prompt_text,
                    "response": assistant_reply.content,
                    "error": None,
                    "duration_ms": duration_ms,
                }
            )
        except Exception as error:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            await event_queue.put(
                {
                    "event": "result",
                    "model": model_display_name,
                    "prompt_index": turn_index,
                    "prompt": prompt_text,
                    "response": "",
                    "error": str(error),
                    "duration_ms": duration_ms,
                }
            )

        await event_queue.put({"event": "_worker_done", "model": model_display_name})

    workers = [asyncio.create_task(model_worker(name)) for name in models_to_run]

    done_workers = 0
    total_workers = len(workers)
    try:
        while done_workers < total_workers:
            event = await event_queue.get()
            if event.get("event") == "_worker_done":
                done_workers += 1
                continue
            yield event
    finally:
        await asyncio.gather(*workers, return_exceptions=True)

    yield {"event": "end"}
