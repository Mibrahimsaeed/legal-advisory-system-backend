"""Chat returns the structured legal answer the web app renders, and keeps conversation hints."""

import pytest

pytestmark = pytest.mark.asyncio


async def _conversation(client, headers, **body):
    r = await client.post("/conversations", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_chat_returns_structured_camelcase_answer(client, make_user):
    h, _ = await make_user("chat.struct@example.com")
    conv = await _conversation(client, h, title="Divorce question", domain="family", archetype="legal-remedies")
    assert conv["domain"] == "family" and conv["archetype"] == "legal-remedies"

    r = await client.post(f"/chat/{conv['id']}/message", headers=h, json={"question": "How do I file for khula?"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"].startswith("[Simulated")  # plain text still present
    answer = body["answer"]
    assert answer["issue"] == "How do I file for khula?"
    assert set(answer) == {"issue", "applicableLaw", "caseLaw", "analysis", "conclusion", "sources"}
    assert answer["applicableLaw"] == [] and answer["caseLaw"] == [] and answer["sources"] == []  # nothing invented
    assert answer["analysis"][0]["text"].startswith("[Simulated")
    assert "sourceId" not in answer["analysis"][0]  # optional field is absent, not null


async def test_messages_include_answer_only_for_assistant(client, make_user):
    h, _ = await make_user("chat.msgs@example.com")
    conv = await _conversation(client, h)
    await client.post(f"/chat/{conv['id']}/message", headers=h, json={"question": "What is bail?"})

    items = (await client.get(f"/conversations/{conv['id']}/messages", headers=h)).json()["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[0]["answer"] is None
    assert items[1]["answer"]["issue"] == "What is bail?"


async def test_with_messages_lists_history_newest_first(client, make_user):
    h, _ = await make_user("chat.history@example.com")
    first = await _conversation(client, h, title="First")
    second = await _conversation(client, h, title="Second")
    # Asking in the older conversation moves it to the top of the history.
    await client.post(f"/chat/{first['id']}/message", headers=h, json={"question": "Hello?"})

    r = await client.get("/conversations/with-messages", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [c["title"] for c in items] == ["First", "Second"]
    assert len(items[0]["messages"]) == 2 and items[1]["messages"] == []
    assert items[0]["messages"][1]["answer"]["issue"] == "Hello?"


async def test_domain_hint_on_message_updates_conversation(client, make_user):
    h, _ = await make_user("chat.hint@example.com")
    conv = await _conversation(client, h)
    assert conv["domain"] == "general" and conv["archetype"] is None
    await client.post(
        f"/chat/{conv['id']}/message", headers=h,
        json={"question": "Is this an offence?", "domain": "criminal", "archetype": "statutory-provision"},
    )
    got = (await client.get(f"/conversations/{conv['id']}", headers=h)).json()
    assert got["domain"] == "criminal" and got["archetype"] == "statutory-provision"


async def test_invalid_domain_rejected(client, make_user):
    h, _ = await make_user("chat.baddomain@example.com")
    assert (await client.post("/conversations", headers=h, json={"domain": "tax"})).status_code == 422
    conv = await _conversation(client, h)
    r = await client.post(f"/chat/{conv['id']}/message", headers=h, json={"question": "x", "archetype": "nope"})
    assert r.status_code == 422


async def test_with_messages_only_shows_own_conversations(client, make_user):
    a, _ = await make_user("chat.owner@example.com")
    b, _ = await make_user("chat.other@example.com")
    await _conversation(client, a, title="Private")
    assert (await client.get("/conversations/with-messages", headers=b)).json()["items"] == []


async def test_profile_exposes_admin_flag_and_cors(client, make_user):
    user, _ = await make_user("flag.user@example.com")
    admin, _ = await make_user("flag.admin@example.com", admin=True)
    assert (await client.get("/users/me", headers=user)).json()["is_admin"] is False
    assert (await client.get("/users/me", headers=admin)).json()["is_admin"] is True

    pre = await client.options(
        "/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"},
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_client_supplied_conversation_id(client, make_user):
    import uuid

    h, _ = await make_user("chat.clientid@example.com")
    other, _ = await make_user("chat.clientid2@example.com")
    cid = str(uuid.uuid4())

    created = await client.post("/conversations", headers=h, json={"id": cid, "title": "Mine"})
    assert created.status_code == 201 and created.json()["id"] == cid
    assert (await client.post(f"/chat/{cid}/message", headers=h, json={"question": "Hi"})).status_code == 200

    # The same id can't be taken again, by anyone, and can't be hijacked.
    assert (await client.post("/conversations", headers=h, json={"id": cid})).status_code == 409
    assert (await client.post("/conversations", headers=other, json={"id": cid})).status_code == 409
    assert (await client.post(f"/chat/{cid}/message", headers=other, json={"question": "x"})).status_code == 403
    assert (await client.post("/conversations", headers=h, json={"id": "not-a-uuid"})).status_code == 422
