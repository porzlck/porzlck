import json
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


USER_SLUG = "mathmatic"
API_URL = "https://leetcode.cn/graphql"

OUTPUT = Path("assets/lc-contest.svg")
DATA_OUTPUT = Path("data/lc-contest.json")


def fetch_contest_data():
    query = """
    query userContest($userSlug: String!) {
      userContestRanking(userSlug: $userSlug) {
        currentRatingRanking
        attendedContestCount
        ratingHistory
      }
    }
    """

    payload = {
        "operationName": "userContest",
        "query": query,
        "variables": {
            "userSlug": USER_SLUG
        }
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if "errors" in result:
        raise RuntimeError(result["errors"])

    ranking = result["data"]["userContestRanking"]

    if not ranking:
        raise RuntimeError("No contest ranking data found")

    return ranking


def parse_rating_history(raw):
    """
    LeetCode CN returns ratingHistory as a JSON string,
    for example:
    [1500, null, 1550.3, ...]
    """

    if isinstance(raw, str):
        values = json.loads(raw)
    else:
        values = raw

    return [float(x) for x in values if x is not None]


def generate_chart(rating_history, ranking):
    if not rating_history:
        raise RuntimeError("Rating history is empty")

    current_rating = rating_history[-1]
    max_rating = max(rating_history)

    x = list(range(1, len(rating_history) + 1))

    plt.figure(figsize=(9, 4.5), dpi=150)
    ax = plt.gca()

    # approximate LeetCode rating bands
    bands = [
        (0, 1400, "#d3d3d3"),
        (1400, 1600, "#b9e3c6"),
        (1600, 1800, "#b8ddf0"),
        (1800, 2000, "#cab8ef"),
        (2000, 2200, "#edc4f5"),
        (2200, 2400, "#f6d7a7"),
        (2400, 2600, "#ffc7a8"),
        (2600, 3000, "#ffb1b1"),
        (3000, 4000, "#ff8f8f"),
    ]

    for low, high, color in bands:
        ax.axhspan(low, high, color=color, alpha=0.28)

    ax.plot(
        x,
        rating_history,
        linewidth=2.4,
        marker="o",
        markersize=3.5,
    )

    ax.set_title(
        "LeetCode Contest Rating",
        fontsize=15,
        fontweight="bold",
        loc="left"
    )

    ax.set_xlabel("Rated Contests")
    ax.set_ylabel("Rating")

    ax.grid(True, alpha=0.2)
    ax.set_axisbelow(True)

    ax.text(
        0.98,
        0.96,
        f"Current: {current_rating:.0f}\nMax: {max_rating:.0f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox=dict(
            boxstyle="round,pad=0.3",
            fc="white",
            ec="#aaaaaa",
            alpha=0.85
        )
    )

    plt.tight_layout()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(
        OUTPUT,
        format="svg",
        bbox_inches="tight"
    )

    plt.close()

    return current_rating, max_rating


def main():
    ranking = fetch_contest_data()

    rating_history = parse_rating_history(
        ranking["ratingHistory"]
    )

    current_rating, max_rating = generate_chart(
        rating_history,
        ranking
    )

    DATA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    DATA_OUTPUT.write_text(
        json.dumps(
            {
                "userSlug": USER_SLUG,
                "currentRating": current_rating,
                "maxRating": max_rating,
                "currentRatingRanking": ranking.get(
                    "currentRatingRanking"
                ),
                "attendedContestCount": ranking.get(
                    "attendedContestCount"
                ),
                "ratingHistory": rating_history
            },
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("Generated:", OUTPUT)
    print("Current rating:", current_rating)
    print("Max rating:", max_rating)


if __name__ == "__main__":
    main()
