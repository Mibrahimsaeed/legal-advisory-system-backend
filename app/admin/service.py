"""
Admin dashboard queries.

Privacy rules enforced here (not just in the dashboard UI):
- Questions are returned without answers and without the asker's identity.
- Documents are returned as metadata only; contents are never read.
- People in question/document lists are shown as an anonymous "User xxxx"
  reference (a short hash of their id), not their email or name.
- Every admin change is written to the audit log.
"""

import hashlib
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import status as http_status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditLog
from app.auth.models import PasswordResetCode
from app.billing.models import FreeUsage, Payment, Subscription
from app.common.exceptions import AppException, NotFoundError
from app.common.storage_client import delete_file
from app.conversations.models import Conversation, Message
from app.documents.models import Document
from app.generated_docs.models import GeneratedDocument
from app.rag.models import RagDocument
from app.users.models import EmailChangeCode, User
from config.settings import get_settings

# Legal areas used to group questions. Simple keyword matching for now; the
# AI pipeline can replace this with a real classifier later.
# Each pattern is matched at word boundaries ("fir" must not match "fired").
# A trailing "*" means "word starts with" (e.g. "marr*" matches marry, married, marriage).
TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Labour & employment", (
        "salary", "salaries", "employer*", "employee*", "employment", "labour", "labor", "fired", "dismiss*",
        "termination", "terminated", "job", "jobs", "wage*", "maternity", "gratuity", "eobi", "overtime",
    )),
    ("Family law", (
        "divorce*", "khula", "marr*", "nikah*", "custody", "maintenance", "dowry", "dower", "haq mehr", "talaq",
        "guardian*", "husband", "wife", "domestic violence", "child support",
    )),
    ("Criminal law", (
        "fir", "bail", "theft", "murder*", "ppc", "penal", "police", "arrest*", "crime*", "criminal", "fraud",
        "harass*", "cheque", "dishonour*", "489-f", "confession", "accused", "fia", "cyber*",
    )),
    ("Property law", (
        "propert*", "land", "tenant*", "rent", "landlord*", "lease", "mutation", "registry", "inherit*",
        "succession", "sale deed", "evict*", "security deposit",
    )),
    ("Constitutional rights", (
        "constitution*", "fundamental right*", "article", "writ", "high court", "supreme court",
    )),
    ("Business & tax", (
        "tax*", "fbr", "compan*", "contract*", "business*", "partnership", "ntn", "secp", "freelanc*",
    )),
]


def _topic_regex(words: tuple[str, ...]) -> re.Pattern[str]:
    parts = [re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) for w in words]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)")


_TOPIC_PATTERNS = [(label, _topic_regex(words)) for label, words in TOPIC_KEYWORDS]
OTHER_TOPIC = "Other"

MIME_LABELS = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "text/plain": "Text",
}


def anonymize(user_id: str) -> str:
    """Stable, non-reversible short label for a user, e.g. 'User 3f2a'."""
    key = get_settings().jwt_secret_key.encode()
    return "User " + hashlib.sha256(key + user_id.encode()).hexdigest()[:4]


def classify_topic(text: str) -> str:
    lowered = text.lower()
    for label, pattern in _TOPIC_PATTERNS:
        if pattern.search(lowered):
            return label
    return OTHER_TOPIC


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _per_day(dates: list[datetime], days: int, now: datetime) -> list[dict]:
    start = (now - timedelta(days=days - 1)).date()
    counts = Counter(_utc(d).date() for d in dates if d is not None)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": counts.get(start + timedelta(days=i), 0)}
        for i in range(days)
    ]


async def _count(db: AsyncSession, stmt) -> int:
    return (await db.execute(stmt)).scalar_one() or 0


