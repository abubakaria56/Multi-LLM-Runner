# backend/app/api.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import json
from typing import List, Optional

from .services.runner import run_models_stream_concurrent_prompt
from .services.state import reset_memory, remove_models

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    prompt: str
    models: Optional[List[str]] = None


@router.post("/chat-stream")
async def chat_stream(req: ChatRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    async def ndjson_generator():
        async for event in run_models_stream_concurrent_prompt(
            prompt, model_names=req.models
        ):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(ndjson_generator(), media_type="application/x-ndjson")


class ResetRequest(BaseModel):
    models: Optional[List[str]] = None


@router.post("/reset-memory")
async def reset_memory_route(req: ResetRequest):
    reset_memory(req.models)
    return JSONResponse({"status": "ok", "reset_models": req.models or "all"})


class RemoveModelsRequest(BaseModel):
    models: List[str]


@router.post("/remove-models")
async def remove_models_route(req: RemoveModelsRequest):
    if not req.models:
        raise HTTPException(status_code=400, detail="No models provided.")
    remove_models(req.models)
    return JSONResponse({"status": "ok", "removed": req.models})
