"""Create or refresh the two Formcraft forms used by Catapult.

This is intentionally idempotent: re-running it preserves form references,
question IDs, existing responses, and linked spreadsheet columns.
"""

from __future__ import annotations

import json
from typing import Any

from formcraft import repository
from formcraft.app import _attach_sheet, _sync_sheet
from formcraft.models import FormIn

COMMON_QUESTIONS = [
    {"type": "short_text", "label": "Name", "required": True},
    {"type": "email", "label": "Email"},
    {"type": "short_text", "label": "Phone"},
    {"type": "short_text", "label": "Business name"},
    {"type": "short_text", "label": "Website"},
    {"type": "long_text", "label": "Main goal", "required": True},
    {"type": "short_text", "label": "Budget"},
    {"type": "short_text", "label": "Timeline"},
    {"type": "long_text", "label": "Additional context"},
    {"type": "long_text", "label": "Diagnostic answers"},
    {"type": "long_text", "label": "Attribution"},
    {
        "type": "checkbox",
        "label": "Consent",
        "required": True,
        "options": ["Agreed", "Not agreed"],
    },
    {"type": "short_text", "label": "Source", "required": True},
]

FORMS = {
    "contact": {
        "title": "Catapult — Strategy Brief",
        "description": "Growth and infrastructure enquiries submitted from Catapult.",
        "confirm_msg": "Your brief is in. We will respond within 24 hours.",
        "diagnostic_required": False,
    },
    "diagnostic": {
        "title": "Catapult — Growth Diagnostic",
        "description": "Qualified diagnostic enquiries submitted from Catapult.",
        "confirm_msg": "Your diagnostic is in. We will respond within 24 hours.",
        "diagnostic_required": True,
    },
}


def _payload(spec: dict[str, Any], existing: dict[str, Any] | None) -> FormIn:
    old_questions = {
        question["label"]: question for question in (existing or {}).get("questions", [])
    }
    questions: list[dict[str, Any]] = []
    for definition in COMMON_QUESTIONS:
        question = dict(definition)
        if question["label"] == "Diagnostic answers":
            question["required"] = spec["diagnostic_required"]
        old = old_questions.get(question["label"])
        if old:
            question["id"] = old["id"]
        questions.append(question)

    old_sections = {
        section["title"]: section for section in (existing or {}).get("sections", [])
    }
    section: dict[str, Any] = {
        "title": "Growth enquiry",
        "description": "Contact, business context, and attribution captured together.",
        "questions": questions,
    }
    if old := old_sections.get(section["title"]):
        section["id"] = old["id"]

    return FormIn.model_validate(
        {
            "title": spec["title"],
            "description": spec["description"],
            "display_mode": "section",
            "accent": "#D9431F",
            "is_published": True,
            "confirm_msg": spec["confirm_msg"],
            "sections": [section],
        }
    )


def main() -> None:
    current = {form["title"]: form for form in repository.list_forms()}
    result: dict[str, Any] = {}

    for kind, spec in FORMS.items():
        summary = current.get(spec["title"])
        existing = repository.get_form(form_id=summary["id"]) if summary else None
        payload = _payload(spec, existing)
        if existing:
            form_id = existing["id"]
            repository.update_form(form_id, payload)
        else:
            form_id = repository.create_form(payload)

        form = repository.get_form(form_id=form_id)
        if form is None:
            raise RuntimeError(f"Could not reload {spec['title']}")
        sheet = _sync_sheet(form_id) if form.get("sheet_id") else _attach_sheet(form_id)
        refreshed = repository.get_form(form_id=form_id)
        if refreshed is None:
            raise RuntimeError(f"Could not reload {spec['title']}")
        result[kind] = {
            "form_id": form_id,
            "public_ref": refreshed["public_ref"],
            "published": refreshed["is_published"],
            "sheet": sheet,
            "questions": {
                question["label"]: question["id"]
                for question in refreshed["questions"]
            },
        }

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
