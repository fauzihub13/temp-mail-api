"""Temp Mail API — minimal IMAP-based email viewer.

Endpoints:
  GET /inbox                   — list all inbox emails (today only, last 10)
  GET /inbox/{email}           — list emails for specific address (today only)
  GET /inbox/{email}/{uid}     — email detail
  GET /health                  — health check

Usage:
  uvicorn main:app --host 0.0.0.0 --port 8000
"""

import email as email_lib
import imaplib
import os
import re
import socket
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")
IMAP_TIMEOUT = int(os.getenv("IMAP_TIMEOUT", "30"))

app = FastAPI(title="Temp Mail API", version="1.2.0")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _connect(host: str = None, port: int = None, user: str = None, password: str = None) -> imaplib.IMAP4_SSL:
    """Connect to IMAP with timeout."""
    h = host or IMAP_HOST
    p = port or IMAP_PORT
    u = user or IMAP_USER
    pw = password or IMAP_PASS

    socket.setdefaulttimeout(IMAP_TIMEOUT)
    imap = imaplib.IMAP4_SSL(h, p)
    imap.login(u, pw)
    return imap


def _parse_addr(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"[\w.+-]+@[\w.-]+", s)
    return m.group(0).lower() if m else ""


def _today_imap_search() -> str:
    """Return IMAP date string for today (e.g., '23-Jul-2026')."""
    return datetime.now().strftime("%d-%b-%Y")


def _msg_to_dict(msg, uid: str, body: str = None) -> dict:
    """Convert email.message.Message → minimal dict."""
    date_str = msg.get("Date", "")
    ts = None
    if date_str:
        try:
            ts = parsedate_to_datetime(date_str).isoformat()
        except Exception:
            ts = date_str

    result = {
        "uid": uid,
        "from": _parse_addr(msg.get("From", "")),
        "to": _parse_addr(msg.get("To", "")),
        "date": ts,
    }
    if body is not None:
        result["body"] = body
    return result


