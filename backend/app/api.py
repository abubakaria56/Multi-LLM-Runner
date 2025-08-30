from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import json
from .services.runner import (
    load_questions_from_jsonl_bytes,
    extract_user_prompts,
    run_models_over_prompts,
    run_models_stream,
)

router = APIRouter(prefix="/api")


@router.post("/upload")
async def upload_and_run(file: UploadFile = File(...)):
    """
    Legacy non-streaming endpoint: waits for all results then returns JSON.
    """
    if not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="Please upload a .jsonl file")
    data = await file.read()
    questions = await load_questions_from_jsonl_bytes(data)
    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions found in file")

    prompts = extract_user_prompts(questions)
    if not prompts:
        raise HTTPException(status_code=400, detail="No user prompts found in file")

    results = await run_models_over_prompts(prompts)
    return JSONResponse(content={"count_prompts": len(prompts), "results": results})


@router.post("/upload-stream")
async def upload_and_stream(file: UploadFile = File(...)):
    """
    Streaming endpoint: as each (model, prompt) finishes, we push a line of JSON.
    Response type: application/x-ndjson  (1 JSON object per line)
    """
    if not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="Please upload a .jsonl file")

    data = await file.read()
    questions = await load_questions_from_jsonl_bytes(data)
    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions found in file")

    prompts = extract_user_prompts(questions)
    if not prompts:
        raise HTTPException(status_code=400, detail="No user prompts found in file")

    async def ndjson_generator():
        async for event in run_models_stream(prompts):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(ndjson_generator(), media_type="application/x-ndjson")
