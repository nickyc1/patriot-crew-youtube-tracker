#!/usr/bin/env python3
"""Build aggregate-only weekly survey and YouTube spend data."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


SURVEY_QUESTION = "Where did you FIRST hear about Patriot Crew?"
SURVEY_OTHER = f"{SURVEY_QUESTION} None of the above"
ORDER_ID = "Order id"
DATE = "Date"
REQUIRED_COLUMNS = {DATE, ORDER_ID, SURVEY_QUESTION, SURVEY_OTHER}
MAX_CSV_BYTES = 10 * 1024 * 1024
PUBLIC_WEEK_FIELDS = {
    "week_start",
    "week_end",
    "label",
    "is_partial",
    "survey_responses",
    "youtube_responses",
    "youtube_share",
    "youtube_spend",
    "impressions",
    "clicks",
    "cost_per_youtube_response",
}


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


def is_youtube_response(row: dict[str, str]) -> bool:
    primary = (row.get(SURVEY_QUESTION) or "").casefold()
    other = (row.get(SURVEY_OTHER) or "").casefold()
    return "youtube" in primary or "youtube" in other


def read_survey(path: Path) -> list[dict[str, object]]:
    if path.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("Survey CSV exceeds the 10 MB safety limit")

    deduplicated: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Survey CSV is missing columns: {sorted(missing)}")

        for row_number, row in enumerate(reader, start=2):
            order_id = (row.get(ORDER_ID) or "").strip()
            if not order_id:
                raise ValueError(f"Missing order ID on row {row_number}")
            deduplicated[order_id] = {
                "date": parse_iso_date(row[DATE]),
                "youtube": is_youtube_response(row),
            }

    return list(deduplicated.values())


def fetch_youtube_delivery(
    config_path: Path, customer_id: str, start: date, end: date
) -> list[dict[str, object]]:
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_storage(str(config_path))
    service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          segments.date,
          segments.ad_network_type,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks
        FROM campaign
        WHERE segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'
          AND segments.ad_network_type = 'YOUTUBE'
          AND metrics.cost_micros > 0
        ORDER BY segments.date
    """

    rows = []
    for row in service.search(customer_id=customer_id, query=query):
        rows.append(
            {
                "date": parse_iso_date(row.segments.date),
                "spend": row.metrics.cost_micros / 1_000_000,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
            }
        )
    return rows


def pearson(pairs: Iterable[tuple[float, float]]) -> float | None:
    values = list(pairs)
    if len(values) < 3:
        return None
    xs, ys = zip(*values)
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in values)
    x_denominator = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    y_denominator = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if not x_denominator or not y_denominator:
        return None
    return numerator / (x_denominator * y_denominator)


