import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


USER_SLUG = "mathmatic"
TIMEZONE = "Asia/Shanghai"

TZ = ZoneInfo(TIMEZONE)

API_URLS = [
    "https://leetcode.cn/graphql/noj-go/",
    "https://leetcode.cn/graphql/",
]

OUTPUT = Path("assets/lc-heatmap.svg")
DATA_OUTPUT = Path("data/lc-heatmap.json")


def graphql_request(endpoint, payload):
    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/130.0 Safari/537.36"
            ),
            "Origin": "https://leetcode.cn",
            "Referer": f"https://leetcode.cn/u/{USER_SLUG}/",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:
        error_body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"HTTP {e.code}: {error_body}"
        )


def fetch_year(year):
    query = """
query userProfileCalendar($userSlug: String!, $year: Int) {
  userCalendar(userSlug: $userSlug, year: $year) {
    submissionCalendar
  }
}
"""

    payload = {
        "operationName": "userProfileCalendar",
        "variables": {
            "userSlug": USER_SLUG,
            "year": year,
        },
        "query": query,
    }

    last_error = None

    for endpoint in API_URLS:
        try:
            print(
                f"Fetching {year} from {endpoint}"
            )

            result = graphql_request(
                endpoint,
                payload
            )

            if result.get("errors"):
                raise RuntimeError(
                    str(result["errors"])
                )

            calendar = (
                result
                .get("data", {})
                .get("userCalendar")
            )

            if calendar is None:
                raise RuntimeError(
                    "userCalendar is null"
                )

            raw = calendar.get(
                "submissionCalendar"
            )

            if not raw:
                return {}

            if isinstance(raw, str):
                raw = json.loads(raw)

            return raw

        except Exception as e:
            print(
                "Endpoint failed:",
                endpoint
            )
            print(e)
            last_error = e

    raise RuntimeError(
        f"All endpoints failed: {last_error}"
    )


def build_daily_counts():
    today = datetime.now(TZ).date()

    years = {
        today.year,
        today.year - 1,
    }

    daily = {}

    for year in sorted(years):
        raw = fetch_year(year)

        for timestamp, count in raw.items():
            try:
                ts = int(timestamp)
                count = int(count)
            except (TypeError, ValueError):
                continue

            day = datetime.fromtimestamp(
                ts,
                tz=TZ,
            ).date()

            daily[day] = (
                daily.get(day, 0)
                + count
            )

    return daily


def color_for_count(count):
    if count <= 0:
        return "#161b22"

    if count <= 2:
        return "#0e4429"

    if count <= 5:
        return "#006d32"

    if count <= 9:
        return "#26a641"

    return "#39d353"


