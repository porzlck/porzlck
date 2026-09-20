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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


HANDLE = os.environ.get("CF_HANDLE", "porzlck")
TIMEZONE = os.environ.get("CF_TIMEZONE", "Asia/Shanghai")
TZ = ZoneInfo(TIMEZONE)

ASSETS_DIR = Path("assets")
DATA_DIR = Path("data")

HEATMAP_PATH = ASSETS_DIR / "cf-heatmap.svg"
RATING_CHART_PATH = ASSETS_DIR / "cf-rating.svg"
PROBLEM_RATING_CHART_PATH = ASSETS_DIR / "cf-problem-ratings.svg"
STATS_PATH = DATA_DIR / "cf-stats.json"

PAGE_SIZE = 5000


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Codeforces-GitHub-Stats/1.0"},
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
        time.sleep(2.1)  # Codeforces API limit

    print(f"Fetched {len(submissions)} submissions")
    return submissions


def fetch_rating_history():
    query = urllib.parse.urlencode({"handle": HANDLE})
    url = f"https://codeforces.com/api/user.rating?{query}"
    print("Fetching rating history ...")
    result = get_json(url)
    print(f"Fetched {len(result)} rating records")
    return result


def problem_key(problem):
    return (
        problem.get("contestId"),
        problem.get("problemsetName"),
        problem.get("index"),
        problem.get("name"),
    )


def build_first_solves(submissions):
    """
    Count each problem only once: first accepted date.
    """
    first_solves = {}

    for submission in submissions:
        if submission.get("verdict") != "OK":
            continue

        problem = submission.get("problem", {})
        key = problem_key(problem)

        solved_date = datetime.fromtimestamp(
            submission["creationTimeSeconds"], tz=TZ
        ).date()

        info = {
            "date": solved_date,
            "name": problem.get("name"),
            "contestId": problem.get("contestId"),
            "index": problem.get("index"),
            "rating": problem.get("rating"),
            "tags": problem.get("tags", []),
        }

        if key not in first_solves or solved_date < first_solves[key]["date"]:
            first_solves[key] = info

    return first_solves


def build_daily_counts(first_solves):
    daily = Counter()
    for info in first_solves.values():
        daily[info["date"]] += 1
    return daily


def max_streak(daily, start=None, end=None):
    active_days = sorted(
        day for day, count in daily.items()
        if count > 0
        and (start is None or day >= start)
        and (end is None or day <= end)
    )

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


def cf_color_for_rating(rating):
    if rating is None:
        return "#cccccc"
    if rating < 1200:
        return "#c8c8c8"
    if rating < 1400:
        return "#77dd77"
    if rating < 1600:
        return "#76d7c4"
    if rating < 1900:
        return "#8f8fe8"
    if rating < 2100:
        return "#d07be2"
    if rating < 2400:
        return "#e7b56d"
    if rating < 2600:
        return "#ef7777"
    return "#ff3333"


