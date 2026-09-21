import json
import urllib.request
import urllib.error
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


# =========================
# 配置
# =========================

USER_SLUG = "mathmatic"

API_URL = "https://leetcode.cn/graphql"

OUTPUT = Path("assets/lc-contest.svg")
DATA_OUTPUT = Path("data/lc-contest.json")


# =========================
# 获取 LeetCode CN 竞赛数据
# =========================

def fetch_contest_data():
    query = """
query userContest($userSlug: String!) {
  userContestRanking(userSlug: $userSlug) {
    currentRatingRanking
    ratingHistory
  }
}
"""

    payload = {
        "operationName": "userContest",
        "variables": {
            "userSlug": USER_SLUG
        },
        "query": query
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
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

            raw = response.read().decode("utf-8")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        print("LeetCode HTTP error")
        print("Status:", e.code)
        print("Response:")
        print(error_body)

        raise RuntimeError(
            f"LeetCode returned HTTP {e.code}: "
            f"{error_body}"
        )

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to LeetCode CN: {e}"
        )

    result = json.loads(raw)

    # GraphQL 本身返回错误
    if result.get("errors"):
        print("GraphQL errors:")
        print(
            json.dumps(
                result["errors"],
                indent=2,
                ensure_ascii=False
            )
        )

        raise RuntimeError(
            f"GraphQL error: {result['errors']}"
        )

    data = result.get("data")

    if not data:
        raise RuntimeError(
            f"No data returned: {result}"
        )

    ranking = data.get(
        "userContestRanking"
    )

    if ranking is None:
        raise RuntimeError(
            "userContestRanking is null. "
            "Check USER_SLUG."
        )

    return ranking


# =========================
# 处理 ratingHistory
# =========================

def parse_rating_history(raw):
    """
    LeetCode CN 的 ratingHistory 通常类似：

    "[1500, null, 1532.4, 1601.2, ...]"

    也可能直接返回 list。
    """

    if raw is None:
        return []

    if isinstance(raw, str):
        try:
            values = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(
                "Cannot parse ratingHistory: "
                + raw
            )

    elif isinstance(raw, list):
        values = raw

    else:
        raise RuntimeError(
            "Unknown ratingHistory type: "
            + str(type(raw))
        )

    ratings = []

    for value in values:
        if value is None:
            continue

        try:
            ratings.append(
                float(value)
            )
        except (TypeError, ValueError):
            continue

    return ratings


# =========================
# Rating → 等级
# =========================

def get_rank_name(rating):
    """
    这里只用于卡片文字显示。

    你的约 2898 会显示 Guardian。
    """

    if rating >= 2600:
        return "Guardian"

    if rating >= 2200:
        return "Knight"

    return "Contestant"


# =========================
# 生成 SVG 曲线
# =========================

def generate_chart(
    rating_history,
    ranking
):
    if not rating_history:
        raise RuntimeError(
            "Rating history is empty"
        )

    current_rating = rating_history[-1]
    max_rating = max(rating_history)

    rank_name = get_rank_name(
        current_rating
    )

    current_rank = ranking.get(
        "currentRatingRanking"
    )

    # 横坐标：
    # 第 1、2、3... 次有效 Rating 更新
    x = list(
        range(
            1,
            len(rating_history) + 1
        )
    )

    fig, ax = plt.subplots(
        figsize=(9, 4.5),
        dpi=150
    )

    # LeetCode 风格的简单背景区间
    bands = [
        (0, 1400, "#eeeeee"),
        (1400, 1600, "#dff3e4"),
        (1600, 1800, "#dceef8"),
        (1800, 2000, "#e7e0f7"),
        (2000, 2200, "#f3def8"),
        (2200, 2400, "#f8ead4"),
        (2400, 2600, "#ffe1ca"),
        (2600, 3000, "#ffd4d4"),
        (3000, 4000, "#ffbebe"),
    ]

    for low, high, color in bands:
        ax.axhspan(
            low,
            high,
            color=color,
            alpha=0.45
        )

    ax.plot(
        x,
        rating_history,
        linewidth=2.4,
        marker="o",
        markersize=3.5
    )

    ax.set_title(
        "LeetCode Contest Rating",
        fontsize=15,
        fontweight="bold",
        loc="left",
        pad=12
    )

    ax.xaxis.set_visible(False)

    ax.set_ylabel(
        "Rating"
    )

    ax.grid(
        True,
        alpha=0.20
    )

    ax.set_axisbelow(True)

    # 当前数据框
    info = (
        f"Current: {current_rating:.0f}\n"
        f"Max: {max_rating:.0f}\n"
        f"{rank_name}"
    )

    if current_rank is not None:
        info += (
            f"\nRank: #{current_rank}"
        )

    ax.text(
        0.98,
        0.96,
        info,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9.5,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": "#aaaaaa",
            "alpha": 0.88
        }
    )

    # 标记最新 Rating
    ax.annotate(
        f"{current_rating:.0f}",
        xy=(
            x[-1],
            current_rating
        ),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=9
    )

    plt.tight_layout()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    plt.savefig(
        OUTPUT,
        format="svg",
        bbox_inches="tight"
    )

    plt.close(fig)

    return (
        current_rating,
        max_rating,
        rank_name
    )


# =========================
# 保存 JSON 数据
# =========================

def save_json(
    ranking,
    rating_history,
    current_rating,
    max_rating,
    rank_name
):
    DATA_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "userSlug": USER_SLUG,

        "currentRating":
            round(
                current_rating,
                2
            ),

        "maxRating":
            round(
                max_rating,
                2
            ),

        "rankName":
            rank_name,

        "currentRatingRanking":
            ranking.get(
                "currentRatingRanking"
            ),

        "ratingHistory":
            rating_history
    }

    DATA_OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


# =========================
# main
# =========================

def main():
    print(
        f"Fetching LeetCode CN data "
        f"for {USER_SLUG} ..."
    )

    ranking = fetch_contest_data()

    print("Ranking data received.")

    raw_history = ranking.get(
        "ratingHistory"
    )

    rating_history = (
        parse_rating_history(
            raw_history
        )
    )

    print(
        "Rating records:",
        len(rating_history)
    )

    if rating_history:
        print(
            "Latest rating:",
            rating_history[-1]
        )

    current_rating, max_rating, rank_name = (
        generate_chart(
            rating_history,
            ranking
        )
    )

    save_json(
        ranking,
        rating_history,
        current_rating,
        max_rating,
        rank_name
    )

    print()
    print("Done!")
    print(
        "Current rating:",
        round(current_rating, 2)
    )
    print(
        "Max rating:",
        round(max_rating, 2)
    )
    print(
        "Rank:",
        rank_name
    )
    print(
        "SVG:",
        OUTPUT
    )
    print(
        "JSON:",
        DATA_OUTPUT
    )


if __name__ == "__main__":
    main()
