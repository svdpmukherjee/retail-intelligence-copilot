# ruff: noqa: E501  (long lines are manual prose)
"""Regenerate the synthetic manual PDFs (needs `pip install reportlab`; PDFs are committed)."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "manuals"

# Section headings are numbered ("1. Title") so the indexer can recover section structure.
MANUALS = {
    "smart-speaker-user-manual": (
        "Smart Speaker User Manual",
        {
            "1. Setup": "Plug in the speaker and wait for the light ring to pulse white. Open the companion app and follow the pairing steps. Setup takes about 5 minutes.",
            "2. Voice commands": "Say the wake word followed by a command such as play music or set a timer. The microphone can be muted with the top button, which turns the ring red.",
            "3. Troubleshooting": "If the speaker does not respond, unplug it for 30 seconds. To factory reset, hold the mute button for 12 seconds until the ring flashes orange.",
        },
    ),
    "robot-vacuum-manual": (
        "Robot Vacuum Owner Manual",
        {
            "1. First use": "Charge the vacuum on its dock for 4 hours before the first cleaning run. Remove cables and small objects from the floor.",
            "2. Maintenance": "Empty the dust bin after every run. Replace the filter every 3 months and the side brushes every 6 months. Wash the mop pad after each use.",
            "3. Error codes": "Error 1 means a wheel is stuck. Error 5 means the bumper is blocked. Error 9 means the dust bin is missing or full.",
        },
    ),
    "electric-kettle-safety-sheet": (
        "Electric Kettle Safety Sheet",
        {
            "1. Safe use": "Fill the kettle between the MIN and MAX marks only. Always place it on a flat, heat-resistant surface and close the lid before boiling.",
            "2. Cleaning": "Descale monthly with a citric acid solution. Never immerse the base or the cord in water.",
            "3. Warranty": "The kettle carries a 24-month warranty covering heating element failure. Limescale build-up is not covered.",
        },
    ),
    "fitness-tracker-quick-start": (
        "Fitness Tracker Quick Start",
        {
            "1. Charging": "Clip the tracker into the charging cradle. A full charge takes 90 minutes and gives up to 7 days of battery life.",
            "2. Tracking": "The tracker records steps, heart rate, and sleep automatically. Wear it snugly one finger width above the wrist bone for accurate heart rate.",
            "3. Water resistance": "The tracker is water resistant to 50 metres and can be worn while swimming. Avoid hot showers and saunas.",
        },
    ),
}


def write_pdf(path: Path, title: str, sections: dict[str, str]) -> None:
    c = canvas.Canvas(
        str(path), pagesize=A4, invariant=1
    )  # invariant: reproducible bytes
    y = 800
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, y, title)
    y -= 36
    for heading, body in sections.items():
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, heading)
        y -= 20
        c.setFont("Helvetica", 10)
        line = ""
        for word in body.split():
            if len(line) + len(word) > 90:
                c.drawString(60, y, line)
                y -= 14
                line = ""
            line = f"{line} {word}".strip()
        c.drawString(60, y, line)
        y -= 30
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for slug, (title, sections) in MANUALS.items():
        write_pdf(OUT / f"{slug}.pdf", title, sections)
