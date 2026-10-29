"""Fill the database with demo users, questions and documents for the admin dashboard.

All demo accounts use emails ending in @demo.example.com, so they are easy to remove.

Usage (from the backend folder):
    python3 scripts/seed_demo_data.py            # add demo data
    python3 scripts/seed_demo_data.py --remove   # delete all demo data again

Demo accounts all use the password: DemoPass123
"""
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.auth.password import hash_password  # noqa: E402
from db.session import AsyncSessionLocal as async_session_factory  # noqa: E402
from app.conversations.models import Conversation, Message  # noqa: E402
from app.documents.models import Document  # noqa: E402
from app.users.models import User  # noqa: E402

DEMO_DOMAIN = "@demo.example.com"

NAMES = [
    "Ayesha Khan", "Bilal Ahmed", "Fatima Noor", "Hamza Ali", "Zainab Raza", "Usman Tariq",
    "Maryam Iqbal", "Saad Malik", "Hira Shah", "Ali Hassan", "Sana Javed", "Omar Farooq",
    "Iqra Siddiqui", "Hassan Butt", "Mahnoor Aslam", "Daniyal Qureshi", "Areeba Sheikh", "Taha Mirza",
]

QUESTIONS = [
    "What is the procedure for khula in Pakistan?",
    "How is child custody decided after divorce?",
    "Can my husband marry again without my permission?",
    "How much maintenance can a wife claim after divorce?",
    "What should I do if police refuse to register an FIR?",
    "How do I apply for bail in a criminal case?",
    "What is the punishment for cheque dishonour under section 489-F?",
    "Is a confession before police admissible in court?",
    "My landlord is not returning my security deposit. What can I do?",
    "How do I transfer property after my father's death?",
    "What documents are needed to register a property sale?",
    "Can a tenant be evicted without notice?",
    "What does Article 25 of the Constitution guarantee?",
    "Can I file a writ petition in the High Court?",
    "What are my rights if I am arrested?",
    "My employer fired me without notice. Am I owed compensation?",
    "What is the minimum wage in Punjab?",
    "How many days of maternity leave am I entitled to?",
    "How do I register a private limited company with SECP?",
    "Do I have to file an income tax return as a freelancer?",
    "What is the limitation period for filing a civil suit?",
    "How do I get a succession certificate?",
    "Can a daughter claim a share in inherited agricultural land?",
    "What is the process for a court marriage?",
    "How do I report cyber harassment to the FIA?",
]

DOCS = [
    ("rent_agreement.pdf", "application/pdf"),
    ("nikahnama_scan.pdf", "application/pdf"),
    ("fir_copy.pdf", "application/pdf"),
    ("property_deed.pdf", "application/pdf"),
    ("employment_contract.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("legal_notice_draft.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("case_notes.txt", "text/plain"),
]


async def remove() -> None:
    async with async_session_factory() as db:
        ids = list((await db.execute(select(User.id).where(User.email.like(f"%{DEMO_DOMAIN}")))).scalars())
        if not ids:
            print("No demo data found.")
            return
        conv_ids = list((await db.execute(select(Conversation.id).where(Conversation.user_id.in_(ids)))).scalars())
        if conv_ids:
            await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await db.execute(delete(Conversation).where(Conversation.user_id.in_(ids)))
        await db.execute(delete(Document).where(Document.user_id.in_(ids)))
        await db.execute(delete(User).where(User.id.in_(ids)))
        await db.commit()
        print(f"Removed {len(ids)} demo users and their data.")


async def seed() -> None:
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    pw = hash_password("DemoPass123")
    async with async_session_factory() as db:
        exists = (await db.execute(select(User.id).where(User.email.like(f"%{DEMO_DOMAIN}")).limit(1))).first()
        if exists:
            print("Demo data already exists. Run with --remove first to recreate it.")
            return
        n_conv = n_q = n_doc = 0
        for i, name in enumerate(NAMES):
            joined = now - timedelta(days=rng.randint(1, 29), hours=rng.randint(0, 23))
            user = User(
                id=str(uuid.uuid4()),
                email=name.lower().replace(" ", ".") + DEMO_DOMAIN,
                hashed_password=pw,
                full_name=name,
                is_active=i not in (5, 13),  # two deactivated accounts for the demo
                created_at=joined,
                updated_at=joined,
            )
            db.add(user)
            for _ in range(rng.randint(1, 3)):
                started = joined + timedelta(hours=rng.randint(1, max(2, int((now - joined).total_seconds() // 3600) - 1)))
                if started > now:
                    started = now - timedelta(minutes=rng.randint(5, 600))
                qs = rng.sample(QUESTIONS, rng.randint(1, 4))
                conv = Conversation(id=str(uuid.uuid4()), user_id=user.id, title=qs[0][:60], created_at=started, updated_at=started)
                db.add(conv)
                n_conv += 1
                t = started
                for q in qs:
                    db.add(Message(id=str(uuid.uuid4()), conversation_id=conv.id, role="user", content=q, created_at=t))
                    db.add(Message(
                        id=str(uuid.uuid4()), conversation_id=conv.id, role="assistant",
                        content="[Demo answer - not shown on the admin dashboard]", created_at=t + timedelta(seconds=20),
                    ))
                    n_q += 1
                    t += timedelta(minutes=rng.randint(2, 30))
            for _ in range(rng.choice([0, 0, 1, 1, 2])):
                fname, mime = rng.choice(DOCS)
                db.add(Document(
                    id=str(uuid.uuid4()), user_id=user.id, original_filename=fname, mime_type=mime,
                    size_bytes=rng.randint(40_000, 2_400_000), storage_key=f"demo/{uuid.uuid4()}",
                    status=rng.choice(["ready", "ready", "ready", "failed"]),
                    created_at=joined + timedelta(hours=rng.randint(1, 20)),
                ))
                n_doc += 1
        await db.commit()
        print(f"Added {len(NAMES)} demo users, {n_conv} conversations, {n_q} questions, {n_doc} documents.")
        print("Demo password for all of them: DemoPass123")


if __name__ == "__main__":
    asyncio.run(remove() if "--remove" in sys.argv else seed())