def _msg_body(msg) -> str:
    """Extract plain-text body from email."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    return ""


def _is_today(date_str: str) -> bool:
    """Check if date string is today."""
    if not date_str:
        return False
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date() == datetime.now().date()
    except Exception:
        return False


def _search_emails(target_email: str, limit: int = 50) -> list[dict]:
    """Search IMAP for emails sent TO target_email (today only)."""
    target = target_email.lower().strip()
    imap = _connect()
    try:
        imap.select(IMAP_FOLDER, readonly=True)

        # Server-side filter: only today's emails
        today = _today_imap_search()
        _, msg_data = imap.search(None, f'SINCE "{today}"')
        msg_ids = msg_data[0].split()
        if not msg_ids:
            return []

        results = []
        scan_ids = list(reversed(msg_ids[-50:]))

        for msg_id in scan_ids:
            try:
                _, raw = imap.fetch(msg_id, "(RFC822 FLAGS)")
                if not raw or not raw[0]:
                    continue

                msg = email_lib.message_from_bytes(raw[0][1])
                flags_raw = raw[1].decode() if isinstance(raw[1], bytes) else str(raw[1])

                # Check recipient match
                recipients = []
                for hdr in ("To", "Delivered-To", "X-Original-To", "Envelope-To"):
                    val = msg.get(hdr, "") or ""
                    for part in val.split(","):
                        addr = _parse_addr(part)
                        if addr:
                            recipients.append(addr)

                if target not in recipients:
                    continue

                uid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                seen = "\\Seen" in flags_raw
                body = _msg_body(msg)

                entry = _msg_to_dict(msg, uid, body)
                entry["seen"] = seen
                results.append(entry)

                if len(results) >= limit:
                    break
            except Exception:
                continue

        return results
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _fetch_email(target_email: str, uid: str) -> dict:
    """Fetch single email by UID."""
    target = target_email.lower().strip()
    imap = _connect()
    try:
        imap.select(IMAP_FOLDER, readonly=True)
        _, raw = imap.fetch(uid.encode(), "(RFC822 FLAGS)")
        if not raw or not raw[0]:
            raise ValueError(f"email uid={uid} not found")

        msg = email_lib.message_from_bytes(raw[0][1])

        # Verify recipient
        recipients = []
        for hdr in ("To", "Delivered-To", "X-Original-To", "Envelope-To"):
            val = msg.get(hdr, "") or ""
            for part in val.split(","):
                addr = _parse_addr(part)
                if addr:
                    recipients.append(addr)

        if target not in recipients:
            raise ValueError(f"email uid={uid} not addressed to {target}")

        flags_raw = raw[1].decode() if isinstance(raw[1], bytes) else str(raw[1])
        seen = "\\Seen" in flags_raw
        body = _msg_body(msg)

        entry = _msg_to_dict(msg, uid, body)
        entry["seen"] = seen
        return entry
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _read_inbox(host: str, port: int, user: str, password: str, folder: str, limit: int) -> list[dict]:
    """Read all emails from IMAP inbox (today only)."""
    imap = _connect(host=host, port=port, user=user, password=password)
    try:
        imap.select(folder, readonly=True)

        # Server-side filter: only today's emails
        today = _today_imap_search()
        _, msg_data = imap.search(None, f'SINCE "{today}"')
        msg_ids = msg_data[0].split()
        if not msg_ids:
            return []

        results = []
        scan_ids = list(reversed(msg_ids[-limit:]))

        for msg_id in scan_ids:
            try:
                _, raw = imap.fetch(msg_id, "(RFC822 FLAGS)")
                if not raw or not raw[0]:
                    continue

                msg = email_lib.message_from_bytes(raw[0][1])
                flags_raw = raw[1].decode() if isinstance(raw[1], bytes) else str(raw[1])
                seen = "\\Seen" in flags_raw

                uid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                body = _msg_body(msg)

                entry = _msg_to_dict(msg, uid, body)
                entry["seen"] = seen
                results.append(entry)
            except Exception:
                continue

        return results
    finally:
        try:
            imap.logout()
        except Exception:
            pass


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "imap": IMAP_HOST}


@app.get("/inbox/{email}")
def get_inbox(email: str, limit: int = Query(default=50, le=200)):
    """List emails for address (today only, newest first)."""
    try:
        emails = _search_emails(email, limit=limit)
        return {"email": email, "count": len(emails), "emails": emails}
    except socket.timeout:
        raise HTTPException(504, detail="IMAP connection timeout")
    except imaplib.IMAP4.error as e:
        raise HTTPException(502, detail=f"IMAP error: {e}")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/inbox/{email}/{uid}")
def get_email_detail(email: str, uid: str):
    """Get email detail."""
    try:
        detail = _fetch_email(email, uid)
        return detail
    except socket.timeout:
        return JSONResponse(
            status_code=408,
            content={"error": True, "message": "Connection to mail server timed out", "code": 408}
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            return JSONResponse(
                status_code=404,
                content={"error": True, "message": f"Email with UID '{uid}' not found", "code": 404}
            )
        return JSONResponse(
            status_code=404,
            content={"error": True, "message": f"Email UID '{uid}' not addressed to '{email}'", "code": 404}
        )
    except imaplib.IMAP4.error as e:
        return JSONResponse(
            status_code=502,
            content={"error": True, "message": f"IMAP error: {str(e)}", "code": 502}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": True, "message": str(e), "code": 500}
        )


@app.get("/inbox")
def get_all_inbox(limit: int = Query(default=10, le=100, description="Max emails to fetch")):
    """Read all inbox emails (today only). Uses IMAP credentials from .env."""
    try:
        emails = _read_inbox(
            host=IMAP_HOST,
            port=IMAP_PORT,
            user=IMAP_USER,
            password=IMAP_PASS,
            folder=IMAP_FOLDER,
            limit=limit,
        )
        return {
            "host": IMAP_HOST,
            "folder": IMAP_FOLDER,
            "count": len(emails),
            "emails": emails,
        }
    except socket.timeout:
        raise HTTPException(504, detail="IMAP connection timeout")
    except imaplib.IMAP4.error as e:
        raise HTTPException(502, detail=f"IMAP error: {e}")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
