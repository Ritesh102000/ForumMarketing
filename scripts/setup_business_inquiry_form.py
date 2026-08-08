"""Create or update the ready-to-share business inquiry form."""

from __future__ import annotations

import argparse

from formcraft import db, repository, sheets
from formcraft.app import _attach_sheet
from formcraft.config import settings
from formcraft.models import FormIn

FORM_TITLE = "Business Inquiry & Meeting"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--calendly-url",
        default="",
        help="Your complete Calendly event URL, such as https://calendly.com/name/intro",
    )
    return parser.parse_args()


def _payload(existing: dict | None, calendly_url: str) -> FormIn:
    old_questions = {
        question["label"]: question for question in (existing or {}).get("questions", [])
    }
    old_sections = {
        section["title"]: section for section in (existing or {}).get("sections", [])
    }

    definitions = [
        {
            "type": "short_text",
            "label": "Name",
            "placeholder": "Your full name",
            "required": True,
        },
        {
            "type": "email",
            "label": "Email",
            "placeholder": "you@business.com",
            "required": True,
        },
        {
            "type": "short_text",
            "label": "Business name",
            "placeholder": "Your business or brand name",
            "required": True,
        },
        {
            "type": "long_text",
            "label": "Business description",
            "help_text": "Briefly tell us what your business does.",
            "placeholder": "What do you sell, and who do you help?",
            "required": True,
        },
        {
            "type": "long_text",
            "label": "Main business problem",
            "help_text": "Keep it short—what is the biggest problem you want help solving?",
            "placeholder": "The main issue is…",
            "required": True,
        },
        {
            "type": "radio",
            "label": "Budget currency",
            "options": ["US Dollar ($)", "Indian Rupee (₹)"],
            "required": True,
        },
        {
            "type": "number",
            "label": "Approximate budget",
            "help_text": "Enter the amount in the currency selected above.",
            "placeholder": "e.g. 1000 or 50000",
            "required": True,
            "config": {"min": 0},
        },
        {
            "type": "short_text",
            "label": "Calendly booking status",
            "required": False,
            "config": {"hidden": True, "calendly_field": "status"},
        },
        {
            "type": "short_text",
            "label": "Calendly event URI",
            "required": False,
            "config": {"hidden": True, "calendly_field": "event_uri"},
        },
        {
            "type": "short_text",
            "label": "Calendly invitee URI",
            "required": False,
            "config": {"hidden": True, "calendly_field": "invitee_uri"},
        },
        {
            "type": "short_text",
            "label": "Calendly booking completed at",
            "required": False,
            "config": {"hidden": True, "calendly_field": "completed_at"},
        },
    ]

    questions = []
    for definition in definitions:
        question = dict(definition)
        if old := old_questions.get(question["label"]):
            question["id"] = old["id"]
        questions.append(question)

    section = {
        "title": "Tell us about your business",
        "description": "Share a few details, then book an available meeting slot below.",
        "questions": questions,
    }
    if old := old_sections.get(section["title"]):
        section["id"] = old["id"]

    saved_meeting_url = (existing or {}).get("meeting_url", "")
    return FormIn.model_validate(
        {
            "title": FORM_TITLE,
            "description": (
                "Tell us about your business, the problem you want to solve, "
                "and your approximate budget, then book an available time."
            ),
            "display_mode": "section",
            "accent": "#4f46e5",
            "is_published": True,
            "confirm_msg": "Thanks—your details and meeting are confirmed.",
            "meeting_url": calendly_url or saved_meeting_url,
            "meeting_label": "Choose a time in Calendly",
            "sections": [section],
        }
    )


def main() -> None:
    args = _arguments()
    db.init_db()
    existing_summary = next(
        (form for form in repository.list_forms() if form["title"] == FORM_TITLE), None
    )
    existing = (
        repository.get_form(form_id=existing_summary["id"])
        if existing_summary
        else None
    )
    payload = _payload(existing, args.calendly_url)

    if existing:
        form_id = existing["id"]
        repository.update_form(form_id, payload)
        action = "Updated"
    else:
        form_id = repository.create_form(payload)
        action = "Created"

    form = repository.get_form(form_id=form_id)
    if form is None:
        raise RuntimeError("The form was saved but could not be reloaded.")

    print(f"{action}: {form['title']}")
    print(f"Public form: {settings.base_url}/f/{form['public_ref']}")
    if form["meeting_url"]:
        print(f"Calendly: {form['meeting_url']}")
    else:
        print("Calendly: not set—paste the link in Form settings > Meeting link")

    if form.get("sheet_id"):
        form["sheet_questions"] = form["questions"]
        sheets.sync_spreadsheet(form)
        sheet = {"url": form["sheet_url"]}
    else:
        sheet = _attach_sheet(form_id, include_archived=False)
    print(f"Google Sheet: {sheet.get('url') or sheet.get('detail')}")


if __name__ == "__main__":
    main()
