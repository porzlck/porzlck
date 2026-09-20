from collections import Counter
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import time
import urllib.parse
import urllib.request


HANDLE = os.environ.get("CF_HANDLE", "porzlck")
TIMEZONE = os.environ.get("CF_TIMEZONE", "Asia/Shanghai")

TZ = ZoneInfo(TIMEZONE)

SVG_PATH = Path("assets/cf-heatmap.svg")
DATA_PATH = Path("data/cf-stats.json")

PAGE_SIZE = 5000


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Codeforces-GitHub-Heatmap/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("status") != "OK":
        raise RuntimeError(data.get("comment", "Codeforces API failed"))

    return data["result"]


def fetch_submissions():
    submissions = []
    start = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "handle": HANDLE,
                "from": start,
                "count": PAGE_SIZE,
            }
        )

        url = f"https://codeforces.com/api/user.status?{query}"

        print(f"Fetching submissions from #{start} ...")
        batch = get_json(url)

        submissions.extend(batch)

        if len(batch) < PAGE_SIZE:
            break

        start += len(batch)
        time.sleep(2.1)

    return submissions


def problem_key(problem):
    return (
        problem.get("contestId"),
        problem.get("problemsetName"),
        problem.get("index"),
        problem.get("name"),
    )


def build_daily_stats(submissions):
    first_solve = {}

    for submission in submissions:
        if submission.get("verdict") != "OK":
            continue

        problem = submission.get("problem", {})
        key = problem_key(problem)

        timestamp = submission["creationTimeSeconds"]

        solved_date = datetime.fromtimestamp(
            timestamp,
            tz=TZ,
        ).date()

        old_date = first_solve.get(key)

        if old_date is None or solved_date < old_date:
            first_solve[key] = solved_date

    daily = Counter(first_solve.values())
    return daily


def max_streak(daily):
    active_days = sorted(day for day, count in daily.items() if count > 0)

    if not active_days:
        return 0

    best = 1
    current = 1

    for i in range(1, len(active_days)):
        if active_days[i] == active_days[i - 1] + timedelta(days=1):
            current += 1
        else:
            current = 1

        best = max(best, current)

    return best


def color_for_count(count):
    if count <= 0:
        return "empty"
    if count == 1:
        return "#9be9a8"
    if count == 2:
        return "#40c463"
    if count == 3:
        return "#30a14e"
    return "#216e39"


def generate_svg(daily):
    today = datetime.now(TZ).date()
    window_start = today - timedelta(days=364)

    current_week_end = today + timedelta(days=(6 - today.weekday()))
    grid_start = current_week_end - timedelta(days=53 * 7 - 1)

    CELL = 11
    GAP = 3
    STEP = CELL + GAP

    LEFT = 48
    TOP = 48

    WIDTH = LEFT + 53 * STEP + 25
    HEIGHT = 210

    total_solved = sum(daily.values())
    last_year = sum(
        count
        for day, count in daily.items()
        if window_start <= day <= today
    )

    streak = max_streak(daily)

    months = [
        "Jan", "Feb", "Mar", "Apr",
        "May", "Jun", "Jul", "Aug",
        "Sep", "Oct", "Nov", "Dec",
    ]

    parts = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">'
    )

    parts.append("""
    <style>
        .text {
            font-family: -apple-system, BlinkMacSystemFont,
            "Segoe UI", Helvetica, Arial, sans-serif;
            fill: #24292f;
        }

        .muted {
            fill: #57606a;
        }

        .empty {
            fill: #ebedf0;
        }

        @media (prefers-color-scheme: dark) {
            .text { fill: #c9d1d9; }
            .muted { fill: #8b949e; }
            .empty { fill: #161b22; }
        }
    </style>
    """)

    parts.append(
        f'<text x="{LEFT}" y="20" class="text" '
        f'font-size="15" font-weight="600">'
        f'Codeforces Activity — {escape(HANDLE)}</text>'
    )

    labels = {0: "Mon", 2: "Wed", 4: "Fri"}

    for row, label in labels.items():
        y = TOP + row * STEP + CELL - 2
        parts.append(
            f'<text x="4" y="{y}" class="muted" '
            f'font-size="10">{label}</text>'
        )

    previous_month = None

    for week in range(53):
        week_date = grid_start + timedelta(weeks=week)

        if week_date.month != previous_month:
            x = LEFT + week * STEP
            parts.append(
                f'<text x="{x}" y="{TOP - 9}" '
                f'class="muted" font-size="10">'
                f'{months[week_date.month - 1]}</text>'
            )
            previous_month = week_date.month

    for week in range(53):
        for weekday in range(7):
            day = grid_start + timedelta(weeks=week, days=weekday)

            x = LEFT + week * STEP
            y = TOP + weekday * STEP

            if window_start <= day <= today:
                count = daily.get(day, 0)
            else:
                count = 0

            fill = color_for_count(count)

            if fill == "empty":
                rect_fill = 'class="empty"'
            else:
                rect_fill = f'fill="{fill}"'

            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" '
                f'height="{CELL}" rx="2" ry="2" {rect_fill}>'
                f'<title>{day.isoformat()}: {count} solved</title>'
                f'</rect>'
            )

    stats_y = TOP + 7 * STEP + 35

    parts.append(
        f'<text x="{LEFT}" y="{stats_y}" class="text" '
        f'font-size="18">{total_solved} problems solved</text>'
    )

    parts.append(
        f'<text x="{LEFT + 280}" y="{stats_y}" class="text" '
        f'font-size="18">{last_year} in last 365 days</text>'
    )

    parts.append(
        f'<text x="{LEFT + 560}" y="{stats_y}" class="text" '
        f'font-size="18">{streak} day max streak</text>'
    )

    parts.append("</svg>")

    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(
            {
                "handle": HANDLE,
                "totalSolved": total_solved,
                "last365Days": last_year,
                "maxStreak": streak,
                "daily": {
                    day.isoformat(): count
                    for day, count in sorted(daily.items())
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main():
    submissions = fetch_submissions()
    daily = build_daily_stats(submissions)
    generate_svg(daily)
    print("Done")


if __name__ == "__main__":
    main()