async def get_stats(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    users_30d = (await db.execute(select(User.created_at).where(User.created_at >= d30))).scalars().all()
    questions_30d = (
        await db.execute(
            select(Message.content, Message.created_at).where(Message.role == "user", Message.created_at >= d30)
        )
    ).all()

    topic_counts = Counter(classify_topic(q.content) for q in questions_30d)
    docs_by_type = (await db.execute(select(Document.mime_type, func.count()).group_by(Document.mime_type))).all()

    return {
        "total_users": await _count(db, select(func.count()).select_from(User)),
        "active_users": await _count(db, select(func.count()).select_from(User).where(User.is_active.is_(True))),
        "new_users_7d": sum(1 for d in users_30d if _utc(d) >= d7),
        "total_conversations": await _count(db, select(func.count()).select_from(Conversation)),
        "total_questions": await _count(db, select(func.count()).select_from(Message).where(Message.role == "user")),
        "questions_7d": sum(1 for q in questions_30d if _utc(q.created_at) >= d7),
        "total_documents": await _count(db, select(func.count()).select_from(Document)),
        "storage_bytes": await _count(db, select(func.coalesce(func.sum(Document.size_bytes), 0))),
        "questions_per_day": _per_day([q.created_at for q in questions_30d], 30, now),
        "signups_per_day": _per_day(list(users_30d), 30, now),
        "topics": [{"label": k, "count": v} for k, v in topic_counts.most_common()],
        "documents_by_type": sorted(
            ({"label": MIME_LABELS.get(m, "Other"), "count": c} for m, c in docs_by_type),
            key=lambda x: -x["count"],
        ),
    }


async def list_users(db: AsyncSession, q: str | None, status: str | None, limit: int, offset: int) -> dict:
    stmt = select(User)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "deactivated":
        stmt = stmt.where(User.is_active.is_(False))

    total = await _count(db, select(func.count()).select_from(stmt.subquery()))
    users = (await db.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return {"items": await enrich_users(db, list(users)), "total": total}


async def enrich_users(db: AsyncSession, users: list[User]) -> list[dict]:
    """Adds per-user counts (conversations, documents, last activity)."""
    ids = [u.id for u in users]
    if not ids:
        return []
    conv_counts = dict((await db.execute(
        select(Conversation.user_id, func.count()).where(Conversation.user_id.in_(ids)).group_by(Conversation.user_id)
    )).all())
    doc_counts = dict((await db.execute(
        select(Document.user_id, func.count()).where(Document.user_id.in_(ids)).group_by(Document.user_id)
    )).all())
    last_msg = dict((await db.execute(
        select(Conversation.user_id, func.max(Message.created_at))
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id.in_(ids))
        .group_by(Conversation.user_id)
    )).all())
    chat_counts = dict((await db.execute(
        select(Conversation.user_id, func.count())
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id.in_(ids), Message.role == "user")
        .group_by(Conversation.user_id)
    )).all())
    now = datetime.now(timezone.utc)
    plans = {
        sub.user_id: sub.plan_id
        for sub in (await db.execute(select(Subscription).where(
            Subscription.user_id.in_(ids), Subscription.status == "active"
        ))).scalars().all()
        if _utc(sub.expires_at) > now
    }
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at,
            "conversations": conv_counts.get(u.id, 0),
            "documents": doc_counts.get(u.id, 0),
            "last_active": last_msg.get(u.id),
            "plan": plans.get(u.id, "free"),
            "chats_used": chat_counts.get(u.id, 0),
        }
        for u in users
    ]


async def set_user_active(db: AsyncSession, admin: User, user_id: str, is_active: bool) -> User:
    if user_id == admin.id:
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "You can't change your own account status")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    if user.is_admin and not is_active:
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "Another admin can't be deactivated from the dashboard")

    if user.is_active != is_active:
        user.is_active = is_active
        db.add(AdminAuditLog(
            admin_id=admin.id,
            action="user_reactivated" if is_active else "user_deactivated",
            target_user_id=user.id,
            detail=user.email,
        ))
        await db.commit()
        await db.refresh(user)
    return user


async def list_questions(db: AsyncSession, q: str | None, topic: str | None, limit: int, offset: int) -> dict:
    stmt = (
        select(Message.id, Message.content, Message.created_at, Conversation.user_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.role == "user")
        .order_by(Message.created_at.desc())
    )
    if q:
        stmt = stmt.where(func.lower(Message.content).like(f"%{q.strip().lower()}%"))
    rows = (await db.execute(stmt)).all()

    items = [
        {
            "id": r.id,
            "user_ref": anonymize(r.user_id),
            "question": r.content,
            "topic": classify_topic(r.content),
            "created_at": r.created_at,
        }
        for r in rows
    ]
    if topic:
        items = [i for i in items if i["topic"] == topic]
    return {"items": items[offset : offset + limit], "total": len(items)}


