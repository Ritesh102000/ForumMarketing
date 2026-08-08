# Formcraft

A self-hosted form builder. One admin, unlimited forms, three layouts, and a
Google Sheet created automatically for every form.

## The split

Two instances share one Postgres database:

| | **admin** | **public** |
|---|---|---|
| Runs | On your machine | Wherever you host it |
| Binds | `127.0.0.1:8480` | `0.0.0.0:8481` |
| Login page | Yes | **Does not exist** |
| Builder, responses, API | Yes | **Does not exist** |
| Renders a form link | Yes | Yes |
| Accepts submissions | Yes | Yes |

On the public instance the admin routes are **never registered** — there is no
login form to find, no `/admin` path, no API. People you send a form link to
see only the form.

The admin instance adds a second layer: every admin route also checks that the
request came from this machine, reading the socket peer rather than
`X-Forwarded-For` so a header cannot unlock it. Off-machine requests get a
**404**, not a 403, so the surface stays invisible.

## Look and feel

The UI is built from four CSS layers you can retheme without touching markup:

| File | Owns |
|---|---|
| `web/static/css/tokens.css` | Colour, type scale, spacing, radii, shadows |
| `web/static/css/base.css` | Reset, element defaults, utilities |
| `web/static/css/components.css` | Buttons, cards, inputs, badges, placeholders |
| `web/static/css/admin.css` / `form.css` | Page-specific layout |

Change the brand in `tokens.css` (`--brand`, `--highlight`, the two font
stacks) and every surface follows. Individual forms override `--accent` from
the builder.

Shared markup lives in `web/templates/components/ui.html` as Jinja macros —
`media()`, `brand()`, `pill()`, `trust_strip()`.

## Images

Every image slot is declared once in `src/formcraft/media.py`. Where an asset
is missing, a labelled placeholder renders **the brief for that image** — the
slot name, what it should depict, and the pixel size. Nothing breaks, and you
always know what is still to make.

Fill a slot by dropping a file into `web/static/img/`:

```
web/static/img/brand-mark.webp
web/static/img/owner-avatar.jpg
web/static/img/form-cover-creator-intake.webp    ← per-form override
```

There are 40 slots. **`/admin/media`** in the running app shows every one with
its brief, size, filename and fill status, and exports the whole list as a text
file. [PROMPTS.md](PROMPTS.md) groups them into three ready-to-paste batches.

## Setup

