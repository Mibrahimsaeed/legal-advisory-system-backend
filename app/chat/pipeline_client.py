"""
Interface to the AI/RAG pipeline (built separately by the AI/ML team members,
covering the knowledge graph, embeddings, and retrieval).

This module currently returns a simulated answer so the rest of the chat
system (history, storage, API contract) can be built and tested without
waiting for the real pipeline. When the real pipeline is ready, only the
bodies of `query()` and `ingest()` need to change — their signatures and
return types should stay the same so nothing else in the app needs to be touched.
"""

from dataclasses import dataclass, field

from app.chat.answer import AnswerSegment, LegalAnswer


@dataclass
class AnswerResult:
    content: str  # plain-text rendering of the answer (history, streaming, admin stats)
    sources: list[str] = field(default_factory=list)  # citations / document references, once real
    # Structured answer for the web app. If the pipeline only produces text,
    # leave this None and the chat service wraps `content` automatically.
    structured: LegalAnswer | None = None


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
    # No statutes or cases are invented here: the structured answer carries the
    # placeholder text only, with empty law/case/source lists.
    context_note = f" (using {len(context_docs)} attached document(s))" if context_docs else ""
    simulated_content = (
        f"[Simulated response] I received your question: \"{question}\"{context_note}. "
        "This is a placeholder answer used to validate the chat workflow end-to-end. "
        "Once the AI/RAG pipeline is connected, this will be replaced with a real, "
        "grounded legal answer."
    )
    structured = LegalAnswer(
        issue=question.strip()[:300],
        analysis=[AnswerSegment(text=simulated_content)],
    )
    return AnswerResult(content=simulated_content, sources=[], structured=structured)


async def ingest(title: str, text: str, metadata: dict) -> None:
    """
    Add a legal source document (statute, act, ordinance, regulation) to the
    pipeline's knowledge base: chunking, embeddings, graph linking.

    Currently a no-op placeholder, so admins can upload sources and track
    their status, but nothing is indexed until the AI/ML team implements this.
    """
    return None
