# Deploying

Two pieces, one database.

```
   you (your Mac)                          people you send links to
        │                                            │
   admin instance                             public instance
   localhost:8480                             yourforms.vercel.app
   login · builder · responses                /f/<slug> only
        │                                            │
        └──────────────►  Neon Postgres  ◄───────────┘
                              │
                              └──► Google Sheets
```

The admin instance never leaves your machine. The public instance has no login
page — those routes are not registered when `FORMCRAFT_ROLE=public`, so there
is nothing to find and nothing to brute-force. Someone you send a link to lands
straight on the form.

---

## 1. Database — Neon (free)

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the **pooled** connection string — the host contains `-pooler`

```
postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
```

Use the pooled string on Vercel. Serverless functions open a connection per
request, and the pooler is what absorbs that churn instead of Postgres.
Formcraft detects Vercel automatically and skips its own connection pool.

Tables are created on first start. Nothing to migrate.

## 2. Local admin

```bash
cp .env.example .env
```

Set `FORMCRAFT_DATABASE_URL`, `FORMCRAFT_BRAND_NAME`, and
`FORMCRAFT_BASE_URL` (to your future Vercel URL — that is what the share links
in the dashboard will show). Then:

```bash
uv run python scripts/set_password.py
```

```bash
uv run python scripts/run.py
```

## 3. Public instance — Vercel

```bash
npm i -g vercel && vercel login
```

```bash
vercel --prod
```

`vercel.json` and the root `index.py` are already in the repo. The entrypoint forces
`FORMCRAFT_ROLE=public` and **refuses to boot** if you override it to `admin`,
so the builder cannot be published by accident.

Set these in the Vercel project (Settings → Environment Variables):

| Variable | Value |
|---|---|
| `DATABASE_URL` | the **pooled** Neon string (added automatically by Vercel's Neon integration) |
| `FORMCRAFT_ROLE` | `public` |
| `FORMCRAFT_BRAND_NAME` | your business name |
| `FORMCRAFT_BASE_URL` | `https://yourforms.vercel.app` |
| `FORMCRAFT_SECURE_COOKIES` | `1` |
| `FORMCRAFT_GOOGLE_ENABLED` | `1` (only if you want live Sheets sync) |
| `FORMCRAFT_GOOGLE_TOKEN_JSON` | printed by `scripts/google_setup.py` |

Verify: `https://yourforms.vercel.app/healthz` should report `{"ok": true}`.
The public health route deliberately hides role, database, and integration
details from visitors.

Then confirm the admin surface really is absent:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://yourforms.vercel.app/login
```

That must print `404`.

## 4. Google Sheets

```bash
uv run python scripts/google_setup.py
```

It prints the Cloud Console checklist, runs the consent flow, then **proves it
works** by creating a real spreadsheet, writing to it, and deleting it again.
Because this repository is already linked to Vercel, the script can upload the
token as a sensitive variable and enable live sync without exposing the token
in terminal output.

Two things in that checklist matter more than they look:

- **Set publishing status to Production, not Testing.** In Testing, Google
  expires the refresh token after **7 days** and your deployment silently stops
  syncing. You cannot re-authorise interactively on Vercel.
- **We request only `drive.file`.** That is a *non-sensitive* scope, so
  Production needs no verification review. The Sheets API accepts it for files
  the app created — which is all Formcraft ever touches. It cannot see the rest
  of your Drive. The "unverified app" notice on the consent screen is expected
  and fine for your own account.

### Direct live synchronization on Vercel

No n8n host is required. The public Vercel Function saves the response in
Postgres first, then appends it through the Google Sheets API. If Google is
temporarily unavailable, the response remains pending and can be retried from
the admin dashboard. A hidden response ID makes retries idempotent.

If you prefer to keep the Google credential off the public host, leave
`FORMCRAFT_GOOGLE_ENABLED=0` on Vercel and set it to `1` locally. Responses
will then appear in Sheets in batches when you press **Retry pending**.

---

## Notes and limits

**Cold starts.** The first request after idle takes 2–4 seconds while the
function boots and connects. Subsequent requests are fast. Acceptable for
forms; if it bothers you, Vercel's paid tiers keep functions warm.

**Function usage.** Vercel's free Hobby allowance is usage-capped and intended
for personal, non-commercial projects. Formcraft's short request/response work
fits the technical limits, but a business deployment should use Vercel Pro.

**Static files.** Served by the app and cached for a year via `vercel.json`.
Images you add under `web/static/img/` ship with the deployment — re-deploy
after adding one.

**Custom domain.** Add it in Vercel, then update `FORMCRAFT_BASE_URL` in *both*
places so the share links in your dashboard match reality.