def generate_heatmap_svg(daily):
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
    HEIGHT = 235

    total_solved = sum(daily.values())
    last_year = sum(
        count for day, count in daily.items() if window_start <= day <= today
    )

    month_start = today - timedelta(days=29)
    last_month = sum(
        count for day, count in daily.items() if month_start <= day <= today
    )

    streak_all = max_streak(daily)
    streak_year = max_streak(daily, start=window_start, end=today)
    streak_month = max_streak(daily, start=month_start, end=today)

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">'
    )

    parts.append("""
    <style>
        .text {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
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
        f'<text x="{LEFT}" y="20" class="text" font-size="15" font-weight="600">'
        f'Codeforces Activity — {escape(HANDLE)}</text>'
    )

    labels = {0: "Mon", 2: "Wed", 4: "Fri"}
    for row, label in labels.items():
        y = TOP + row * STEP + CELL - 2
        parts.append(f'<text x="4" y="{y}" class="muted" font-size="10">{label}</text>')

    previous_month = None
    for week in range(53):
        week_date = grid_start + timedelta(weeks=week)
        if week_date.month != previous_month:
            x = LEFT + week * STEP
            parts.append(
                f'<text x="{x}" y="{TOP - 9}" class="muted" font-size="10">'
                f'{months[week_date.month - 1]}</text>'
            )
            previous_month = week_date.month

    for week in range(53):
        for weekday in range(7):
            day = grid_start + timedelta(weeks=week, days=weekday)
            x = LEFT + week * STEP
            y = TOP + weekday * STEP

            count = daily.get(day, 0) if window_start <= day <= today else 0
            fill = color_for_count(count)

            if fill == "empty":
                rect_fill = 'class="empty"'
            else:
                rect_fill = f'fill="{fill}"'

            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" ry="2" {rect_fill}>'
                f'<title>{day.isoformat()}: {count} solved</title></rect>'
            )

    stats_y = TOP + 7 * STEP + 35

    parts.append(
        f'<text x="{LEFT}" y="{stats_y}" class="text" font-size="22">{total_solved}</text>'
        f'<text x="{LEFT}" y="{stats_y + 17}" class="muted" font-size="11">problems solved all time</text>'
    )

    parts.append(
        f'<text x="{LEFT + 260}" y="{stats_y}" class="text" font-size="22">{last_year}</text>'
        f'<text x="{LEFT + 260}" y="{stats_y + 17}" class="muted" font-size="11">solved in last 365 days</text>'
    )

    parts.append(
        f'<text x="{LEFT + 510}" y="{stats_y}" class="text" font-size="22">{last_month}</text>'
        f'<text x="{LEFT + 510}" y="{stats_y + 17}" class="muted" font-size="11">solved in last 30 days</text>'
    )

    streak_y = stats_y + 52

    parts.append(
        f'<text x="{LEFT}" y="{streak_y}" class="text" font-size="18">{streak_all} days</text>'
        f'<text x="{LEFT}" y="{streak_y + 16}" class="muted" font-size="11">max streak</text>'
    )

    parts.append(
        f'<text x="{LEFT + 260}" y="{streak_y}" class="text" font-size="18">{streak_year} days</text>'
        f'<text x="{LEFT + 260}" y="{streak_y + 16}" class="muted" font-size="11">max streak / last year</text>'
    )

    parts.append(
        f'<text x="{LEFT + 510}" y="{streak_y}" class="text" font-size="18">{streak_month} days</text>'
        f'<text x="{LEFT + 510}" y="{streak_y + 16}" class="muted" font-size="11">max streak / last month</text>'
    )

    parts.append("</svg>")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    HEATMAP_PATH.write_text("\n".join(parts), encoding="utf-8")


def generate_problem_rating_chart(first_solves):
    ratings = [
        info["rating"]
        for info in first_solves.values()
        if info.get("rating") is not None
    ]

    counter = Counter(ratings)
    xs = list(range(800, 3600, 100))
    ys = [counter.get(x, 0) for x in xs]
    colors = [cf_color_for_rating(x) for x in xs]

    plt.figure(figsize=(14, 5), dpi=150)
    ax = plt.gca()
    ax.bar(xs, ys, width=75, color=colors, edgecolor="#444444", linewidth=0.6)

    ax.set_title("Problem Ratings", fontsize=18, fontweight="bold", loc="left", pad=15)
    ax.set_ylabel("Problems Solved")
    ax.set_xlabel("Problem Rating")
    ax.set_xticks(xs)
    ax.set_xticklabels(xs, rotation=45)
    ax.grid(True, axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    plt.tight_layout()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(PROBLEM_RATING_CHART_PATH, format="svg", bbox_inches="tight")
    plt.close()


def generate_rating_curve(rating_history):
    if not rating_history:
        return

    dates = [
        datetime.fromtimestamp(item["ratingUpdateTimeSeconds"], tz=TZ)
        for item in rating_history
    ]
    ratings = [item["newRating"] for item in rating_history]

    current_rating = ratings[-1]
    max_rating = max(ratings)

    plt.figure(figsize=(14, 5), dpi=150)
    ax = plt.gca()

    # background rating bands
    bands = [
        (0, 1200, "#c8c8c8"),
        (1200, 1400, "#77dd77"),
        (1400, 1600, "#76d7c4"),
        (1600, 1900, "#8f8fe8"),
        (1900, 2100, "#d07be2"),
        (2100, 2400, "#e7b56d"),
        (2400, 2600, "#ef7777"),
        (2600, 4000, "#ff3333"),
    ]

    for y0, y1, color in bands:
        ax.axhspan(y0, y1, color=color, alpha=0.22)

    ax.plot(
        dates,
        ratings,
        linewidth=2.5,
        marker="o",
        markersize=5,
    )

    ax.set_title("Codeforces Rating History", fontsize=18, fontweight="bold", loc="left", pad=15)
    ax.set_ylabel("Rating")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.25)
    ax.set_axisbelow(True)

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=30)

    ax.annotate(
        f"Current: {current_rating}",
        xy=(dates[-1], ratings[-1]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=10,
    )

    ax.text(
        0.99,
        0.96,
        f"Max: {max_rating}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#aaaaaa", alpha=0.8),
    )

    plt.tight_layout()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(RATING_CHART_PATH, format="svg", bbox_inches="tight")
    plt.close()


def write_stats_json(daily, first_solves, rating_history):
    today = datetime.now(TZ).date()
    last_year_start = today - timedelta(days=364)
    last_month_start = today - timedelta(days=29)

    stats = {
        "handle": HANDLE,
        "generatedAt": datetime.now(TZ).isoformat(),
        "totalSolved": len(first_solves),
        "solvedLast365Days": sum(
            count for day, count in daily.items()
            if last_year_start <= day <= today
        ),
        "solvedLast30Days": sum(
            count for day, count in daily.items()
            if last_month_start <= day <= today
        ),
        "maxStreak": max_streak(daily),
        "ratingHistoryCount": len(rating_history),
        "currentRating": rating_history[-1]["newRating"] if rating_history else None,
        "maxRating": max((x["newRating"] for x in rating_history), default=None),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    submissions = fetch_submissions()
    rating_history = fetch_rating_history()

    first_solves = build_first_solves(submissions)
    daily = build_daily_counts(first_solves)

    generate_heatmap_svg(daily)
    generate_problem_rating_chart(first_solves)
    generate_rating_curve(rating_history)
    write_stats_json(daily, first_solves, rating_history)

    print("Done.")
    print(f"Generated: {HEATMAP_PATH}")
    print(f"Generated: {PROBLEM_RATING_CHART_PATH}")
    print(f"Generated: {RATING_CHART_PATH}")
    print(f"Generated: {STATS_PATH}")


if __name__ == "__main__":
    main()