async def list_documents(db: AsyncSession, q: str | None, limit: int, offset: int) -> dict:
    stmt = select(Document)
    if q:
        stmt = stmt.where(func.lower(Document.original_filename).like(f"%{q.strip().lower()}%"))
    total = await _count(db, select(func.count()).select_from(stmt.subquery()))
    docs = (await db.execute(stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return {
        "items": [
            {
                "id": d.id,
                "user_ref": anonymize(d.user_id),
                "original_filename": d.original_filename,
                "file_type": MIME_LABELS.get(d.mime_type, "Other"),
                "size_bytes": d.size_bytes,
                "status": d.status,
                "created_at": d.created_at,
            }
            for d in docs
        ],
        "total": total,
    }


async def get_system(db: AsyncSession) -> dict:
    from app.chat import pipeline_client

    settings = get_settings()
    try:
        await db.execute(select(1))
        db_status = {"name": "Database", "status": "ok", "detail": settings.database_url.split(":")[0]}
    except Exception as e:  # pragma: no cover
        db_status = {"name": "Database", "status": "error", "detail": str(e)[:120]}

    # Ask the pipeline a tiny probe question: the placeholder answers start
    # with "[Simulated", a real pipeline's answers won't.
    try:
        probe = await pipeline_client.query("status check", [], [])
        simulated = probe.content.startswith("[Simulated")
    except Exception:
        simulated = False
    services = [
        {"name": "API server", "status": "ok", "detail": f"environment: {settings.app_env}"},
        db_status,
        {
            "name": "AI answer pipeline",
            "status": "simulated" if simulated else "ok",
            "detail": "Placeholder answers until the GraphRAG pipeline is connected" if simulated else "Connected",
        },
        {
            "name": "Email (reset codes)",
            "status": "ok" if settings.smtp_host and settings.smtp_user else "not_configured",
            "detail": "SMTP configured" if settings.smtp_host and settings.smtp_user else "Codes are printed in the server terminal",
        },
        {
            "name": "Google sign-in",
            "status": "ok" if settings.google_client_ids_list else "not_configured",
            "detail": f"{len(settings.google_client_ids_list)} client ID(s)" if settings.google_client_ids_list else "GOOGLE_CLIENT_IDS not set",
        },
        _case_law_service(),
    ]
    tables = {
        "users": await _count(db, select(func.count()).select_from(User)),
        "conversations": await _count(db, select(func.count()).select_from(Conversation)),
        "messages": await _count(db, select(func.count()).select_from(Message)),
        "uploaded documents": await _count(db, select(func.count()).select_from(Document)),
        "generated documents": await _count(db, select(func.count()).select_from(GeneratedDocument)),
    }
    return {"app_env": settings.app_env, "services": services, "database_tables": tables}


def _case_law_service() -> dict:
    from app.caselaw.repository import load_cases

    n = len(load_cases())
    return {
        "name": "Case law data",
        "status": "ok" if n else "not_configured",
        "detail": f"{n:,} cases loaded" if n else "No case law files in data/case_law yet",
    }


async def list_audit(db: AsyncSession, limit: int, offset: int) -> dict:
    total = await _count(db, select(func.count()).select_from(AdminAuditLog))
    rows = (
        await db.execute(
            select(AdminAuditLog, User.email)
            .join(User, User.id == AdminAuditLog.admin_id)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "admin_email": email,
                "action": log.action,
                "target": log.detail,
                "detail": None,
                "created_at": log.created_at,
            }
            for log, email in rows
        ],
        "total": total,
    }


# ---------------------------------------------------------------------------
# Overview for the web app dashboard + user deletion
# ---------------------------------------------------------------------------

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
OVERVIEW_MONTHS = 6


def _month_starts(now: datetime, count: int) -> list[datetime]:
    """First instant of each of the last `count` calendar months, oldest first, ending with this month."""
    year, month = now.year, now.month
    starts = []
    for _ in range(count):
        starts.append(datetime(year, month, 1, tzinfo=timezone.utc))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(starts))


