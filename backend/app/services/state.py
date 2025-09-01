# backend/app/services/state.py
from typing import Dict, List, Optional
from ..models.llm_provider import Message
from ..models.llm_provider import KongLLM

conversation_memory: Dict[str, List[Message]] = {
    model_name: [] for model_name in KongLLM.model_name_map.keys()
}
used_models: Dict[str, bool] = {
    model_name: False for model_name in KongLLM.model_name_map.keys()
}


def get_memory(model_name: str) -> List[Message]:
    return conversation_memory.setdefault(model_name, [])


def mark_used(model_name: str) -> None:
    used_models[model_name] = True


def has_been_used(model_name: str) -> bool:
    return bool(used_models.get(model_name, False))


def reset_memory(models: Optional[List[str]] = None) -> None:
    if models is None:
        for k in list(conversation_memory.keys()):
            conversation_memory[k] = []
            used_models[k] = False
        return
    for m in models:
        conversation_memory[m] = []
        used_models[m] = False


def reset_memory_if_first_time(selected_models: List[str]) -> None:
    for m in selected_models:
        if not has_been_used(m):
            conversation_memory[m] = []  # ensure fresh for first-ever use


def remove_models(models: List[str]) -> None:
    """
    Remove models' memory right now and mark them unused.
    (If they are selected again later, they start fresh from that moment.)
    """
    for m in models:
        conversation_memory.pop(m, None)  # drop any existing memory list
        used_models[m] = False  # mark as never used (fresh start next time)
