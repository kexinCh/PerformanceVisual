from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from data_processing import METRICS, pp, pct, process_workbook


APP_DIR = Path(__file__).parent
OUT = APP_DIR / "dashboard_screenshots"
OUT.mkdir(exist_ok=True)
DATA = process_workbook(APP_DIR / "data" / "Golfer Resilience Data Set.xlsx")
CONTEXT = "Tournament + Qualifying"


def font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_shell(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    width, height = 1600, 900
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, 18], fill="#003262")
    draw.rectangle([0, 18, width, 28], fill="#FDB515")
    draw.text((70, 82), title, fill="#1F2937", font=font(48))
    draw.text((70, 145), "Static fallback screen for live interview backup", fill="#6B7280", font=font(25))
    return img, draw


def team_value(metric: str, year: int) -> float:
    row = DATA.team_benchmark[
        (DATA.team_benchmark["Game Type"] == CONTEXT)
        & (DATA.team_benchmark["Metric"].astype(str) == metric)
        & (DATA.team_benchmark["Year"] == year)
    ]
    return float(row.iloc[0]["team_benchmark"])


def draw_team_overview() -> None:
    img, draw = draw_shell("Team Overview")
    blue = "#003262"
    gold = "#FDB515"
    ink = "#1F2937"
    muted = "#6B7280"
    line = "#D8DEE9"
    card_bg = "#F7F9FC"

    draw.text((70, 205), "Tournament + Qualifying selected by default", fill=muted, font=font(24))

    x0, y0 = 70, 260
    card_w, card_h, gap = 345, 150, 28
    for i, metric in enumerate(METRICS):
        x = x0 + i * (card_w + gap)
        b24 = team_value(metric, 2024)
        b25 = team_value(metric, 2025)
        draw.rounded_rectangle([x, y0, x + card_w, y0 + card_h], radius=16, outline=line, width=2, fill=card_bg)
        draw.text((x + 22, y0 + 20), metric, fill=ink, font=font(22))
        draw.text((x + 22, y0 + 62), pct(b25), fill=blue, font=font(38))
        draw.text((x + 22, y0 + 112), f"{pp(b25 - b24)} vs 2024", fill=ink, font=font(22))

    draw.text((70, 470), "How the team benchmark shifted", fill=ink, font=font(34))
    y = 540
    for metric in METRICS:
        b24 = team_value(metric, 2024)
        b25 = team_value(metric, 2025)
        x24 = 455 + int(b24 * 900)
        x25 = 455 + int(b25 * 900)
        draw.text((70, y - 14), metric, fill=ink, font=font(25))
        draw.line([x24, y, x25, y], fill=line, width=9)
        draw.ellipse([x24 - 14, y - 14, x24 + 14, y + 14], fill=blue)
        draw.ellipse([x25 - 14, y - 14, x25 + 14, y + 14], fill=gold, outline="#8A6D00", width=2)
        draw.text((x24 - 92, y - 16), pct(b24), fill=blue, font=font(22))
        draw.text((x25 + 22, y - 16), pct(b25), fill=ink, font=font(22))
        draw.text((1280, y - 16), pp(b25 - b24), fill=ink, font=font(25))
        y += 72

    draw.text((70, 830), "Run locally at http://localhost:8501 if the deployed link is unavailable.", fill=muted, font=font(24))
    img.save(OUT / "team_overview.png")


def player_yoy(player: str, metric: str):
    row = DATA.yoy[
        (DATA.yoy["Player"] == player)
        & (DATA.yoy["Game Type"] == CONTEXT)
        & (DATA.yoy["Metric"].astype(str) == metric)
    ]
    return row.iloc[0]


def draw_player_example(player: str = "Golfer H") -> None:
    img, draw = draw_shell(f"Player Explorer: {player}")
    blue = "#003262"
    ink = "#1F2937"
    muted = "#6B7280"
    line = "#D8DEE9"
    card_bg = "#F7F9FC"

    draw.text(
        (70, 205),
        "Recommended live-demo athlete because this profile has large year-over-year movement.",
        fill=muted,
        font=font(24),
    )

    x0, y0 = 70, 260
    card_w, card_h, gap = 345, 150, 28
    for i, metric in enumerate(METRICS):
        row = player_yoy(player, metric)
        x = x0 + i * (card_w + gap)
        draw.rounded_rectangle([x, y0, x + card_w, y0 + card_h], radius=16, outline=line, width=2, fill=card_bg)
        draw.text((x + 22, y0 + 20), metric, fill=ink, font=font(21))
        draw.text((x + 22, y0 + 62), pct(row["clean_value_2025"]), fill=blue, font=font(38))
        draw.text((x + 22, y0 + 108), f"{pp(row['yoy_change_pp'])} vs 2024", fill=ink, font=font(21))
        draw.text((x + 22, y0 + 132), f"{pp(row['relative_to_team_pp_2025'])} vs team", fill=ink, font=font(21))

    draw.text((70, 470), "Coach-facing demo notes", fill=ink, font=font(34))
    notes = [
        "Show the Year-over-Year Profile to separate absolute change from teammate context.",
        "Use the Bad-Hole section without forcing the three rates to sum to 100%.",
        "Use the Team Comparison chart to answer whether a value is high or low among teammates.",
        "Avoid psychological claims; describe supplied transition indicators only.",
    ]
    y = 520
    for note in notes:
        draw.rounded_rectangle([70, y - 16, 1530, y + 58], radius=12, outline=line, width=2, fill=card_bg)
        draw.text((105, y + 3), note, fill=ink, font=font(25))
        y += 82

    draw.text((70, 865), "Run locally at http://localhost:8501 if the deployed link is unavailable.", fill=muted, font=font(24))
    img.save(OUT / "player_example.png")


draw_team_overview()
draw_player_example()
print(f"Wrote fallback screenshots to {OUT}")
