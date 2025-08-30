import json
from typing import List, Tuple

from ..models.llm_provider import KongLLM, Message
from ..models.question_objects import Question


async def load_questions_from_jsonl_bytes(file_bytes: bytes) -> List[Question]:
    questions: List[Question] = []
    for raw_line in file_bytes.splitlines():
        line = raw_line.decode("utf-8").strip()
        if not line:
            continue
        try:
            question_data = json.loads(line)
            questions.append(Question.from_dict(question_data))
        except json.JSONDecodeError:
            continue
    return questions


def extract_all_user_prompts(questions: List[Question]) -> List[Tuple[str, str]]:
    user_prompt_pairs: List[Tuple[str, str]] = []
    for question in questions:
        for turn in question.conversation:
            if turn.role == "user":
                user_prompt_pairs.append((question.question_id, turn.content))
    return user_prompt_pairs


# async def run_models_over_prompts(
#     user_prompts: List[str],
# ) -> Dict[str, List[Dict[str, Any]]]:
#     results_by_model: Dict[str, List[Dict[str, Any]]] = {}
#     model_names_to_run = list(KongLLM.model_name_map.keys())

#     async def run_single_model(model_display_name: str):
#         model_results: List[Dict[str, Any]] = []
#         conversation_state: List[Message] = []

#         async with KongLLM(model_name=model_display_name) as model:
#             for prompt_index, prompt_text in enumerate(user_prompts):
#                 try:
#                     conversation_state.append(Message(role="user", content=prompt_text))
#                     assistant_reply = await model.chat_complete(
#                         messages=conversation_state
#                     )
#                     conversation_state.append(
#                         Message(role="assistant", content=assistant_reply.content)
#                     )
#                     model_results.append(
#                         {
#                             "prompt_index": prompt_index,
#                             "prompt": prompt_text,
#                             "response": assistant_reply.content,
#                             "error": None,
#                         }
#                     )
#                 except Exception as error:
#                     conversation_state.append(
#                         Message(role="assistant", content=f"[ERROR] {error}")
#                     )
#                     model_results.append(
#                         {
#                             "prompt_index": prompt_index,
#                             "prompt": prompt_text,
#                             "response": "",
#                             "error": str(error),
#                         }
#                     )

#         results_by_model[model_display_name] = model_results

#     for model_name in model_names_to_run:
#         await run_single_model(model_name)

#     return results_by_model


async def run_models_stream(
    user_prompts: List[str]
):
    models_to_run = list(KongLLM.model_name_map.keys())

    yield {
        "event": "start",
        "count_prompts": len(user_prompts),
        "models": models_to_run,
    }

    for model_display_name in models_to_run:
        conversation_state: List[Message] = []

        async with KongLLM(model_name=model_display_name) as model:
            for prompt_index, prompt_text in enumerate(user_prompts):
                try:
                    conversation_state.append(Message(role="user", content=prompt_text))
                    assistant_reply = await model.chat_complete(
                        messages=conversation_state
                    )
                    conversation_state.append(
                        Message(role="assistant", content=assistant_reply.content)
                    )

                    yield {
                        "event": "result",
                        "model": model_display_name,
                        "prompt_index": prompt_index,
                        "prompt": prompt_text,
                        "response": assistant_reply.content,
                        "error": None,
                    }

                except Exception as error:
                    conversation_state.append(
                        Message(role="assistant", content=f"[ERROR] {error}")
                    )
                    yield {
                        "event": "result",
                        "model": model_display_name,
                        "prompt_index": prompt_index,
                        "prompt": prompt_text,
                        "response": "",
                        "error": str(error),
                    }

    yield {"event": "end"}
