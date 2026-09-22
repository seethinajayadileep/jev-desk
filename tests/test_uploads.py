"""CSV, text, and PDF uploads become the one customer message."""

import io
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pypdf import PdfReader, PdfWriter

from jev_desk.samples import SAMPLES
from jev_desk.server import Desk, handler_for
from jev_desk.uploads import UploadError, extract_text, parse_submission
from tests.test_routing import answers
from tests.test_triage import FakeClient, FakeResult


BILLING = SAMPLES[0].message
SALES = SAMPLES[2].message


def _multipart(message: str, filename: str | None = None, data: bytes | None = None, content_type: str = "application/octet-stream"):
    boundary = "jevdeskboundary"
    parts = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="message"\r\n\r\n'
            f"{message}\r\n"
        ).encode()
    ]
    if filename is not None:
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="upload"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
            + (data or b"")
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def _tiny_pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 720 Td ({safe}) Tj ET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_text_and_csv_and_pdf_become_the_message():
    assert extract_text("note.txt", BILLING.encode()) == BILLING
    assert extract_text("note.csv", BILLING.encode()) == BILLING
    csv_rows = "team,note\nbilling,Charged twice\nsales,Annual plan\n"
    assert extract_text("inbox.csv", csv_rows.encode()) == (
        "team: billing\nnote: Charged twice\n\nteam: sales\nnote: Annual plan"
    )
    assert extract_text("ticket.pdf", _tiny_pdf(SALES)) == SALES


def test_rejects_the_wrong_kind_and_unreadable_files():
    for name, data in (
        ("notes.docx", b"hello"),
        ("image.png", b"\x89PNG\r\n"),
        ("scan.pdf", b"not a pdf"),
        ("empty.txt", b"   \n"),
        ("blank.csv", b"\n\n"),
    ):
        try:
            extract_text(name, data)
        except UploadError as exc:
            assert str(exc)
        else:
            raise AssertionError(name)
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=72, height=72)
    long_pdf = io.BytesIO()
    writer.write(long_pdf)
    try:
        extract_text("long.pdf", long_pdf.getvalue())
    except UploadError as exc:
        assert "too many pages" in str(exc)
    else:
        raise AssertionError("long pdf")
    locked = io.BytesIO()
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(_tiny_pdf(SALES))))
    writer.encrypt("secret")
    writer.write(locked)
    try:
        extract_text("locked.pdf", locked.getvalue())
    except UploadError as exc:
        assert "password" in str(exc)
    else:
        raise AssertionError("locked pdf")


def test_sample_text_file_uses_the_same_route_and_names_the_file():
    desk = Desk(live=False)
    body, content_type = _multipart("", "customer.txt", BILLING.encode(), "text/plain")
    submission = parse_submission(content_type, body)
    html = desk.page_for_submission(submission)
    assert "Billing" in html
    assert "refund requested" in html
    assert "From customer.txt" in html
    assert 'class="queue-name"' in html


def test_bad_upload_does_not_invent_a_queue():
    desk = Desk(live=False)
    html = desk.page_for_submission(parse_submission(*reversed(_multipart("", "photo.png", b"hello", "image/png"))))
    assert "Upload a CSV, text, or PDF file." in html
    assert "No team, urgency, or refund probability was invented" in html
    assert 'class="queue-name"' not in html
    assert "From photo.png" in html


def test_filename_is_escaped():
    desk = Desk(live=False)
    html = desk.page_for_submission(
        parse_submission(*reversed(_multipart("", "<script>.txt", b"hello", "text/plain")))
    )
    assert "From &lt;script&gt;.txt" in html
    assert "<script>.txt" not in html


def test_live_pdf_is_one_call_with_the_extracted_text():
    team, urgency, refund = answers(choice="sales", noul=0.05, team_confidence=0.93, urgency_confidence=0.8)
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-1.13.0"))
    desk = Desk(live=True, client=client)
    body, content_type = _multipart("ignored pasted text", "plan.pdf", _tiny_pdf(SALES), "application/pdf")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        request = Request(
            f"http://127.0.0.1:{port}/",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        html = urlopen(request).read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert len(client.calls) == 1
    assert client.calls[0][0] == SALES
    assert "From plan.pdf" in html
    assert "Sales" in html
    assert "jev-1.13.0" in html


def test_pasted_message_still_sorts_when_the_file_field_is_empty():
    desk = Desk(live=False)
    body, content_type = _multipart(BILLING, "", b"", "application/octet-stream")
    html = desk.page_for_submission(parse_submission(content_type, body))
    assert "Billing" in html
    assert "refund requested" in html
    assert "From " not in html


def test_home_page_offers_a_file_input():
    desk = Desk(live=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        html = urlopen(f"http://127.0.0.1:{port}/").read().decode()
        body, content_type = _multipart("", "nope.exe", b"MZ", "application/octet-stream")
        request = Request(
            f"http://127.0.0.1:{port}/",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            response = urlopen(request)
            status = response.status
            page = response.read().decode()
        except HTTPError as exc:
            status = exc.code
            page = exc.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert 'type="file"' in html
    assert 'accept=".csv,.txt,.text,.pdf,text/csv,text/plain,application/pdf"' in html
    assert "Or upload a file" in html
    assert status == 200
    assert "Upload a CSV, text, or PDF file." in page
