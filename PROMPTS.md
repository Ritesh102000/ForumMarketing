# Image generation prompts

40 slots. Save each result to `web/static/img/<slot>.webp` — the app swaps the
placeholder for your image on the next page load. No restart, no code change.

Track progress at **`/admin/media`** in the running app, or grab the live list
with current filled/missing status from **Download all briefs** on that page.

Three batches below, one per visual treatment. Prompt them separately —
mixing vector and photographic direction in one request muddies both.

---

## Shared style header

Put this at the top of every batch.

```
STYLE — applies to every image in this batch:
Palette: deep indigo #4F46E5 anchors everything, warm amber #F0A03C is the
single accent, neutral greys otherwise. Never introduce a third hue.
NEVER render text, letterforms, numbers, or words inside any image — every
label in the product is live HTML composited on top.
Export WebP.
```

---

## Batch 1 — Flat vector (15 images)

```
Flat vector illustration. Two colours only, transparent background, even line
weights, no drop shadows, no gradients inside shapes, no 3D, no skeuomorphism.
Clean geometric construction. Generate:

1.  brand-mark.webp        512×512  — Bold geometric glyph, flat white on deep
    indigo. Abstract link or handshake form. Legible at 24px.
2.  brand-wordmark.webp    720×160  — Horizontal abstract mark, one flat colour,
    transparent. Inverts cleanly for dark mode.
3.  favicon.webp           256×256  — The mark reduced for a 16px tab. One solid
    shape, maximum contrast, zero fine detail.
4.  dashboard-empty.webp   800×600  — Stack of floating form cards, one lifting
    away, thin line connecting to a small spreadsheet grid.
5.  form-success.webp      600×600  — Paper plane arcing upward with a light
    dotted trail. Optimistic, restrained, no confetti.
6.  not-found.webp         800×600  — An unplugged cable end, or a paper plane
    folded flat. Sympathetic, not alarming — this is usually a typo.
7.  responses-empty.webp   800×600  — Empty inbox tray with one faint dotted
    card outline hovering above it.
8.  builder-empty.webp     640×480  — Three stacked blank input-field shapes,
    plus sign hovering over the top one. Line-art weight, indigo only.
9.  process-1.webp         600×600  — AUDIT: magnifying glass over a profile
    card with three small metric bars.
10. process-2.webp         600×600  — POSITION: two cards being reordered, one
    lifting above the other with a small upward arrow.
11. process-3.webp         600×600  — PITCH: an envelope leaving a stack toward
    a distant brand shape.
12. seal-verified.webp     400×400  — Circular badge: a ring with a check or
    laurel form inside. One flat colour. Reads at 40px.
13. avatar-fallback.webp   400×400  — Neutral geometric silhouette, flat indigo
    on pale tint. Deliberately generic — must not read as a specific person.
14. pattern-grid.webp      1200×1200 — Seamless tileable technical grid. Thin
    indigo lines at low opacity, heavier every fifth. Must tile invisibly.
15. texture-grain.webp     1200×1200 — Seamless tileable noise, near
    transparent, monochrome. No motif. Used at very low opacity.
```

## Batch 2 — Gradient fields (10 images)

```
Abstract gradient mesh with subtle film grain. No subject matter, no objects,
no horizon. These sit BEHIND text, so keep contrast low and the composition
calm — the eye should pass over them. Generate:

16. form-cover.webp        1600×600  — Indigo → magenta → amber. The default
    banner across the top of a form.
17. form-cover-warm.webp   1600×600  — Amber → coral → soft rose. Sunrise
    warmth. For intake and welcome forms.
18. form-cover-cool.webp   1600×600  — Indigo → teal → pale cyan. Calm and
    clinical. For feedback and surveys.
19. form-cover-mono.webp   1600×600  — Greyscale only, near-black to bone.
    Editorial. For contracts and formal onboarding.
20. form-cover-bold.webp   1600×600  — Indigo against hot magenta, harder edges
    between colour fields. Energetic. For launches.
21. og-default.webp        1200×630  — Deep indigo, subtle mesh in one corner,
    abstract mark small upper-left. Centre and lower two thirds EMPTY.
22. og-form.webp           1200×630  — Warmer variant of the above, amber
    gradient corner. For forms sent to creators rather than clients.
23. stat-backdrop.webp     1200×600  — Deep indigo with a faint diagonal light
    sweep. Almost nothing happening — large numbers sit over it.
24. email-header.webp      1200×400  — Deep indigo field, abstract mark small
    and left-aligned, soft amber bleeding in from the right edge.
25. deck-cover.webp        1600×900  — Indigo → magenta mesh with a strong
    diagonal. More dramatic than the form banners; nothing overlays the top.
```

## Batch 3 — Photographic (6 images)

```
Documentary photography. Natural light, shallow depth of field, warm colour
grade. Real working environments, candid moments — not posed stock scenes, not
handshakes, not people pointing at laptops. Screens must be unreadable. Vary
the people across the set. Generate:

26. login-panel.webp    1200×1600 portrait — Over-the-shoulder: a creator
    reviewing a contract on a laptop in a warm-lit room. Keep the bottom third
    visually calm; a quote is overlaid there.
27. case-study-1.webp   1200×800 — A creator at work in their own space:
    filming, editing, or packing product.
28. case-study-2.webp   1200×800 — Different creator, different setting and
    time of day, different craft.
29. case-study-3.webp   1200×800 — Third creator. Vary age, setting and craft
    again so the set reads as a real range of people.
30. team-photo.webp     1600×1000 — The team mid-conversation, not lined up for
    camera. Leave clear space on one side for overlaid copy.
31. office-detail.webp  1200×1200 — Close crop of a working surface: notebook,
    laptop corner, coffee, cables. Must work heavily cropped.
```

---

## Do not generate these 9

They need real assets. A generated stand-in here is the thing that backfires
if anyone notices.

| Slot | Why |
|---|---|
| `owner-avatar` | A real headshot of whoever sends the forms. Highest-trust element on the page. |
| `testimonial-1`, `-2`, `-3` | Real people who agreed to be quoted. A synthetic face beside a real quote is a trust problem. |
| `trust-logo-1` … `-4` | Real client logos you have permission to display. |
| `signature` | A scan of the sender's actual signature. A generated one on a business document is a misrepresentation risk. |

---

## Per-form covers

Any form can override the shared banner. Copy whichever variant suits it:

```bash
cp web/static/img/form-cover-warm.webp \
   web/static/img/form-cover-creator-intake-yJ5ZmJo-gV25.webp
```

The builder sidebar shows the exact filename for whichever form is open.
