# Image slots

Every image in the UI is declared once in [`src/formcraft/media.py`](src/formcraft/media.py).
If the file exists, it renders. If not, a labelled dashed placeholder appears in
its place showing the slot name, the brief, and the target size. Nothing breaks
either way, so you can ship without any images and fill them in over time.

## How to fill a slot

Save the file as `web/static/img/<slot>.<ext>` — `.webp`, `.png`, `.jpg`,
`.svg` and `.avif` are all picked up, in that order of preference. No code
change, no restart needed beyond a refresh.

```
web/static/img/brand-mark.webp
web/static/img/owner-avatar.jpg
web/static/img/form-cover-creator-intake.webp    ← per-form override
```

## Art direction

One system, so the surfaces feel like one product:

- **Palette** — deep indigo `#4f46e5` as the anchor, warm amber `#f0a03c` as the
  single accent. Everything else neutral.
- **Illustrations** — flat vector, two colours, transparent background, even
  line weights. No drop shadows, no gradients inside illustrations, no text.
- **Photography** — natural light, shallow depth of field, warm grade. Real
  workspaces, not stock-photo handshakes.
- **Never render text inside an image.** Titles are live HTML on top.

## The briefs

All 40 briefs live in one place and are generated from the code, so they cannot
drift:

- **In the app** — `/admin/media` shows every slot with its brief, target size,
  exact filename, and whether it is filled yet.
- **As a file** — **Download all briefs** on that page exports the current list
  with MISSING/FILLED status.
- **As prompts** — [PROMPTS.md](PROMPTS.md) groups them into three batches by
  visual treatment, ready to paste into an image model.

## Adding a new slot

Add an entry to `SLOTS` in `src/formcraft/media.py`, then drop it into a
template:

```jinja
{% from "components/ui.html" import media %}
{{ media("your-slot", slots, media_url) }}
```

The placeholder renders itself from the `description` you wrote, and the slot
appears in the gallery automatically.
