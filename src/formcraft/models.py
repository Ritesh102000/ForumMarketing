"""Question types and payload schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DisplayMode = Literal["single", "section", "one_by_one"]

QUESTION_TYPES: dict[str, dict[str, Any]] = {
    "short_text": {"label": "Short text", "has_options": False},
    "long_text": {"label": "Paragraph", "has_options": False},
    "email": {"label": "Email", "has_options": False},
    "number": {"label": "Number", "has_options": False},
    "date": {"label": "Date", "has_options": False},
    "time": {"label": "Time", "has_options": False},
    "select": {"label": "Dropdown", "has_options": True},
    "radio": {"label": "Single choice", "has_options": True},
    "checkbox": {"label": "Multiple choice", "has_options": True},
    "scale": {"label": "Linear scale", "has_options": False},
    "rating": {"label": "Star rating", "has_options": False},
}

MULTI_VALUE_TYPES = {"checkbox"}


class QuestionIn(BaseModel):
    id: str | None = None
    section_id: str | None = None
    type: str
    label: str = Field(min_length=1, max_length=500)
    help_text: str = ""
    placeholder: str = ""
    required: bool = False
    options: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in QUESTION_TYPES:
            raise ValueError(f"unknown question type: {value}")
        return value

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SectionIn(BaseModel):
    id: str | None = None
    title: str = ""
    description: str = ""
    questions: list[QuestionIn] = Field(default_factory=list)


class FormIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    display_mode: DisplayMode = "single"
    accent: str = "#6366f1"
    is_published: bool = False
    confirm_msg: str = "Thanks — your response has been recorded."
    sections: list[SectionIn] = Field(default_factory=list)

    @field_validator("accent")
    @classmethod
    def valid_hex(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("#") or len(value) not in (4, 7):
            raise ValueError("accent must be a hex colour like #6366f1")
        return value


def validate_answer(question: dict[str, Any], raw: Any) -> tuple[Any, str | None]:
    """Return (normalised value, error). Error is None when the answer is valid."""
    qtype = question["type"]
    required = bool(question["required"])
    options = question["options"]

    if qtype in MULTI_VALUE_TYPES:
        values = (
            raw if isinstance(raw, list) else ([raw] if raw not in (None, "") else [])
        )
        values = [str(v) for v in values if str(v).strip()]
        if required and not values:
            return None, "This question is required."
        unknown = [v for v in values if v not in options]
        if unknown:
            return None, f"Unexpected option: {unknown[0]}"
        return values, None

    value = "" if raw is None else str(raw).strip()
    if not value:
        return ("", None) if not required else (None, "This question is required.")

    if qtype in {"select", "radio"} and value not in options:
        return None, f"Unexpected option: {value}"

    if qtype == "email" and ("@" not in value or "." not in value.split("@")[-1]):
        return None, "Enter a valid email address."

    if qtype in {"number", "scale", "rating"}:
        try:
            number = float(value)
        except ValueError:
            return None, "Enter a number."
        config = question["config"]
        minimum = config.get("min")
        maximum = config.get("max")
        if minimum is not None and number < float(minimum):
            return None, f"Must be at least {minimum}."
        if maximum is not None and number > float(maximum):
            return None, f"Must be at most {maximum}."
        return (int(number) if number.is_integer() else number), None

    return value, None
