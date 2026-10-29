"""
Direct LLM fallback — a simpler path that skips the RAG pipeline entirely.
Useful for quick testing or if the pipeline is temporarily unavailable.

Currently simulated, same as pipeline_client.py. Wire up a real LLM API call
here (e.g. OpenAI, Anthropic) if a direct-fallback mode is ever needed
alongside the main pipeline.
"""

from app.chat.pipeline_client import AnswerResult


async def query(question: str, history: list[dict]) -> AnswerResult:
    simulated_content = (
        f"[Simulated LLM fallback response] {question}"
    )
    return AnswerResult(content=simulated_content, sources=[])
