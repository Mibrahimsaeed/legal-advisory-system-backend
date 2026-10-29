from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class DayCount(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class LabelCount(BaseModel):
    label: str
    count: int


class Stats(BaseModel):
    total_users: int
    active_users: int
    new_users_7d: int
    total_conversations: int
    total_questions: int
    questions_7d: int
    total_documents: int
    storage_bytes: int
    questions_per_day: list[DayCount]  # last 30 days
    signups_per_day: list[DayCount]  # last 30 days
    topics: list[LabelCount]  # legal area of questions, last 30 days
    documents_by_type: list[LabelCount]


class AdminUser(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    conversations: int
    documents: int
    last_active: datetime | None
    plan: str = "free"  # free | monthly | quarterly
    chats_used: int = 0  # questions this person has asked


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class UserStatusUpdate(BaseModel):
    is_active: bool


class AdminQuestion(BaseModel):
    """A user's question only. Never the answer, never who asked."""
    id: str
    user_ref: str  # anonymous, e.g. "User 3f2a"
    question: str
    topic: str
    created_at: datetime


class AdminQuestionPage(BaseModel):
    items: list[AdminQuestion]
    total: int


class AdminDocument(BaseModel):
    """File metadata only. The file's contents are never exposed here."""
    id: str
    user_ref: str
    original_filename: str
    file_type: str
    size_bytes: int
    status: str
    created_at: datetime


class AdminDocumentPage(BaseModel):
    items: list[AdminDocument]
    total: int


class ServiceStatus(BaseModel):
    name: str
    status: str  # "ok" | "not_configured" | "simulated" | "error"
    detail: str


class SystemStatus(BaseModel):
    app_env: str
    services: list[ServiceStatus]
    database_tables: dict[str, int]


class AuditEntry(BaseModel):
    id: str
    admin_email: str
    action: str
    target: str | None
    detail: str | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


# --- Overview for the web app's admin dashboard (camelCase to match its types) ---

class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class OverviewStats(_Camel):
    total_users: int
    active_users: int  # asked a question in the last 30 days
    new_users: int  # joined this calendar month
    total_queries: int
    free_chats_used: int  # questions asked by people not on a paid plan
    paid_users: int
    monthly_revenue: int  # PKR, this calendar month
    rag_documents: int  # legal sources fully processed


class MonthlyValue(_Camel):
    month: str
    value: int


class LabelledValue(_Camel):
    label: str
    value: int


class Overview(_Camel):
    stats: OverviewStats
    user_growth: list[MonthlyValue]  # total users at the end of each month
    revenue: list[MonthlyValue]
    queries: list[MonthlyValue]
    user_distribution: list[LabelledValue]
    subscribers_by_plan: list[LabelledValue]
