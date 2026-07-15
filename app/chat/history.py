from config.constants import MAX_HISTORY_MESSAGES
from app.conversations.models import Message


def build_history(messages: list[Message]) -> list[dict]:
    """
    Convert stored Message rows into the [{"role": ..., "content": ...}, ...]
    shape that LLM APIs expect. Uses a simple sliding window (most recent N
    messages) to keep prompts a manageable size — swap for summarization
    later if conversations get long enough to need it.
    """
    recent = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages
    return [{"role": m.role, "content": m.content} for m in recent]
