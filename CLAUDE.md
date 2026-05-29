# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Python client for the `mobilelk.teploenergo-nn.ru` REST API — the mobile backend for Teploenergo Nizhny Novgorod (district heating utility). The HTTP log files (`teploenergo1`–`teploenergo3`, `teploenegro4`) are captured traffic from the Android app and document the API surface.

## Environment Setup

```powershell
# Activate virtualenv
.\.venv\Scripts\Activate.ps1

# Install dependencies (once requirements.txt exists)
pip install -r requirements.txt
```

Python 3.12, venv at `.venv/`.

## API Reference (from captured traffic)

Base URL: `https://mobilelk.teploenergo-nn.ru`  
Backend: Bitrix Site Manager (PHP 8.3)  
User-Agent must be: `okhttp/4.9.0`

### Authentication flow

```
POST /users/auth/
Content-Type: application/x-www-form-urlencoded

LOGIN=<email>&PASSWORD=<password>
```

Returns `Set-Cookie: PHPSESSID=...` and a JSON body containing a Bitrix `sessid` token. Both must be carried on subsequent requests: the cookie in `Cookie:` header, the `sessid` as a query parameter.

### Endpoints (all require `?sessid=<bitrix_sessid>` and `Cookie: PHPSESSID=<id>`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/bills/list/` | List all bills for the account |
| GET | `/bills/getDebt/?ls=<account_no>` | Current debt for a personal account (`ls`) |
| GET | `/accruals/listSixMonth/?ls=<account_no>` | Six-month accrual history; `ls` can be empty for the default account |
| GET | `/apartmentPu/list/` | List apartments and metering units (PU) |

All responses are gzip-compressed (`Accept-Encoding: gzip` required).

### Key observations

- `ls` is the personal account number (e.g. `7024690127`).
- The `sessid` query param is a Bitrix CSRF token, distinct from `PHPSESSID`.
- Responses are `Content-Type: text/html` even though the body is JSON (Bitrix quirk) — decode after decompression.
