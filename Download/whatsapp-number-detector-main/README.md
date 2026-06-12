# WhatsApp CSV Automation (Local)

Local web app to upload a lead CSV, generate WhatsApp links, optionally send WhatsApp Cloud API messages, and download processed CSV output.

## Features

- CSV upload with validation (`name`, `email`, `phone`, `website`, `whatsapp` required)
- Stream-based CSV processing for large files (1000+ rows)
- Phone/WhatsApp normalization to international format
- `wa_link` generation (`https://wa.me/<number>`)
- Optional WhatsApp Business Cloud API send with retry support
- Progress tracking (`processedRows / totalRows`)
- Download full output or filtered output (`sent`, `failed`, `skipped`)
- Local logging to console and `logs/app.log`

## Project Structure

```
/client
/server
/controllers
/routes
/services
/utils
.env
```

## Setup

1. Install dependencies:

```bash
npm install
```

2. Configure environment:

```bash
copy .env.example .env
```

3. Update `.env` values for WhatsApp Cloud API if sending is needed:

- `WA_PHONE_NUMBER_ID`
- `WA_ACCESS_TOKEN`
- `ENABLE_WHATSAPP_SEND=true`

4. Start server:

```bash
npm run dev
```

5. Open in browser:

`http://localhost:4000`

## Input CSV Columns

- `name`
- `email`
- `phone`
- `website`
- `whatsapp`

## Output CSV Columns

- `name`
- `email`
- `phone`
- `website`
- `whatsapp`
- `wa_link`
- `status` (`sent`, `failed`, `skipped`)

## Notes

- If `whatsapp` is empty, the system falls back to `phone`.
- If `sendMessages` is not enabled in UI or env, rows are marked as `skipped` (unless number is invalid).
- Invalid numbers are marked as `failed`.