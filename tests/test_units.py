"""Tests that need no database."""

from __future__ import annotations

import pytest

from formcraft import sheets
from formcraft.models import FormIn, validate_answer
from formcraft.repository import slugify
from formcraft.sheets import RESPONSE_ID_KEY, _column_letter


@pytest.mark.parametrize(
    ("question", "raw", "expected_ok"),
    [
        ({"type": "short_text", "required": True, "options": [], "config": {}}, "", False),
        ({"type": "short_text", "required": False, "options": [], "config": {}}, "", True),
        ({"type": "email", "required": True, "options": [], "config": {}}, "nope", False),
        ({"type": "email", "required": True, "options": [], "config": {}}, "a@b.co", True),
        ({"type": "radio", "required": True, "options": ["A"], "config": {}}, "B", False),
        ({"type": "radio", "required": True, "options": ["A"], "config": {}}, "A", True),
        ({"type": "scale", "required": True, "options": [], "config": {"min": 1, "max": 5}}, "9", False),
        ({"type": "scale", "required": True, "options": [], "config": {"min": 1, "max": 5}}, "3", True),
        ({"type": "number", "required": True, "options": [], "config": {}}, "abc", False),
    ],
)
def test_validate_answer(question, raw, expected_ok):
    _, error = validate_answer(question, raw)
    assert (error is None) is expected_ok


def test_checkbox_rejects_unknown_option():
    question = {"type": "checkbox", "required": False, "options": ["A", "B"], "config": {}}
    value, error = validate_answer(question, ["A", "B"])
    assert error is None and value == ["A", "B"]
    _, error = validate_answer(question, ["A", "Z"])
    assert error is not None


def test_required_checkbox_needs_a_selection():
    question = {"type": "checkbox", "required": True, "options": ["A"], "config": {}}
    _, error = validate_answer(question, [])
    assert error is not None


def test_column_letter():
    assert _column_letter(0) == "A"
    assert _column_letter(25) == "Z"
    assert _column_letter(26) == "AA"
    assert _column_letter(51) == "AZ"
    assert _column_letter(701) == "ZZ"


def test_response_id_mapping_key_cannot_collide_with_question_ids():
    assert RESPONSE_ID_KEY.startswith("__formcraft_")


def test_existing_sheet_response_is_updated_in_place(monkeypatch):
    class Request:
        def __init__(self, result=None):
            self.result = result or {}

        def execute(self):
            return self.result

    class Values:
        def __init__(self):
            self.updates = []
            self.appends = []

        def get(self, **kwargs):
            return Request({"values": [["different-id"], ["response-1"]]})

        def update(self, **kwargs):
            self.updates.append(kwargs)
            return Request()

        def append(self, **kwargs):
            self.appends.append(kwargs)
            return Request()

    class Spreadsheets:
        def __init__(self, values):
            self._values = values

        def values(self):
            return self._values

    class Service:
        def __init__(self, values):
            self._spreadsheets = Spreadsheets(values)

        def spreadsheets(self):
            return self._spreadsheets

    values = Values()
    monkeypatch.setattr(sheets, "enabled", lambda: True)
    monkeypatch.setattr(sheets, "_load_service", lambda: Service(values))
    monkeypatch.setattr(
        sheets,
        "_ensure_columns",
        lambda service, form, questions: {
            "question-1": 1,
            RESPONSE_ID_KEY: 2,
        },
    )

    sheets.append_response(
        {
            "id": "form-1",
            "sheet_id": "sheet-1",
            "questions": [{"id": "question-1"}],
        },
        "response-1",
        {"question-1": "Updated"},
        "2026-08-08T12:00:00Z",
    )

    assert values.appends == []
    assert values.updates[0]["range"] == "Responses!A3:C3"
    assert values.updates[0]["body"]["values"] == [
        ["2026-08-08T12:00:00Z", "Updated", "response-1"]
    ]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Creator Intake", "creator-intake"),
        ("  Weird   Title!! ", "weird-title"),
        ("2026 — Q1 Feedback", "2026-q1-feedback"),
        ("!!!", "form"),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_form_rejects_unknown_question_type():
    with pytest.raises(ValueError, match="unknown question type"):
        FormIn.model_validate(
            {"title": "x", "sections": [{"questions": [{"type": "wat", "label": "y"}]}]}
        )


