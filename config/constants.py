"""
App-wide constants that are NOT environment-dependent.
(Things that change per-environment belong in settings.py instead.)
"""

# --- Uploads ---
ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/plain",
}

# --- Chat / pipeline ---
MAX_HISTORY_MESSAGES = 20          # how many past messages to feed as context
MAX_QUESTION_LENGTH_CHARS = 4000

# --- Pagination defaults ---
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
