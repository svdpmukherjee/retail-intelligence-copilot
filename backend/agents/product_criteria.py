"""Validated product-selection slots, independent of model-generated SQL."""

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProductCriteria(BaseModel):
    mode: Literal["lowest", "below"] = "lowest"
    minimum_reviews: int = Field(ge=2, le=20000)
    limit: int = Field(default=5, ge=1, le=25)
    average_below: float | None = Field(default=None, gt=1, le=5)

    @model_validator(mode="after")
    def threshold_required(self):
        if self.mode == "below" and self.average_below is None:
            raise ValueError("A below selection requires an average threshold")
        return self


def numeric_words(text: str) -> str:
    """Normalize ordinary English selection numbers without changing other words."""
    values = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    def replace(match):
        words = match[0].lower().replace("-", " ").split()
        total = 0
        for word in words:
            if word == "hundred":
                total = max(1, total) * 100
            else:
                total += values[word]
        return str(total)

    pattern = r"\b(?:" + "|".join(values) + r")(?:[ -](?:hundred|" + "|".join(values) + r"))*\b"
    return re.sub(pattern, replace, text, flags=re.I)


def selection_slots(text: str) -> dict:
    """Extract supported explicit choices; absent values remain absent."""
    text = numeric_words(text)
    slots = {}
    if re.search(r"\b(?:lowest|worst)[ -]rated|\blowest\s+(?:average|mean)", text, re.I):
        slots["mode"] = "lowest"
    if re.search(r"\b(?:below|under)\s+(?:a\s+)?threshold\b", text, re.I):
        slots["mode"] = "below"
    if match := re.search(r"\b(?:below|under|less than)\s*([1-5](?:\.\d+)?)", text, re.I):
        slots.update(mode="below", average_below=float(match[1]))
    if match := re.search(
        r"\b(?:at least|minimum(?: of)?|min(?:imum)?[:=]?)\s*(\d+)\s*reviews?", text, re.I
    ):
        slots["minimum_reviews"] = int(match[1])
    if match := re.search(r"\b(\d+)\s*reviews?\s+(?:minimum|or more)\b", text, re.I):
        slots["minimum_reviews"] = int(match[1])
    number = r"(\d+|one|two|three|four|five|ten)"
    match = re.search(
        rf"\b(?:which|what|list|give me|show(?: me)?|use|top|bottom|up to|limit(?: to)?)"
        rf"\s+(?:the\s+)?{number}\b",
        text,
        re.I,
    )
    if match:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
        slots["limit"] = int(match[1]) if match[1].isdigit() else words[match[1].lower()]
    return slots