def test_form_rejects_bad_accent():
    with pytest.raises(ValueError, match="hex colour"):
        FormIn.model_validate({"title": "x", "accent": "red"})


def test_form_accepts_https_meeting_link():
    form = FormIn.model_validate(
        {
            "title": "x",
            "meeting_url": "https://calendly.com/example/intro",
            "sections": [{"questions": [{"type": "short_text", "label": "Name"}]}],
        }
    )
    assert form.meeting_url == "https://calendly.com/example/intro"


def test_form_rejects_unsafe_meeting_link():
    with pytest.raises(ValueError, match="complete https URL"):
        FormIn.model_validate(
            {
                "title": "x",
                "meeting_url": "javascript:alert(1)",
                "sections": [
                    {"questions": [{"type": "short_text", "label": "Name"}]}
                ],
            }
        )


def test_options_are_trimmed_and_blanks_dropped():
    form = FormIn.model_validate(
        {
            "title": "x",
            "sections": [
                {
                    "questions": [
                        {
                            "type": "radio",
                            "label": "y",
                            "options": ["  A  ", "", "   ", "B"],
                        }
                    ]
                }
            ],
        }
    )
    assert form.sections[0].questions[0].options == ["A", "B"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"sections": []}, "add at least one section"),
        (
            {"sections": [{"questions": []}]},
            "add at least one question",
        ),
        (
            {
                "sections": [
                    {
                        "questions": [
                            {"type": "radio", "label": "Pick", "options": ["Only"]}
                        ]
                    }
                ]
            },
            "at least two options",
        ),
        (
            {
                "sections": [
                    {
                        "questions": [
                            {
                                "type": "scale",
                                "label": "Score",
                                "config": {"min": 5, "max": 1},
                            }
                        ]
                    }
                ]
            },
            "maximum must be greater",
        ),
    ],
)
def test_form_structure_errors_are_rejected(change, message):
    payload = {"title": "Validation test", **change}
    with pytest.raises(ValueError, match=message):
        FormIn.model_validate(payload)


# ------------------------------------------------------------- image slots


def test_every_slot_has_a_usable_brief():
    from formcraft.media import SLOTS

    for name, slot in SLOTS.items():
        assert slot.name == name, f"{name} key/name mismatch"
        assert "×" in slot.size, f"{name} has no pixel size"
        assert "/" in slot.ratio, f"{name} has no aspect ratio"
        assert len(slot.description) > 60, f"{name} brief is too thin to act on"


def test_unfilled_slot_resolves_to_none():
    from formcraft.media import resolve

    assert resolve("does-not-exist") is None


def test_slot_resolves_when_the_file_exists(tmp_path, monkeypatch):
    from dataclasses import replace

    from formcraft import config, media

    web = tmp_path / "web" / "static" / "img"
    web.mkdir(parents=True)
    (web / "brand-mark.webp").write_bytes(b"x")
    (web / "form-cover-creator-intake.png").write_bytes(b"x")

    monkeypatch.setattr(
        media, "settings", replace(config.settings, web_dir=tmp_path / "web")
    )

    assert media.resolve("brand-mark") == "/static/img/brand-mark.webp"
    # A per-form variant wins over the generic slot...
    assert (
        media.resolve("form-cover", "creator-intake")
        == "/static/img/form-cover-creator-intake.png"
    )
    # ...and falls back cleanly when that variant is absent.
    assert media.resolve("form-cover", "other-form") is None


def test_media_context_exposes_slots_and_resolver():
    from formcraft.media import SLOTS, context

    ctx = context()
    assert ctx["slots"] is SLOTS
    assert callable(ctx["media_url"])


def test_static_url_is_fingerprinted():
    """Cache-busting: /static is served immutable, so URLs must change on edit."""
    from formcraft.media import static_url

    url = static_url("form.js")
    assert url.startswith("/static/form.js?v=")
    assert len(url.split("?v=")[1]) > 3
    # Stable for the same file — no needless cache invalidation between renders.
    assert static_url("form.js") == url


def test_static_url_survives_a_missing_file():
    from formcraft.media import static_url

    assert static_url("does-not-exist.js") == "/static/does-not-exist.js?v=0"
