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

---

## Cloudflare Email Routing Setup

Arsitektur: **Domain (Cloudflare) → Forward ke Gmail → API baca via IMAP**

### 1. Siapkan Domain

- Domain aktif di Cloudflare (bisa beli di Cloudflare atau transfer)
- Nameserver pointing ke Cloudflare

### 2. Aktifkan Email Routing

1. Login [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Pilih domain kamu
3. Menu **Email** → **Email Routing**
4. Ktab **Get Started**
5. Cloudflare otomatis tambah MX records:
   ```
   Type: MX
   Name: @
   	mail-forwarding.cloudflare.net
   Priority: 47
   ```

### 3. Tambah Destination Address

1. Tab **Routing Rules**
2. Klik **Add catch-all address**
3. Masukkan email Gmail kamu (misal: `your_email@gmail.com`)
4. Gmail dapat email verifikasi → klik konfirmasi
5. Status jadi **Active**

**Hasil:** Semua email ke `*@your_domain.com` masuk ke Gmail.

### 4. Setup Gmail App Password

1. Buka [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Pilih app: **Mail**, device: **Other** → kasih nama "temp-mail-api"
3. Klik **Generate**
4. Copy 16-char password (misal: `abcd efgh ijkl mnop`)
5. Masukkan ke `.env`:
   ```ini
   IMAP_USER=your_email@gmail.com
   IMAP_PASS=abcdefghijklmnop
   ```

### 5. Enable Gmail IMAP

1. Gmail → Settings → See all settings → **Forwarding and POP/IMAP**
2. **IMAP Access** → Enable IMAP
3. Save Changes

### 6. Verifikasi DNS Records

Pastikan records ini ada di Cloudflare DNS:

| Type | Name | Content | Proxy |
|---|---|---|---|
| MX | @ | `route1.mx.cloudflare.net` | N/A |
| MX | @ | `route2.mx.cloudflare.net` | N/A |
| MX | @ | `route3.mx.cloudflare.net` | N/A |

### 7. Test

```bash
# Kirim test email ke random address di domain kamu
# Contoh: test123@your_domain.com

# Lalu cek via API
curl http://localhost:8000/inbox/test123@your_domain.com
```

### Alur Email

```
Sender → Cloudflare (MX) → Gmail inbox → API (IMAP) → Response JSON
```

### Tips

- **Catch-all** = semua email ke domain diterima, tidak perlu buat mailbox manual
- **Gmail limit** ~500 email/hari untuk free account
- **Cloudflare Email Routing** gratis, unlimited
- Bisa tambah **Email Workers** untuk custom logic (filter, transform, dll)
