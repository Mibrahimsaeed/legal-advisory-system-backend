"""Read real case law from the team's PakistanLawSite data export.

Put the export in the folder set by CASE_LAW_DATA_DIR in .env (default: data/case_law).
Accepted files:
  *.json   - a list of cases, or {"cases": [...]}
  *.jsonl  - one case per line
  *.csv    - one case per row, with a header row

Column / key names are matched loosely (see FIELD_ALIASES), so most exports
work without changes. A case needs at least a citation or a title, and some
text or a summary.

If the folder is empty, or nothing matches, the caller gets an empty list and
the app says "not available". Nothing here ever makes up a case.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import get_settings

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "citation": ("citation", "cite", "case_citation", "citations", "reference", "case_no", "case_number"),
    "title": ("title", "case_title", "parties", "name", "case_name"),
    "court": ("court", "court_name", "forum"),
    "date": ("date", "judgment_date", "decided_on", "decision_date", "year"),
    "judges": ("judges", "bench", "judge", "coram"),
    "summary": ("summary", "headnote", "headnotes", "abstract", "short_note"),
    "text": ("text", "judgment", "judgement", "content", "full_text", "body", "description"),
    "url": ("url", "link", "source_url", "source"),
}

STOPWORDS = {
    "the", "and", "for", "with", "case", "cases", "law", "laws", "about", "under", "from", "that", "this",
    "what", "which", "pakistan", "judgment", "judgments", "judgement", "court", "give", "find", "show", "me",
}


@dataclass
class Case:
    citation: str = ""
    title: str = ""
    court: str = ""
    date: str = ""
    judges: str = ""
    summary: str = ""
    text: str = ""
    url: str = ""
    _search: str = field(default="", repr=False)

    @property
    def heading(self) -> str:
        if self.title and self.citation:
            return f"{self.title} ({self.citation})"
        return self.title or self.citation


def _pick(row: dict, key: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in FIELD_ALIASES[key]:
        v = lowered.get(alias)
        if v is None:
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v if x)
        v = str(v).strip()
        if v:
            return v
    return ""


def _to_case(row: dict) -> Case | None:
    if not isinstance(row, dict):
        return None
    c = Case(**{k: _pick(row, k) for k in FIELD_ALIASES})
    if not (c.citation or c.title) or not (c.text or c.summary):
        return None
    c._search = " ".join([c.citation, c.title, c.court, c.summary, c.text]).lower()
    return c


def _read_file(path: Path) -> list[Case]:
    rows: list = []
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data.get("cases", []) if isinstance(data, dict) else data
        elif suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        elif suffix == ".csv":
            csv.field_size_limit(10**8)
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
    except (OSError, ValueError, csv.Error):
        return []
    return [c for c in (_to_case(r) for r in rows) if c]


_cache: dict[str, object] = {"sig": None, "cases": []}


def data_dir() -> Path:
    return Path(get_settings().case_law_data_dir)


def load_cases() -> list[Case]:
    """All cases in the data folder. Re-reads only when the files change."""
    folder = data_dir()
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in {".json", ".jsonl", ".csv"}) if folder.is_dir() else []
    sig = tuple((str(p), p.stat().st_mtime, p.stat().st_size) for p in files)
    if sig != _cache["sig"]:
        cases: list[Case] = []
        for p in files:
            cases.extend(_read_file(p))
        _cache["sig"], _cache["cases"] = sig, cases
    return _cache["cases"]  # type: ignore[return-value]


def _terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9\-]+", query.lower())
    return [w for w in words if (len(w) >= 3 or w.isdigit()) and w not in STOPWORDS]


def search(query: str, limit: int = 5) -> list[Case]:
    """Best-matching real cases for the query, or [] if none match well."""
    cases = load_cases()
    if not cases:
        return []
    q = query.strip().lower()
    terms = _terms(query)

    scored: list[tuple[float, Case]] = []
    for c in cases:
        # An exact citation match (e.g. "PLD 2019 SC 123") wins outright.
        if c.citation and c.citation.lower() == q:
            scored.append((1000.0, c))
            continue
        if not terms:
            continue
        hits = [t for t in terms if t in c._search]
        if len(hits) * 2 < len(terms):  # need at least half the words
            continue
        title, summary, cite = c.title.lower(), c.summary.lower(), c.citation.lower()
        score = 0.0
        for t in hits:
            score += 1 + 3 * (t in title) + 4 * (t in cite) + 2 * (t in summary)
        if q and q in c._search:
            score += 5
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]