def generate_svg(daily):
    today = datetime.now(TZ).date()

    # 最近 365 天
    window_start = (
        today
        - timedelta(days=364)
    )

    # 固定 53 周布局，和 GitHub contribution graph 类似
    grid_end = (
        today
        + timedelta(
            days=(6 - today.weekday())
        )
    )

    grid_start = (
        grid_end
        - timedelta(
            days=53 * 7 - 1
        )
    )

    WIDTH = 900
    HEIGHT = 450

    LEFT = 50
    TOP = 145

    CELL = 12
    GAP = 4
    STEP = CELL + GAP

    months = [
        "Jan", "Feb", "Mar", "Apr",
        "May", "Jun", "Jul", "Aug",
        "Sep", "Oct", "Nov", "Dec",
    ]

    parts = []

    parts.append(
        f'''
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{WIDTH}"
    height="{HEIGHT}"
    viewBox="0 0 {WIDTH} {HEIGHT}"
>
'''
    )

    parts.append(
        '''
<style>
    text {
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Helvetica,
            Arial,
            sans-serif;
    }

    .title {
        fill: #f0f6fc;
        font-size: 26px;
        font-weight: 600;
    }

    .muted {
        fill: #8b949e;
        font-size: 12px;
    }

    .date {
        fill: #8b949e;
        font-size: 12px;
    }
</style>
'''
    )

    # 卡片背景
    parts.append(
        '''
<rect
    x="1"
    y="1"
    width="898"
    height="448"
    rx="10"
    fill="#0d1117"
    stroke="#30363d"
/>
'''
    )

    parts.append(
        '''
<text
    x="50"
    y="52"
    class="title"
>
    LeetCode Heatmap
</text>
'''
    )

    parts.append(
        '''
<text
    x="50"
    y="78"
    class="muted"
>
    Last 52 Weeks
</text>
'''
    )

    # 月份
    previous_month = None

    for week in range(53):
        week_date = (
            grid_start
            + timedelta(
                weeks=week
            )
        )

        if (
            week_date.month
            != previous_month
        ):
            x = LEFT + week * STEP

            parts.append(
                f'''
<text
    x="{x}"
    y="{TOP - 18}"
    class="muted"
>
    {months[week_date.month - 1]}
</text>
'''
            )

            previous_month = (
                week_date.month
            )

    # Heatmap
    for week in range(53):

        for weekday in range(7):

            day = (
                grid_start
                + timedelta(
                    weeks=week,
                    days=weekday,
                )
            )

            x = (
                LEFT
                + week * STEP
            )

            y = (
                TOP
                + weekday * STEP
            )

            if (
                window_start
                <= day
                <= today
            ):
                count = daily.get(
                    day,
                    0
                )

            else:
                count = 0

            color = color_for_count(
                count
            )

            parts.append(
                f'''
<rect
    x="{x}"
    y="{y}"
    width="{CELL}"
    height="{CELL}"
    rx="2"
    fill="{color}"
>
    <title>
        {day.isoformat()}: {count} submissions
    </title>
</rect>
'''
            )

    # 日期
    date_y = (
        TOP
        + 7 * STEP
        + 38
    )

    parts.append(
        f'''
<text
    x="{LEFT}"
    y="{date_y}"
    class="date"
>
    {window_start.strftime("%Y.%m.%d")}
</text>
'''
    )

    parts.append(
        f'''
<text
    x="{WIDTH - 50}"
    y="{date_y}"
    class="date"
    text-anchor="end"
>
    {today.strftime("%Y.%m.%d")}
</text>
'''
    )

    # Less / More
    legend_y = date_y + 52
    legend_x = WIDTH - 255

    parts.append(
        f'''
<text
    x="{legend_x}"
    y="{legend_y + 11}"
    class="muted"
>
    Less
</text>
'''
    )

    legend_colors = [
        "#161b22",
        "#0e4429",
        "#006d32",
        "#26a641",
        "#39d353",
    ]

    for i, color in enumerate(
        legend_colors
    ):
        x = (
            legend_x
            + 35
            + i * 22
        )

        parts.append(
            f'''
<rect
    x="{x}"
    y="{legend_y}"
    width="14"
    height="14"
    rx="2"
    fill="{color}"
    stroke="#30363d"
/>
'''
        )

    parts.append(
        f'''
<text
    x="{legend_x + 155}"
    y="{legend_y + 11}"
    class="muted"
>
    More
</text>
'''
    )

    parts.append("</svg>")

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        "\n".join(parts),
        encoding="utf-8"
    )


def save_json(daily):
    DATA_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "userSlug": USER_SLUG,
        "generatedAt": datetime.now(
            TZ
        ).isoformat(),
        "daily": {
            day.isoformat(): count
            for day, count
            in sorted(
                daily.items()
            )
        },
    }

    DATA_OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def main():
    print(
        f"Fetching LeetCode heatmap "
        f"for {USER_SLUG} ..."
    )

    daily = build_daily_counts()

    print(
        "Calendar days received:",
        len(daily)
    )

    generate_svg(daily)
    save_json(daily)

    print("Done!")
    print("SVG:", OUTPUT)
    print("JSON:", DATA_OUTPUT)


if __name__ == "__main__":
    main()
