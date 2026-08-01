# UI review prompt

Paste the block below into an LLM. Attach, in this order:

1. Screenshots — dashboard, builder, responses page, a public form in each of
   the three layout modes, and one mobile shot
2. `web/static/css/tokens.css` and `components.css`
3. One template, e.g. `web/templates/form.html`

Without the screenshots you get generic advice. The prompt is written to make
generic advice hard to give.

---

```
You are reviewing the UI of a working product. I want specific, applicable
changes — not design principles I already know.

## What it is

A self-hosted form builder used by a small agency that sells brand-partnership
coaching to content creators. Think Typeform, but private and self-hosted.

Two surfaces, with opposite jobs:

SURFACE A — Admin. Dashboard, form builder, response table. One person, daily,
on a desktop, often for long stretches. Should feel like a tool: dense,
fast, forgettable. Nobody needs to be impressed.

SURFACE B — Public form. A creator with 50k+ followers opens a link they were
sent, fills it in once, on a phone about 60% of the time, and never returns.
This is a first impression from a business asking them to hand over contact
details and revenue numbers. It has to feel credible and low-friction.
Everything here is judged on: does this look like a real company, and how
fast can I get out.

The public form has three layouts, set per form:
  - single: every question on one page
  - section: one section per screen, with Back/Continue
  - one_by_one: one question per screen, Typeform style

## Current design system

Tokens live in tokens.css:
  --brand #4F46E5 (indigo), --highlight #F0A03C (amber), --accent per-form,
  overridable by the form author
  Type: system sans for UI, serif display for headings
  Modular scale --step--1 to --step-5, spacing --sp-1 to --sp-8
  Radii --r-sm 8px to --r-pill, three shadow levels
  Full light and dark via prefers-color-scheme

CSS is layered: tokens → base → components → admin/form. Shared markup is
Jinja macros in components/ui.html.

## Hard constraints — do not suggest working around these

- No external network requests at all. No Google Fonts, no CDN, no icon
  libraries, no analytics. Self-hosted or system-native only.
- No frontend framework. Vanilla JS and server-rendered Jinja. Do not suggest
  React, Tailwind, or a component library.
- Light and dark must both work. Not a nice-to-have.
- The per-form --accent is author-controlled and can be any hue, including
  ones that clash with the amber highlight. Anything you propose must survive
  a bad accent choice.
- Images are optional. Every image slot may be empty, and the page must look
  deliberate when it is — not broken, and not full of holes.

## Already known — do not spend the review on these

- Font stack declares "Inter" and "Playfair Display" but never loads them, so
  most machines fall back to system sans and Georgia. I know. Tell me whether
  to self-host them or commit to a system stack, and which.
- Placeholder blocks for missing images are intentionally visible in dev.
- Google Sheets UI is hidden by default. Ignore it.

## What I want back

For each surface, in priority order, at most 8 items total:

1. The single highest-impact change, and why it matters for THAT surface's job
   (a tool, versus a first impression). If your answer would apply equally to
   both surfaces, it is too generic — cut it.
2. For every item: the specific CSS property or markup change, not a
   principle. "Increase --step-1 to 1.125rem and tighten .field gap to 8px"
   beats "improve visual hierarchy".
3. Flag anything actively working against conversion on the public form —
   friction, hesitation, anything that reads as amateur or untrustworthy to
   someone deciding whether to share their income numbers.
4. Call out anything that will break: at 320px width, in dark mode, with a
   clashing accent colour, or with all images missing.

Then, separately: three things you would NOT change, and why. I want to know
what is already working so I do not break it.

Be blunt. If something looks amateur, say so and say exactly why.
```

---

## Getting more out of it

**Ask for one surface at a time.** The admin and the public form have opposite
goals, and reviews that cover both tend to average into mush.

**Feed it the failure cases too.** Screenshot a form with a lime-green accent,
one at 320px, and one with zero images filled. Those are where the design
actually breaks, and a reviewer looking only at the happy path will miss it.

**Push back on anything that needs a network request.** Models default to
suggesting Google Fonts and icon libraries. The constraint block above heads
most of it off, but not all.
