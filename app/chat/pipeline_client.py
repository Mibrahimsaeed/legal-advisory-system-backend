"""
Interface to the AI/RAG pipeline (built separately by the AI/ML team members,
covering the knowledge graph, embeddings, and retrieval).

This module currently returns a simulated answer so the rest of the chat
system (history, storage, API contract) can be built and tested without
waiting for the real pipeline. When the real pipeline is ready, only the
body of `query()` needs to change — its signature and return type should
stay the same so nothing else in the app needs to be touched.
"""

from dataclasses import dataclass, field


@dataclass
class AnswerResult:
    content: str
    sources: list[str] = field(default_factory=list)  # citations / document references, once real


async def query(question: str, context_docs: list[str], history: list[dict]) -> AnswerResult:
    """
    question: the user's latest message
    context_docs: extracted text from any documents attached to this query
    history: prior conversation turns, as [{"role": ..., "content": ...}, ...]

    Returns an AnswerResult. Currently simulated — see module docstring.
    """
    # --- SIMULATED RESPONSE (Phase 5) ---
    # Replace this block with a real call into the GraphRAG / agentic
    # reasoning pipeline once it exists. Keep the function signature the same.
    context_note = f" (using {len(context_docs)} attached document(s))" if context_docs else ""
    simulated_content = (
        f"[Simulated response] I received your question: \"{question}\"{context_note}. "
        "This is a placeholder answer used to validate the chat workflow end-to-end. "
        "Once the AI/RAG pipeline is connected, this will be replaced with a real, "
        "grounded legal answer."
    )
    return AnswerResult(content=simulated_content, sources=[])