You need a Postgres database both instances can reach.
[neon.tech](https://neon.tech) and [supabase.com](https://supabase.com) both
have free tiers that work.

```bash
cd /Users/riteshrajput/Desktop/Dog/formcraft
uv sync
cp .env.example .env
```

Put your connection string in `.env` as `FORMCRAFT_DATABASE_URL`, then:

```bash
uv run python scripts/set_password.py
```

```bash
uv run python scripts/run.py
```

Open http://127.0.0.1:8480. Tables are created automatically on first start.

To create the ready-made business inquiry form and connect its success screen
to Calendly:

```bash
uv run python scripts/setup_business_inquiry_form.py \
  --calendly-url https://calendly.com/your-name/intro-call
```

### Try it with no database at all

```bash
uv run python scripts/dev.py
```

Boots a throwaway embedded Postgres under `data/devdb` and logs you in as
`admin` / `devpassword`. For poking around only.

### The public instance

Same repo, same `.env` except `FORMCRAFT_ROLE=public`, and no admin
credentials needed:

```bash
FORMCRAFT_ROLE=public uv run python scripts/run.py
```

To put it on the internet, see **[DEPLOY.md](DEPLOY.md)** — Vercel plus Neon,
both free tiers.

## What it does

- **Three layouts per form** — all questions on one page, one section per
  screen, or one question at a time. Set per form, changeable any time.
- **One admin, ever.** Credentials live in `.env`, not the database. No signup
  route exists, so a second account cannot be created.
- **Automatic Google Sheets.** Creating a form creates its spreadsheet and
  writes the header row. Each response appends a row.
- **Responses are never lost.** Every submission is written to Postgres first.
  If Sheets is unreachable the response is queued and retried.
- **Question types** — short text, paragraph, email, number, date, time,
  dropdown, single choice, multiple choice, linear scale, star rating.
- **Meeting handoff** — add a Calendly or other HTTPS booking link to any form;
  visitors see the booking button immediately after submitting.

## Getting the data out

Three ways, in order of how little setup they need.

**1. Download.** On any form's responses page: **Download Excel** (`.xlsx`) or
**CSV**. No Google account, no configuration, nothing to link. The workbook
comes with a frozen header row, autofilter, and sensible column widths.

**2. Live link.** Also on the responses page — generate a URL and point Excel
at it with **Data → From Web**, then hit **Refresh** whenever you want the
latest. Same idea as a linked spreadsheet, without Google.

The link is deliberately localhost-only: it is served by the admin instance and
gated on the same is-this-machine check as the rest of the admin surface, so the
key never crosses the network. The tradeoff is that refresh works only while
your admin server is running. Rotate or revoke the key any time.

**3. Google Sheets.** Direct app-to-Google integration; n8n is not involved. A
spreadsheet is created per form, existing responses are backfilled, form edits
update the headers, and new submissions append live.

Exports include questions you have since **deleted** from the form, marked
`(removed)`. Those answers still exist in past responses, and dropping the
columns would quietly lose data.

## Google Sheets (optional)

1. [console.cloud.google.com](https://console.cloud.google.com) → create or pick a project
2. **APIs & Services → Library** → enable **Google Sheets API** and **Google Drive API**
3. **OAuth consent screen** → fill in branding, then set publishing status to
   **Production** (not Testing — see the note below)
4. **Credentials → Create credentials → OAuth client ID → Desktop app**
5. Download the JSON to `data/google_client_secret.json`
6. Authorise once:

```bash
uv run python scripts/google_setup.py
```

It walks you through the console steps, runs the consent flow, then verifies by
creating a real spreadsheet and deleting it — so you find out immediately if an
API is not enabled, rather than on your first response. When the repository is
linked to Vercel, it can securely upload the refresh token and enable live sync
without printing the token or asking you to copy it.

7. Set `FORMCRAFT_GOOGLE_ENABLED=1` in `.env` and restart.

Sheets are created in *your* Drive and owned by you. The app requests only the
`drive.file` scope, so it can only touch files it created — it cannot see the
rest of your Drive. That scope is also **non-sensitive**, which means you can
publish the OAuth app to Production with no Google verification review. Do
publish it: in Testing status Google expires the refresh token after 7 days.

The local admin needs the Google credential to create and update spreadsheets.
For instant live rows, put the same token in Vercel as
`FORMCRAFT_GOOGLE_TOKEN_JSON`; otherwise responses remain queued in Postgres
and sync when you press **Retry pending** locally. Each row carries a hidden
Formcraft response ID, so a retry cannot append the same response twice.

## How it works

```
  you (local)                        everyone else
      │                                    │
  admin:8480 ──┐                    ┌── public:8481
   login       │                    │   /f/{slug} only
   builder     └──►  Postgres  ◄────┘
   responses          │
                      └──► Google Sheets (one spreadsheet per form)
```

| Path | admin | public |
|---|---|---|
| `/` | Dashboard | — |
| `/login` | Login | — |
| `/admin/new`, `/admin/{id}` | Builder | — |
| `/admin/{id}/responses` | Response table | — |
| `/admin/{id}/export.csv`, `.xlsx` | Download | — |
| `/feed/{id}.csv?key=` | Live link (localhost only) | — |
| `/f/{public_ref}` | ✓ | ✓ |
| `/healthz` | ✓ | ✓ |

### Editing a form is safe

Questions keep their IDs across edits, so existing responses and spreadsheet
columns stay attached to the right question. Deleting a question **archives**
it rather than dropping it — historical responses remain readable, and the
spreadsheet column is never reused or shifted.

### Form links are unguessable

The public URL is `/f/{public_ref}`, where `public_ref` is the slug plus a
random suffix — `creator-intake-yJ5ZmJo-gV25`. There is deliberately **no
lookup by slug**: a visitor holding one form's link cannot reach any other form
by guessing `/f/client-onboarding`.

The reference is generated once at creation and never regenerated, so renaming
a form does not break links you have already shared.

Public forms also send `X-Robots-Tag: noindex, nofollow, noarchive` and carry a
matching meta tag — an unguessable URL stops being private the moment a crawler
indexes it. The OpenAPI schema and docs routes are disabled on both instances,
since the schema would otherwise enumerate every route.

### Drafts

A form is only reachable at `/f/{slug}` once **Published** is ticked. While it
is a draft, only a logged-in admin on the local instance sees it, marked with a
preview banner. The public instance returns 404 for drafts.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FORMCRAFT_DATABASE_URL` | — | Postgres connection string. Required |
| `FORMCRAFT_DB_POOL_SIZE` | `5` | Max pooled connections |
| `FORMCRAFT_ROLE` | `admin` | `admin` or `public` |
| `FORMCRAFT_BRAND_NAME` | `Formcraft` | Shown in the header and form footer |
| `FORMCRAFT_OWNER_NAME` / `_ROLE` | — | Shows a "who is asking" card on public forms |
| `FORMCRAFT_ADMIN_ALLOW_REMOTE` | `0` | Set to `1` only behind your own authenticated proxy or VPN |
| `FORMCRAFT_ADMIN_USERNAME` | `admin` | The single admin account |
| `FORMCRAFT_ADMIN_PASSWORD_HASH` | — | Argon2 hash, set by `set_password.py` |
| `FORMCRAFT_SECRET_KEY` | — | Session cookie signing key |
| `FORMCRAFT_BASE_URL` | `http://127.0.0.1:8480` | Public address, used for share links |
| `FORMCRAFT_SECURE_COOKIES` | `0` | Set to `1` when served over HTTPS |
| `FORMCRAFT_GOOGLE_ENABLED` | `0` | Turn Sheets sync on |
| `FORMCRAFT_GOOGLE_TOKEN_JSON` | — | Token as a single line, for hosts with no writable disk |
| `FORMCRAFT_HOST` / `FORMCRAFT_PORT` | per role | Override the bind address |

## Verification

```bash
uv run pytest -q
```

Tests spin up a real embedded Postgres via `pgserver` — no setup needed. Point
`FORMCRAFT_TEST_DATABASE_URL` at your own database to test against that
instead.

```bash
uv run ruff check .
```

## Notes

Before exposing the public instance: set `FORMCRAFT_SECURE_COOKIES=1`, put it
behind TLS, and consider a reverse proxy with its own rate limiting — the
built-in login throttle is per-process and deliberately simple.
