"""
Structured legal answer shown by the web app (issue, applicable law, case law,
analysis, conclusion, cited sources).

The wire format is camelCase to match the web app's TypeScript types, so the
front end can use responses as-is. Python code uses snake_case attributes.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer
from pydantic.alias_generators import to_camel

LegalDomain = Literal["general", "family", "criminal"]
ArchetypeId = Literal["scenario-analysis", "statutory-provision", "case-law-research", "legal-remedies"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StatuteSource(_CamelModel):
    kind: Literal["statute"] = "statute"
    id: str
    title: str
    passage: str
    relevance: str
    provision: str


class CaseSource(_CamelModel):
    kind: Literal["case"] = "case"
    id: str
    title: str
    passage: str
    relevance: str
    court: str
    principle: str


LegalSource = Annotated[StatuteSource | CaseSource, Field(discriminator="kind")]


class AnswerSegment(_CamelModel):
    text: str
    source_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_missing_source(self, handler: Any) -> dict[str, Any]:
        # The web app treats `sourceId` as optional (absent, not null).
        data = handler(self)
        if data.get("sourceId", data.get("source_id")) is None:
            data.pop("sourceId", None)
            data.pop("source_id", None)
        return data


class AnswerAuthority(_CamelModel):
    source_id: str
    summary: str


class LegalAnswer(_CamelModel):
    issue: str
    applicable_law: list[AnswerAuthority] = Field(default_factory=list)
    case_law: list[AnswerAuthority] = Field(default_factory=list)
    analysis: list[AnswerSegment] = Field(default_factory=list)
    conclusion: list[AnswerSegment] = Field(default_factory=list)
    sources: list[LegalSource] = Field(default_factory=list)

    @classmethod
    def from_text(cls, question: str, text: str) -> "LegalAnswer":
        """Wrap a plain-text answer so every reply has the structured shape."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text.strip()]
        return cls(
            issue=question.strip()[:300],
            analysis=[AnswerSegment(text=p) for p in paragraphs],
        )

    def to_storage(self) -> dict:
        """JSON-safe dict (camelCase) for the messages.answer column."""
        return self.model_dump(mode="json", by_alias=True)
