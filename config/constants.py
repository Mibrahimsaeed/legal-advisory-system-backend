"""
App-wide constants that are NOT environment-dependent.
(Things that change per-environment belong in settings.py instead.)
"""

# --- Chat / pipeline ---
MAX_HISTORY_MESSAGES = 20          # how many past messages to feed as context
MAX_QUESTION_LENGTH_CHARS = 4000

# --- Plans / usage (prices in PKR; kept in step with the web app's billing page) ---
FREE_PLAN_ID = "free"
FREE_QUERY_LIMIT = 6               # free questions allowed per window
FREE_REFRESH_HOURS = 6             # window starts when the limit is reached
PLANS: dict[str, dict] = {
    "free": {"name": "Free", "price_pkr": 0, "period_days": None},
    "monthly": {"name": "Monthly", "price_pkr": 4000, "period_days": 30},
    "quarterly": {"name": "Quarterly", "price_pkr": 11000, "period_days": 90},
}

# --- Pagination defaults ---
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