def build_public_data(
    survey_rows: list[dict[str, object]],
    delivery_rows: list[dict[str, object]],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if not survey_rows:
        raise ValueError("Survey CSV has no responses")

    first_date = min(row["date"] for row in survey_rows)
    last_date = max(row["date"] for row in survey_rows)
    first_week = monday(first_date)
    last_week = monday(last_date)

    survey_by_week = defaultdict(lambda: {"responses": 0, "youtube": 0})
    survey_by_month = defaultdict(lambda: {"responses": 0, "youtube": 0})
    for row in survey_rows:
        week = monday(row["date"])
        survey_by_week[week]["responses"] += 1
        survey_by_week[week]["youtube"] += int(row["youtube"])
        month = row["date"].strftime("%Y-%m")
        survey_by_month[month]["responses"] += 1
        survey_by_month[month]["youtube"] += int(row["youtube"])

    delivery_by_week = defaultdict(
        lambda: {"spend": 0.0, "impressions": 0, "clicks": 0}
    )
    delivery_by_month = defaultdict(
        lambda: {"spend": 0.0, "impressions": 0, "clicks": 0}
    )
    for row in delivery_rows:
        week = monday(row["date"])
        delivery_by_week[week]["spend"] += row["spend"]
        delivery_by_week[week]["impressions"] += row["impressions"]
        delivery_by_week[week]["clicks"] += row["clicks"]
        month = row["date"].strftime("%Y-%m")
        delivery_by_month[month]["spend"] += row["spend"]
        delivery_by_month[month]["impressions"] += row["impressions"]
        delivery_by_month[month]["clicks"] += row["clicks"]

    weeks = []
    cursor = first_week
    while cursor <= last_week:
        week_end = cursor + timedelta(days=6)
        survey = survey_by_week[cursor]
        delivery = delivery_by_week[cursor]
        partial = cursor < first_date or week_end > last_date
        youtube_count = survey["youtube"]
        week = {
            "week_start": cursor.isoformat(),
            "week_end": week_end.isoformat(),
            "label": f"{cursor.strftime('%b %-d')}–{week_end.strftime('%b %-d')}",
            "is_partial": partial,
            "survey_responses": survey["responses"],
            "youtube_responses": youtube_count,
            "youtube_share": round(
                youtube_count / survey["responses"] if survey["responses"] else 0, 4
            ),
            "youtube_spend": round(delivery["spend"], 2),
            "impressions": delivery["impressions"],
            "clicks": delivery["clicks"],
            "cost_per_youtube_response": round(
                delivery["spend"] / youtube_count, 2
            )
            if youtube_count and not partial
            else None,
        }
        if set(week) != PUBLIC_WEEK_FIELDS:
            raise AssertionError("Unexpected public week fields")
        weeks.append(week)
        cursor += timedelta(days=7)

    complete_weeks = [week for week in weeks if not week["is_partial"]]
    if not complete_weeks:
        raise ValueError("At least one complete Monday-through-Sunday week is required")
    correlation = pearson(
        (week["youtube_spend"], week["youtube_responses"])
        for week in complete_weeks
    )
    peak_week = max(complete_weeks, key=lambda week: week["youtube_responses"])
    latest_complete = complete_weeks[-1]

    months = {}
    for month in sorted(set(survey_by_month) | set(delivery_by_month)):
        survey = survey_by_month[month]
        delivery = delivery_by_month[month]
        months[month] = {
            "survey_responses": survey["responses"],
            "youtube_responses": survey["youtube"],
            "youtube_share": round(
                survey["youtube"] / survey["responses"] if survey["responses"] else 0,
                4,
            ),
            "youtube_spend": round(delivery["spend"], 2),
            "impressions": delivery["impressions"],
            "clicks": delivery["clicks"],
        }

    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "generated_at": timestamp.isoformat(),
        "data_through": last_date.isoformat(),
        "source_window": {
            "survey_start": first_date.isoformat(),
            "survey_end": last_date.isoformat(),
        },
        "summary": {
            "total_survey_responses": len(survey_rows),
            "total_youtube_responses": sum(
                int(row["youtube"]) for row in survey_rows
            ),
            "same_week_correlation": round(correlation, 2)
            if correlation is not None
            else None,
            "complete_week_count": len(complete_weeks),
            "peak_week": peak_week["label"],
            "peak_week_youtube_responses": peak_week["youtube_responses"],
            "peak_week_youtube_spend": peak_week["youtube_spend"],
            "latest_complete_week": latest_complete["label"],
            "latest_complete_youtube_responses": latest_complete[
                "youtube_responses"
            ],
            "latest_complete_youtube_spend": latest_complete["youtube_spend"],
        },
        "months": months,
        "weeks": weeks,
        "methodology": {
            "survey_definition": "Orders selecting YouTube for where they first heard about Patriot Crew.",
            "spend_definition": "Google Ads cost delivered on YouTube inventory across all campaign types.",
            "week_definition": "Monday through Sunday. Partial weeks are labeled.",
            "interpretation": "Directional acquisition signal; correlation does not prove causation.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey-csv", type=Path, required=True)
    parser.add_argument("--google-ads-config", type=Path, required=True)
    parser.add_argument("--customer-id", default="6620264315")
    parser.add_argument("--output", type=Path, default=Path("docs/data.json"))
    args = parser.parse_args()

    survey_rows = read_survey(args.survey_csv)
    start = monday(min(row["date"] for row in survey_rows))
    end = max(row["date"] for row in survey_rows)
    delivery_rows = fetch_youtube_delivery(
        args.google_ads_config, args.customer_id, start, end
    )
    output = build_public_data(survey_rows, delivery_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary_output.write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    temporary_output.replace(args.output)


if __name__ == "__main__":
    main()