def _next_month(dt: datetime) -> datetime:
    return datetime(dt.year + (dt.month == 12), 1 if dt.month == 12 else dt.month + 1, 1, tzinfo=timezone.utc)


def _monthly(starts: list[datetime], values: list[tuple[datetime, int]], cumulative: bool = False) -> list[dict]:
    """Bucket (timestamp, amount) pairs into the given months."""
    series = []
    for start in starts:
        end = _next_month(start)
        if cumulative:
            total = sum(v for t, v in values if _utc(t) < end)
        else:
            total = sum(v for t, v in values if start <= _utc(t) < end)
        series.append({"month": MONTH_LABELS[start.month - 1], "value": total})
    return series


async def get_overview(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    starts = _month_starts(now, OVERVIEW_MONTHS)
    this_month = starts[-1]
    d30 = now - timedelta(days=30)

    users = (await db.execute(select(User.id, User.created_at, User.is_admin))).all()
    questions = (await db.execute(
        select(Message.created_at, Conversation.user_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.role == "user")
    )).all()
    payments = (await db.execute(select(Payment.paid_at, Payment.amount_pkr))).all()
    active_subs = [
        sub for sub in (await db.execute(select(Subscription).where(Subscription.status == "active"))).scalars().all()
        if _utc(sub.expires_at) > now
    ]
    paid_ids = {sub.user_id for sub in active_subs}
    plan_counts = Counter(sub.plan_id for sub in active_subs)
    admin_ids = {u.id for u in users if u.is_admin}

    rag_count = await _count(
        db, select(func.count()).select_from(RagDocument).where(RagDocument.status == "completed")
    )

    return {
        "stats": {
            "total_users": len(users),
            "active_users": len({q.user_id for q in questions if _utc(q.created_at) >= d30}),
            "new_users": sum(1 for u in users if _utc(u.created_at) >= this_month),
            "total_queries": len(questions),
            "free_chats_used": sum(1 for q in questions if q.user_id not in paid_ids),
            "paid_users": len(paid_ids),
            "monthly_revenue": sum(p.amount_pkr for p in payments if _utc(p.paid_at) >= this_month),
            "rag_documents": rag_count,
        },
        "user_growth": _monthly(starts, [(u.created_at, 1) for u in users], cumulative=True),
        "revenue": _monthly(starts, [(p.paid_at, p.amount_pkr) for p in payments]),
        "queries": _monthly(starts, [(q.created_at, 1) for q in questions]),
        "user_distribution": [
            {"label": "Free users", "value": sum(1 for u in users if u.id not in paid_ids and u.id not in admin_ids)},
            {"label": "Paid users", "value": len(paid_ids - admin_ids)},
            {"label": "Admins", "value": len(admin_ids)},
        ],
        "subscribers_by_plan": [
            {"label": "Monthly plan", "value": plan_counts.get("monthly", 0)},
            {"label": "Quarterly plan", "value": plan_counts.get("quarterly", 0)},
        ],
    }


async def delete_user(db: AsyncSession, admin: User, user_id: str) -> None:
    """
    Permanently delete a person and everything they own: chats, uploaded and
    generated files, codes, plan and allowance. Payment records are kept for
    revenue history. The deletion itself is written to the audit log.
    """
    if user_id == admin.id:
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "You can't delete your own account")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    if user.is_admin:
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "Another admin can't be deleted from the dashboard")

    file_keys = list((await db.execute(select(Document.storage_key).where(Document.user_id == user_id))).scalars().all())
    file_keys += list(
        (await db.execute(select(GeneratedDocument.storage_key).where(GeneratedDocument.user_id == user_id))).scalars().all()
    )
    email = user.email

    conversation_ids = select(Conversation.id).where(Conversation.user_id == user_id)
    await db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
    for model in (Conversation, Document, GeneratedDocument, PasswordResetCode, EmailChangeCode, FreeUsage, Subscription):
        await db.execute(delete(model).where(model.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    db.add(AdminAuditLog(admin_id=admin.id, action="user_deleted", target_user_id=user_id, detail=email))
    await db.commit()

    # Files go last: if the database step had failed, nothing would be lost.
    for key in file_keys:
        delete_file(key)
