"""
Extracts plain text from uploaded documents so it can later be fed into
the AI/RAG pipeline. Kept intentionally simple and dependency-light for
now; swap in a more robust library (e.g. pypdf, python-docx) as needed
once the real pipeline is being built.
"""


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    if mime_type == "text/plain":
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    if mime_type == "application/pdf":
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            # pypdf not installed yet — return empty rather than crashing the upload.
            return ""
        except Exception:
            return ""

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            from docx import Document
            import io

            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            return ""
        except Exception:
            return ""

    return ""
