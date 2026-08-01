"""Image slots.

Every image the UI can show is declared here once. If the file exists under
`web/static/img/` it is rendered; if not, a labelled placeholder appears in its
place describing exactly what belongs there. Nothing breaks either way.

Drop a file named `<slot>.<ext>` into web/static/img to fill a slot.
See IMAGES.md for the generation briefs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import settings

EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg", ".svg", ".avif")


@dataclass(frozen=True)
class Slot:
    name: str
    label: str
    size: str
    ratio: str
    description: str
    round: bool = False


SLOTS: dict[str, Slot] = {
    "brand-mark": Slot(
        name="brand-mark",
        label="Brand mark",
        size="512×512",
        ratio="1 / 1",
        description=(
            "Square app icon. A single bold geometric glyph — a stylised 'G' or an "
            "abstract handshake/link form — in flat white on a deep indigo field. "
            "No text, no gradients, no photorealism. Must stay legible at 24px."
        ),
        round=False,
    ),
    "brand-wordmark": Slot(
        name="brand-wordmark",
        label="Wordmark",
        size="720×160",
        ratio="9 / 2",
        description=(
            "Horizontal logotype reading the business name. Tight modern geometric "
            "sans, medium weight, generous letter-spacing. Transparent background, "
            "single flat colour so it inverts cleanly in dark mode."
        ),
    ),
    "login-panel": Slot(
        name="login-panel",
        label="Sign-in panel",
        size="1200×1600",
        ratio="3 / 4",
        description=(
            "Editorial portrait image for the sign-in screen. Moody, warm-lit "
            "workspace scene — a creator reviewing a contract on a laptop, shot "
            "over-the-shoulder, shallow depth of field. Deep indigo and amber "
            "colour grade. No readable text on screens. Leaves the upper third "
            "visually quiet for an overlaid quote."
        ),
    ),
    "dashboard-empty": Slot(
        name="dashboard-empty",
        label="Empty dashboard",
        size="800×600",
        ratio="4 / 3",
        description=(
            "Flat vector spot illustration: a stack of floating form cards with "
            "one lifting away, plus a small spreadsheet grid connected by a thin "
            "line. Two-colour — indigo and warm amber — on transparent. Clean "
            "line weights, no drop shadows, no text."
        ),
    ),
    "form-cover": Slot(
        name="form-cover",
        label="Form cover",
        size="1600×600",
        ratio="8 / 3",
        description=(
            "Wide banner across the top of a public form. Abstract soft-gradient "
            "mesh in indigo → magenta → amber with subtle film grain. No subject "
            "matter, no text — it sits behind the form title, so keep it low "
            "contrast and calm. Per-form override: name the file "
            "`form-cover-<slug>.webp`."
        ),
    ),
    "owner-avatar": Slot(
        name="owner-avatar",
        label="Owner headshot",
        size="400×400",
        ratio="1 / 1",
        description=(
            "Square professional headshot of the person sending the form. Natural "
            "light, neutral background, shoulders-up, warm and approachable rather "
            "than corporate. Centre the face — it renders as a circle."
        ),
        round=True,
    ),
    "trust-logo-1": Slot(
        name="trust-logo-1",
        label="Client logo 1",
        size="240×80",
        ratio="3 / 1",
        description=(
            "Monochrome client or partner logo for the trust strip. Transparent "
            "background, single flat colour, generous padding. Rendered greyscale "
            "at 26px tall."
        ),
    ),
    "trust-logo-2": Slot(
        name="trust-logo-2",
        label="Client logo 2",
        size="240×80",
        ratio="3 / 1",
        description=(
            "Second client or partner logo. Monochrome, transparent background, "
            "single flat colour, generous padding. Rendered greyscale at 26px "
            "tall, so colour and fine detail are wasted here."
        ),
    ),
    "trust-logo-3": Slot(
        name="trust-logo-3",
        label="Client logo 3",
        size="240×80",
        ratio="3 / 1",
        description=(
            "Third client or partner logo. Monochrome, transparent background, "
            "single flat colour, generous padding. Match the optical weight of "
            "the other three so the strip reads evenly."
        ),
    ),
    "trust-logo-4": Slot(
        name="trust-logo-4",
        label="Client logo 4",
        size="240×80",
        ratio="3 / 1",
        description=(
            "Fourth client or partner logo. Monochrome, transparent background, "
            "single flat colour, generous padding. Leave this slot empty rather "
            "than filling it with a weak logo — three strong marks beat four."
        ),
    ),
    "form-success": Slot(
        name="form-success",
        label="Submitted state",
        size="600×600",
        ratio="1 / 1",
        description=(
            "Flat vector spot illustration for the thank-you screen: a paper plane "
            "arcing upward with a light dotted trail, or an envelope dissolving "
            "into small particles. Two-colour indigo and amber on transparent. "
            "Optimistic, restrained, no confetti clichés, no text."
        ),
    ),
    "not-found": Slot(
        name="not-found",
        label="Form not available",
        size="800×600",
        ratio="4 / 3",
        description=(
            "Flat vector spot illustration for a broken or expired form link: "
            "an unplugged cable end, or a paper aeroplane that has folded flat. "
            "Two-colour indigo and amber on transparent. Sympathetic rather "
            "than alarming — this is usually a typo, not a failure."
        ),
    ),
    "responses-empty": Slot(
        name="responses-empty",
        label="No responses yet",
        size="800×600",
        ratio="4 / 3",
        description=(
            "Flat vector spot illustration: an empty inbox tray with one faint "
            "dotted outline of a card hovering above it, suggesting the first "
            "response is on its way. Indigo and amber, transparent, no text."
        ),
    ),
    "builder-empty": Slot(
        name="builder-empty",
        label="Empty builder canvas",
        size="640×480",
        ratio="4 / 3",
        description=(
            "Small flat vector illustration: three stacked blank input-field "
            "shapes with a plus sign hovering over the top one. Line-art "
            "weight, indigo only, transparent background."
        ),
    ),
    "favicon": Slot(
        name="favicon",
        label="Browser tab icon",
        size="256×256",
        ratio="1 / 1",
        description=(
            "The brand mark rendered for a 16px browser tab: one solid shape, "
            "maximum contrast, no fine detail, no text. Flat white on deep "
            "indigo, square with slightly rounded corners."
        ),
    ),
    "texture-grain": Slot(
        name="texture-grain",
        label="Background texture",
        size="1200×1200",
        ratio="1 / 1",
        description=(
            "Seamless tileable subtle noise/grain texture, near-transparent, "
            "monochrome. Used at very low opacity behind large surfaces to "
            "stop flat colour looking digital. No pattern or motif."
        ),
    ),
    "testimonial-1": Slot(
        name="testimonial-1",
        label="Testimonial portrait 1",
        size="400×400",
        ratio="1 / 1",
        description=(
            "Square portrait of a real creator who agreed to be quoted. Natural "
            "light, neutral background, warm and candid. Use a real person — "
            "a generated face next to a real quote is a trust problem."
        ),
        round=True,
    ),
    "testimonial-2": Slot(
        name="testimonial-2",
        label="Testimonial portrait 2",
        size="400×400",
        ratio="1 / 1",
        description="Second testimonial portrait. Square, natural light, neutral "
            "background, candid rather than posed. Choose a different setting "
            "and skin tone from the first so the row reads as a real range of "
            "people. Must be a real person who agreed to be quoted.",
        round=True,
    ),
    "testimonial-3": Slot(
        name="testimonial-3",
        label="Testimonial portrait 3",
        size="400×400",
        ratio="1 / 1",
        description="Third testimonial portrait. Square, natural light, neutral "
            "background, candid. Vary the age and setting again — three "
            "near-identical portraits read as stock and undo the trust the "
            "row is there to build.",
        round=True,
    ),
    "form-cover-warm": Slot(
        name="form-cover-warm",
        label="Cover variant — warm",
        size="1600×600",
        ratio="8 / 3",
        description=(
            "Alternate form banner. Amber to coral to soft rose. Sunrise warmth, "
            "inviting — suits intake and welcome forms. "
            "Abstract gradient mesh with film grain, no subject matter, no "
            "text — a form title sits over it. Copy to "
            "form-cover-<public-ref>.webp to use on a specific form."
        ),
    ),
    "form-cover-cool": Slot(
        name="form-cover-cool",
        label="Cover variant — cool",
        size="1600×600",
        ratio="8 / 3",
        description=(
            "Alternate form banner. Indigo to teal to pale cyan. Calm and clinical "
            "— suits feedback and survey forms. "
            "Abstract gradient mesh with film grain, no subject matter, no "
            "text — a form title sits over it. Copy to "
            "form-cover-<public-ref>.webp to use on a specific form."
        ),
    ),
    "form-cover-mono": Slot(
        name="form-cover-mono",
        label="Cover variant — mono",
        size="1600×600",
        ratio="8 / 3",
        description=(
            "Alternate form banner. Greyscale only, from near-black to bone. "
            "Editorial and serious — suits contracts and formal onboarding. "
            "Abstract gradient mesh with film grain, no subject matter, no "
            "text — a form title sits over it. Copy to "
            "form-cover-<public-ref>.webp to use on a specific form."
        ),
    ),
    "form-cover-bold": Slot(
        name="form-cover-bold",
        label="Cover variant — bold",
        size="1600×600",
        ratio="8 / 3",
        description=(
            "Alternate form banner. High-contrast indigo against hot magenta, "
            "harder edges between colour fields. Energetic — suits launches and "
            "campaigns. "
            "Abstract gradient mesh with film grain, no subject matter, no "
            "text — a form title sits over it. Copy to "
            "form-cover-<public-ref>.webp to use on a specific form."
        ),
    ),
    "case-study-1": Slot(
        name="case-study-1",
        label="Case study 1",
        size="1200×800",
        ratio="3 / 2",
        description=(
            "Editorial photo for a client result card. A creator at work in their own "
            "space — filming, editing, packing product. Documentary feel, natural "
            "light, warm grade. Real work, not a posed portrait."
        ),
    ),
    "case-study-2": Slot(
        name="case-study-2",
        label="Case study 2",
        size="1200×800",
        ratio="3 / 2",
        description=(
            "Second client result card. Different creator, different setting and time "
            "of day, so the set reads as a range of people rather than one shoot."
        ),
    ),
    "case-study-3": Slot(
        name="case-study-3",
        label="Case study 3",
        size="1200×800",
        ratio="3 / 2",
        description=(
            "Third client result card. Same documentary treatment; vary the craft "
            "shown again."
        ),
    ),
    "process-1": Slot(
        name="process-1",
        label="Process step 1",
        size="600×600",
        ratio="1 / 1",
        description=(
            "Flat vector icon-illustration for step one, Audit: a magnifying glass "
            "over a profile card with three small metric bars. Indigo with one amber "
            "highlight, transparent, no text."
        ),
    ),
    "process-2": Slot(
        name="process-2",
        label="Process step 2",
        size="600×600",
        ratio="1 / 1",
        description=(
            "Step two, Position: two cards being reordered, one lifting above the "
            "other with a small upward arrow. Same treatment as step one."
        ),
    ),
    "process-3": Slot(
        name="process-3",
        label="Process step 3",
        size="600×600",
        ratio="1 / 1",
        description=(
            "Step three, Pitch: an envelope leaving a stack toward a distant brand "
            "shape. Same treatment as steps one and two."
        ),
    ),
    "team-photo": Slot(
        name="team-photo",
        label="Team photo",
        size="1600×1000",
        ratio="8 / 5",
        description=(
            "Wide candid shot of the team mid-conversation, not lined up for camera. "
            "Natural light, real room, slightly warm grade. Leave space on one side "
            "for overlaid copy."
        ),
    ),
    "office-detail": Slot(
        name="office-detail",
        label="Atmosphere detail",
        size="1200×1200",
        ratio="1 / 1",
        description=(
            "Close crop of a working surface — notebook, laptop corner, coffee, "
            "cables. Shallow depth of field, warm light. Used as a texture break "
            "between sections; must work heavily cropped."
        ),
    ),
    "stat-backdrop": Slot(
        name="stat-backdrop",
        label="Statistic backdrop",
        size="1200×600",
        ratio="2 / 1",
        description=(
            "Very low-contrast abstract backdrop for large numbers laid over it. Deep "
            "indigo with a faint diagonal light sweep. Almost nothing happening — the "
            "numbers are the subject."
        ),
    ),
    "email-header": Slot(
        name="email-header",
        label="Email banner",
        size="1200×400",
        ratio="3 / 1",
        description=(
            "Banner for the top of an email. Deep indigo field, the abstract mark "
            "small and left-aligned, a soft amber gradient bleeding in from the right "
            "edge. No text — subject lines carry that."
        ),
    ),
    "deck-cover": Slot(
        name="deck-cover",
        label="Proposal cover",
        size="1600×900",
        ratio="16 / 9",
        description=(
            "Cover image for a pitch deck or proposal PDF. Abstract indigo-to-magenta "
            "mesh with a strong diagonal, more dramatic than the form banners since "
            "nothing overlays the top half. No text."
        ),
    ),
    "avatar-fallback": Slot(
        name="avatar-fallback",
        label="Default avatar",
        size="400×400",
        ratio="1 / 1",
        description=(
            "Neutral placeholder shown when someone has no photo. Simple geometric "
            "silhouette, flat indigo on a pale tint. Deliberately generic — it must "
            "not read as a specific person."
        ),
        round=True,
    ),
    "pattern-grid": Slot(
        name="pattern-grid",
        label="Grid backdrop",
        size="1200×1200",
        ratio="1 / 1",
        description=(
            "Seamless tileable technical grid: thin indigo lines at low opacity on "
            "transparent, with slightly heavier lines every fifth. Blueprint feel. "
            "Must tile invisibly."
        ),
    ),
    "seal-verified": Slot(
        name="seal-verified",
        label="Trust seal",
        size="400×400",
        ratio="1 / 1",
        description=(
            "Small circular badge mark suggesting verification — a ring with a check "
            "or laurel form inside. Single flat colour, no text, no ribbons. Reads "
            "clearly at 40px."
        ),
    ),
    "og-form": Slot(
        name="og-form",
        label="Form social card",
        size="1200×630",
        ratio="40 / 21",
        description=(
            "Alternate link-preview card with a warmer treatment than og-default, for "
            "forms sent to creators rather than clients. Amber gradient corner on "
            "deep indigo. Centre left empty for the composited title."
        ),
    ),
    "signature": Slot(
        name="signature",
        label="Signature",
        size="600×200",
        ratio="3 / 1",
        description=(
            "Handwritten signature in a single flat dark colour on transparent, ink "
            "pen weight with natural variation. Should be an actual scan of the "
            "sender's signature — a generated one on a business document is a "
            "misrepresentation risk."
        ),
    ),
    "og-default": Slot(
        name="og-default",
        label="Social preview",
        size="1200×630",
        ratio="40 / 21",
        description=(
            "Link preview card shown when a form URL is shared. Deep indigo "
            "background, the wordmark centred in the upper left, generous negative "
            "space in the lower two thirds. Subtle mesh gradient in one corner. "
            "Leave the centre clear — the form title is composited over it."
        ),
    ),
}


def resolve(slot_name: str, variant: str = "") -> str | None:
    """Return the public URL for a slot, or None when no asset exists yet.

    `variant` allows a per-form override, e.g. form-cover-creator-intake.
    """
    img_dir = settings.web_dir / "static" / "img"
    candidates = [f"{slot_name}-{variant}"] if variant else []
    candidates.append(slot_name)

    for stem in candidates:
        for ext in EXTENSIONS:
            if (img_dir / f"{stem}{ext}").is_file():
                return f"/static/img/{stem}{ext}"
    return None


_ASSET_HASHES: dict[str, str] = {}


def static_url(path: str) -> str:
    """/static/<path> with a content fingerprint appended.

    Without this, a deploy can leave visitors running cached JS against new
    templates — and the Vercel config marks /static immutable, so the stale
    copy would stick. The fingerprint changes only when the file changes.
    """
    if path not in _ASSET_HASHES:
        target = settings.web_dir / "static" / path
        try:
            stat = target.stat()
            _ASSET_HASHES[path] = f"{int(stat.st_mtime):x}{stat.st_size:x}"
        except OSError:
            _ASSET_HASHES[path] = "0"
    return f"/static/{path}?v={_ASSET_HASHES[path]}"


def briefs() -> str:
    """Every outstanding brief as plain text, ready to paste into a model."""
    lines = [
        "FORMCRAFT IMAGE BRIEFS",
        "Save each file to web/static/img/<slot>.webp",
        "Never render text inside an image — all copy is live HTML on top.",
        "",
    ]
    for name, slot in SLOTS.items():
        status = "FILLED" if resolve(name) else "MISSING"
        lines += [
            f"[{status}] {name}.webp — {slot.size}, ratio {slot.ratio}",
            f"  {slot.label}",
            f"  {' '.join(slot.description.split())}",
            "",
        ]
    return "\n".join(lines)


def context() -> dict[str, Any]:
    """Injected into every template render."""
    return {"slots": SLOTS, "media_url": resolve, "static_url": static_url}
