from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import json

from .services.runner import (
    load_questions_from_jsonl_bytes,
    extract_all_user_prompts,
    run_models_stream,
)

router = APIRouter(prefix="/api")


# @router.post("/upload")
# async def upload_and_run(file: UploadFile = File(...)):
#     """
#     Non-streaming endpoint: runs all prompts and returns the combined JSON result.
#     """
#     if not file.filename.endswith(".jsonl"):
#         raise HTTPException(status_code=400, detail="Please upload a .jsonl file")

#     file_bytes = await file.read()
#     questions = await load_questions_from_jsonl_bytes(file_bytes)
#     if not questions:
#         raise HTTPException(status_code=400, detail="No valid questions found in file")

#     user_prompt_pairs = extract_all_user_prompts(
#         questions
#     )  # List[(question_id, prompt)]
#     user_prompts = [prompt for (_qid, prompt) in user_prompt_pairs]

#     if not user_prompts:
#         raise HTTPException(status_code=400, detail="No user prompts found in file")

#     results_by_model = await run_models_over_prompts(user_prompts)
#     return JSONResponse(
#         content={"count_prompts": len(user_prompts), "results": results_by_model}
#     )


@router.post("/upload-stream")
async def upload_and_stream(file: UploadFile = File(...)):
    """
    Streaming endpoint: yields NDJSON lines as each (model, prompt) completes.
    """
    if not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="Please upload a .jsonl file")

    file_bytes = await file.read()
    questions = await load_questions_from_jsonl_bytes(file_bytes)
    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions found in file")

    user_prompt_pairs = extract_all_user_prompts(questions)
    user_prompts = [prompt for (_qid, prompt) in user_prompt_pairs]

    if not user_prompts:
        raise HTTPException(status_code=400, detail="No user prompts found in file")

    async def ndjson_generator():
        async for event in run_models_stream(user_prompts):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(ndjson_generator(), media_type="application/x-ndjson")
