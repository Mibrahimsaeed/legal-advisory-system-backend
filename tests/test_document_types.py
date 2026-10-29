"""Uploads accept only PDF, Word (.docx) and text files, judged by extension AND real contents."""

import io
import zipfile

import pytest

pytestmark = pytest.mark.asyncio

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<x/>")
    return buffer.getvalue()


DOCX_BYTES = _zip("[Content_Types].xml", "word/document.xml")


async def _upload(client, headers, name, data, content_type="application/octet-stream"):
    return await client.post("/documents/upload", headers=headers, files={"file": (name, data, content_type)})


async def test_allowed_types_accepted_regardless_of_browser_content_type(client, make_user):
    h, _ = await make_user("types.ok@example.com")
    pdf = await _upload(client, h, "brief.pdf", PDF_BYTES)
    docx = await _upload(client, h, "contract.docx", DOCX_BYTES)
    txt = await _upload(client, h, "notes.txt", "Section 7. Talaq. اردو".encode("utf-8"))
    assert (pdf.status_code, docx.status_code, txt.status_code) == (201, 201, 201)
    assert pdf.json()["mime_type"] == "application/pdf"
    assert docx.json()["mime_type"] == DOCX_MIME
    assert txt.json()["mime_type"] == "text/plain"  # the real type is stored, not the header


async def test_extension_is_case_insensitive(client, make_user):
    h, _ = await make_user("types.case@example.com")
    assert (await _upload(client, h, "SCAN.PDF", PDF_BYTES)).status_code == 201
    assert (await _upload(client, h, "Notes.TXT", b"hello")).status_code == 201


@pytest.mark.parametrize("name,data", [
    ("photo.png", PNG_BYTES), ("photo.jpg", JPEG_BYTES), ("photo.jpeg", JPEG_BYTES), ("anim.gif", b"GIF89a\x01\x00"),
    ("virus.exe", b"MZ\x90\x00"), ("data.csv", b"a,b\n1,2\n"), ("pack.zip", _zip("a.txt")),
    ("slides.pptx", _zip("ppt/presentation.xml")), ("sheet.xlsx", _zip("xl/workbook.xml")), ("noextension", b"hello"),
])
async def test_other_file_types_rejected(client, make_user, name, data):
    h, _ = await make_user("types.bad@example.com")
    r = await _upload(client, h, name, data, "text/plain")  # even when the header claims text/plain
    assert r.status_code == 415, name
    assert "PDF" in r.json()["detail"] and "docx" in r.json()["detail"]


async def test_old_doc_format_explained(client, make_user):
    h, _ = await make_user("types.doc@example.com")
    r = await _upload(client, h, "old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    assert r.status_code == 415 and "save the file as .docx" in r.json()["detail"]


@pytest.mark.parametrize("name,data", [
    ("fake.txt", PNG_BYTES),                       # image renamed to .txt
    ("fake2.txt", JPEG_BYTES),
    ("fake.pdf", PNG_BYTES),                       # image renamed to .pdf
    ("fake2.pdf", b"just some text, not a pdf"),
    ("fake.docx", PNG_BYTES),                      # not a zip at all
    ("fake2.docx", _zip("something/else.xml")),    # a zip, but not a Word document
    ("fake3.docx", b"plain text pretending to be docx"),
    ("binary.txt", b"hello\x00world"),             # binary data in a .txt
])
async def test_renamed_files_rejected_by_contents(client, make_user, name, data):
    h, _ = await make_user("types.fake@example.com")
    r = await _upload(client, h, name, data, "text/plain" if name.endswith(".txt") else "application/pdf")
    assert r.status_code == 415, name
    assert "does not look like a real" in r.json()["detail"]


async def test_empty_file_rejected(client, make_user):
    h, _ = await make_user("types.empty@example.com")
    assert (await _upload(client, h, "empty.txt", b"")).status_code == 400


async def test_rejected_upload_is_not_stored(client, make_user):
    h, _ = await make_user("types.nostore@example.com")
    await _upload(client, h, "fake.txt", PNG_BYTES)
    assert (await client.get("/documents", headers=h)).json() == []


async def test_admin_rag_upload_uses_the_same_rules(client, make_user):
    admin, _ = await make_user("types.admin@example.com", admin=True)
    data = {"title": "Act", "document_type": "act", "year": "1999", "source": "gazette"}
    fake = await client.post("/admin/rag/documents", headers=admin, data=data, files={"file": ("act.txt", PNG_BYTES, "text/plain")})
    assert fake.status_code == 415
    image = await client.post("/admin/rag/documents", headers=admin, data=data, files={"file": ("act.png", PNG_BYTES, "image/png")})
    assert image.status_code == 415
    ok = await client.post("/admin/rag/documents", headers=admin, data=data, files={"file": ("act.docx", DOCX_BYTES, "application/octet-stream")})
    assert ok.status_code == 202
