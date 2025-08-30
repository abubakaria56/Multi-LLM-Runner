import asyncio
import json
from typing import Any, Dict, List, AsyncIterator, Optional
from ..models.llm_provider import KongLLM, Message
from ..models.question_objects import Question
from ..core.settings import settings


async def load_questions_from_jsonl_bytes(data: bytes) -> List[Question]:
    """Parse uploaded JSONL bytes into Question objects (skip bad lines)."""
    questions: List[Question] = []
    for raw in data.splitlines():
        line = raw.decode("utf-8").strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            questions.append(Question.from_dict(record))
        except json.JSONDecodeError:
            continue
    return questions


def extract_user_prompts(questions: List[Question]) -> List[str]:
    """Collect every user message from all conversations in order."""
    prompts: List[str] = []
    for q in questions:
        for turn in q.conversation:
            if turn.role == "user":
                prompts.append(turn.content)
    return prompts


async def run_models_over_prompts(
    prompts: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Batch (non-streaming) evaluation; kept for compatibility with the old endpoint.
    Returns a dict of model -> list of {prompt, response, error}.
    """
    results: Dict[str, List[Dict[str, Any]]] = {}
    sem = asyncio.Semaphore(settings.max_concurrent_evals)

    async def _run_single(model_display_name: str):
        model_results: List[Dict[str, Any]] = []
        async with KongLLM(model_name=model_display_name) as model:
            for p in prompts:
                async with sem:
                    try:
                        resp = await model.chat_complete(
                            [Message(role="user", content=p)]
                        )
                        model_results.append(
                            {"prompt": p, "response": resp.content, "error": None}
                        )
                    except Exception as e:
                        model_results.append(
                            {"prompt": p, "response": "", "error": str(e)}
                        )
        results[model_display_name] = model_results

    model_names = settings.enabled_models or list(KongLLM.model_name_map.keys())
    for m in model_names:
        await _run_single(m)

    return results


async def run_models_stream(
    prompts: List[str],
    model_names: Optional[List[str]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Streaming version: yields one dict per completed (model, prompt) pair.

    Yields events shaped like:
      { "event": "result", "model": "<display model>", "prompt_index": 0,
        "prompt": "...", "response": "...", "error": null }
    and at the end:
      { "event": "end" }
    """
    sem = asyncio.Semaphore(settings.max_concurrent_evals)
    models = (
        model_names or settings.enabled_models or list(KongLLM.model_name_map.keys())
    )

    # Optional: send a "start" meta event first
    yield {
        "event": "start",
        "count_prompts": len(prompts),
        "models": models,
    }

    for model_display_name in models:
        async with KongLLM(model_name=model_display_name) as model:
            for idx, p in enumerate(prompts):
                async with sem:
                    try:
                        resp = await model.chat_complete(
                            [Message(role="user", content=p)]
                        )
                        yield {
                            "event": "result",
                            "model": model_display_name,
                            "prompt_index": idx,
                            "prompt": p,
                            "response": resp.content,
                            "error": None,
                        }
                    except Exception as e:
                        yield {
                            "event": "result",
                            "model": model_display_name,
                            "prompt_index": idx,
                            "prompt": p,
                            "response": "",
                            "error": str(e),
                        }

    yield {"event": "end"}
