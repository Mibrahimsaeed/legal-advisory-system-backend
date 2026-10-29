"""
Which files may be uploaded (PDF, Word .docx, plain text) and how they are checked.

The browser's content-type header is only a hint and is easy to fake (an image
renamed to notes.txt still says "text/plain"). So a file is accepted only when
BOTH its extension is allowed AND its actual bytes look like that kind of file.
"""

import codecs
import io
import zipfile
from pathlib import PurePath

from app.common.exceptions import AppException

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT = "text/plain"

EXTENSION_TYPES = {".pdf": PDF, ".docx": DOCX, ".txt": TXT}
ALLOWED_MESSAGE = "Only PDF, Word (.docx) and text (.txt) files can be uploaded."

_PDF_MARKER = b"%PDF-"
_PDF_HEADER_WINDOW = 1024  # the PDF spec allows a little junk before the marker
_TEXT_SAMPLE = 8192


def _is_pdf(data: bytes) -> bool:
    return _PDF_MARKER in data[:_PDF_HEADER_WINDOW]


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _is_text(data: bytes) -> bool:
    sample = data[:_TEXT_SAMPLE]
    if b"\x00" in sample:
        return False
    try:
        # Incremental, so a multi-byte character cut at the end of the sample is not an error.
        codecs.getincrementaldecoder("utf-8")().decode(sample, final=False)
    except UnicodeDecodeError:
        return False
    return True


_CHECKS = {PDF: _is_pdf, DOCX: _is_docx, TXT: _is_text}
_LABELS = {PDF: "PDF", DOCX: "Word (.docx)", TXT: "text"}


def detect_document_type(filename: str, file_bytes: bytes) -> str:
    """Return the file's real MIME type, or raise HTTP 415/400 if it is not an allowed document."""
    extension = PurePath(filename or "").suffix.lower()
    mime_type = EXTENSION_TYPES.get(extension)
    if mime_type is None:
        hint = " Old .doc files are not supported: save the file as .docx first." if extension == ".doc" else ""
        raise AppException(415, ALLOWED_MESSAGE + hint)
    if not file_bytes:
        raise AppException(400, "The file is empty.")
    if not _CHECKS[mime_type](file_bytes):
        raise AppException(415, f"This does not look like a real {_LABELS[mime_type]} file. {ALLOWED_MESSAGE}")
    return mime_type
