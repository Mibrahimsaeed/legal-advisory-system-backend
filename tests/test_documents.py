import pytest

pytestmark = pytest.mark.asyncio


async def test_upload_document_requires_login(client):
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post("/documents/upload", files=files)
    assert response.status_code == 401


async def test_upload_text_document_success(client, auth_headers):
    files = {"file": ("notes.txt", b"This is a legal note.", "text/plain")}
    response = await client.post("/documents/upload", files=files, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "notes.txt"
    assert body["mime_type"] == "text/plain"
    assert body["status"] == "ready"


async def test_upload_unsupported_file_type_rejected(client, auth_headers):
    files = {"file": ("virus.exe", b"binary content", "application/x-msdownload")}
    response = await client.post("/documents/upload", files=files, headers=auth_headers)
    assert response.status_code == 415


async def test_list_documents(client, auth_headers):
    files = {"file": ("listed.txt", b"content", "text/plain")}
    await client.post("/documents/upload", files=files, headers=auth_headers)

    response = await client.get("/documents", headers=auth_headers)
    assert response.status_code == 200
    filenames = [doc["original_filename"] for doc in response.json()]
    assert "listed.txt" in filenames


async def test_delete_document(client, auth_headers):
    files = {"file": ("to_delete.txt", b"content", "text/plain")}
    upload_response = await client.post("/documents/upload", files=files, headers=auth_headers)
    document_id = upload_response.json()["id"]

    delete_response = await client.delete(f"/documents/{document_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    list_response = await client.get("/documents", headers=auth_headers)
    ids = [doc["id"] for doc in list_response.json()]
    assert document_id not in ids


async def test_delete_nonexistent_document_returns_404(client, auth_headers):
    response = await client.delete("/documents/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
