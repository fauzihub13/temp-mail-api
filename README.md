# Temp Mail API

Minimal IMAP-based email viewer API. Query inbox by email address via REST API. Only returns today's emails.

## Setup

```bash
cd temp-mail-api
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
```ini
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASS=your_app_password
IMAP_FOLDER=INBOX
IMAP_TIMEOUT=30
```

Gmail: pakai [App Password](https://myaccount.google.com/apppasswords), bukan password biasa. Enable IMAP di Settings.

## Run

```bash
# Development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

Docs otomatis: `http://localhost:8000/docs` (Swagger UI)

## Endpoints

### `GET /health`

Health check.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "imap": "imap.gmail.com"}
```

---

### `GET /inbox`

List semua email di inbox hari ini (10 terakhir default). Pakai credentials dari `.env`.

| Param | Type | Default | Keterangan |
|---|---|---|---|
| `limit` | query | `10` | Max emails (maks 100) |

```bash
curl http://localhost:8000/inbox
curl http://localhost:8000/inbox?limit=20
```

```json
{
  "host": "imap.gmail.com",
  "folder": "INBOX",
  "count": 2,
  "emails": [
    {
      "uid": "1236",
      "from": "info@account.netflix.com",
      "to": "mad_e8x2a@mpruy.my.id",
      "date": "2026-07-23T07:23:23+00:00",
      "body": "Tap the link to create your account...",
      "seen": false
    }
  ]
}
```

---

### `GET /inbox/{email}`

List email yang dikirim ke address tersebut hari ini (newest first).

| Param | Type | Default | Keterangan |
|---|---|---|---|
| `email` | path | - | Email address target |
| `limit` | query | `50` | Max emails (maks 200) |

```bash
curl http://localhost:8000/inbox/test@domain.com
curl http://localhost:8000/inbox/test@domain.com?limit=10
```

```json
{
  "email": "test@domain.com",
  "count": 1,
  "emails": [
    {
      "uid": "1231",
      "from": "noreply@xiaomi.com",
      "to": "test@domain.com",
      "date": "2026-07-23T10:00:00+00:00",
      "body": "Your verification code is 123456",
      "seen": false
    }
  ]
}
```

---

### `GET /inbox/{email}/{uid}`

Detail email berdasarkan UID.

```bash
curl http://localhost:8000/inbox/test@domain.com/1231
```

```json
{
  "uid": "1231",
  "from": "noreply@xiaomi.com",
  "to": "test@domain.com",
  "date": "2026-07-23T10:00:00+00:00",
  "body": "Your verification code is 123456",
  "seen": false
}
```

**Error response (404):**

```json
{
  "error": true,
  "message": "Email with UID '999' not found",
  "code": 404
}
```

```json
{
  "error": true,
  "message": "Email UID '1231' not addressed to 'other@domain.com'",
  "code": 404
}
```

## Response Fields

| Field | Type | Keterangan |
|---|---|---|
| `uid` | string | Unique ID email di mailbox |
| `from` | string | Pengirim email |
| `to` | string | Penerima email |
| `date` | string | Tanggal email (ISO format) |
| `body` | string | Isi email (plain text atau HTML) |
| `seen` | boolean | Status sudah dibaca atau belum |

## Env Variables

| Variable | Default | Keterangan |
|---|---|---|
| `IMAP_HOST` | `imap.gmail.com` | IMAP server host |
| `IMAP_PORT` | `993` | IMAP server port (SSL) |
| `IMAP_USER` | - | IMAP username / email |
| `IMAP_PASS` | - | IMAP password / app password |
| `IMAP_FOLDER` | `INBOX` | Mailbox folder name |
| `IMAP_TIMEOUT` | `30` | Koneksi timeout (detik) |

## Error Codes

| Code | Keterangan |
|---|---|
| 200 | OK |
| 404 | Email/UID tidak ditemukan atau bukan recipient |
| 408 | Connection timeout |
| 502 | IMAP connection error |
| 500 | Internal server error |
