#!/usr/bin/env python3
"""Build the aggregate-only Patriot Crew YouTube executive scorecard."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


SURVEY_QUESTION = "Where did you FIRST hear about Patriot Crew?"
SURVEY_OTHER = f"{SURVEY_QUESTION} None of the above"
ORDER_ID = "Order id"
DATE = "Date"
REQUIRED_COLUMNS = {DATE, ORDER_ID, SURVEY_QUESTION, SURVEY_OTHER}
MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_SHOPIFY_RESPONSE_BYTES = 5 * 1024 * 1024
SHOPIFY_ENDPOINT = (
    "https://unclesamscloset.myshopify.com/admin/api/2026-01/graphql.json"
)
SHOPIFY_TOKEN_REFERENCE = "op://Personal/hjqvngp54luxigyrirfwdqhzqu/notesPlain"
ORDER_ID_PATTERN = re.compile(r"^[0-9]{1,20}$")
YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")

CREATOR_AD_GROUPS = {
    "Jarrod Wright Videos": "Jarrod Wright",
    "Taylor Arkland Round 2 Videos": "Taylor Arkland",
    "Taylor Arkland Videos": "Taylor Arkland",
    "Tyler Kuhn Videos": "Tyler Kuhn",
    "Matthew Brown Construction Video": "Grant McMullen",
}
CREATOR_VIDEO_IDS = {
    "2Da1sBq61MA": "Todd Spears",
    "uqXpKewPht8": "William White",
}
PUBLIC_WEEK_FIELDS = {
    "week_start",
    "week_end",
    "label",
    "survey_responses",
    "youtube_responses",
    "youtube_spend",
    "youtube_revenue",
    "youtube_aov",
    "survey_roas",
    "cost_per_youtube_response",
    "matched_youtube_orders",
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
            if not ORDER_ID_PATTERN.fullmatch(order_id):
                raise ValueError(f"Invalid Shopify order ID on row {row_number}")
            deduplicated[order_id] = {
                "order_id": order_id,
                "date": parse_iso_date(row[DATE]),
                "youtube": is_youtube_response(row),
            }

    return list(deduplicated.values())


def google_ads_service(config_path: Path):
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_storage(str(config_path))
    return client.get_service("GoogleAdsService")


def fetch_youtube_delivery(
    service, customer_id: str, start: date, end: date
) -> list[dict[str, object]]:
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


def fetch_june_creator_assets(service, customer_id: str) -> list[dict[str, object]]:
    query = """
        SELECT
          ad_group.name,
          asset.youtube_video_asset.youtube_video_id,
          asset.youtube_video_asset.youtube_video_title,
          metrics.cost_micros,
          metrics.conversions_value
        FROM ad_group_ad_asset_view
        WHERE segments.date BETWEEN '2026-06-01' AND '2026-06-30'
          AND campaign.advertising_channel_type = 'DEMAND_GEN'
          AND asset.type = 'YOUTUBE_VIDEO'
          AND metrics.cost_micros > 0
    """
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in service.search(customer_id=customer_id, query=query):
        youtube_id = row.asset.youtube_video_asset.youtube_video_id
        if not YOUTUBE_ID_PATTERN.fullmatch(youtube_id):
            continue
        creator = CREATOR_VIDEO_IDS.get(youtube_id) or CREATOR_AD_GROUPS.get(
            row.ad_group.name
        )
        if not creator:
            continue
        key = (creator, youtube_id)
        video = grouped.setdefault(
            key,
            {
                "creator": creator,
                "youtube_id": youtube_id,
                "title": row.asset.youtube_video_asset.youtube_video_title[:120],
                "spend": 0.0,
                "google_reported_revenue": 0.0,
            },
        )
        video["spend"] += row.metrics.cost_micros / 1_000_000
        video["google_reported_revenue"] += row.metrics.conversions_value

    creators: dict[str, dict[str, object]] = {}
    for video in grouped.values():
        creator = creators.setdefault(
            video["creator"],
            {
                "creator": video["creator"],
                "spend": 0.0,
                "google_reported_revenue": 0.0,
                "videos": [],
            },
        )
        public_video = {
            "youtube_id": video["youtube_id"],
            "title": video["title"],
            "spend": round(video["spend"], 2),
            "google_reported_revenue": round(
                video["google_reported_revenue"], 2
            ),
        }
        creator["videos"].append(public_video)
        creator["spend"] += video["spend"]
        creator["google_reported_revenue"] += video["google_reported_revenue"]

    result = []
    for creator in creators.values():
        creator["videos"].sort(key=lambda video: video["spend"], reverse=True)
        creator["video_count"] = len(creator["videos"])
        creator["spend"] = round(creator["spend"], 2)
        creator["google_reported_revenue"] = round(
            creator["google_reported_revenue"], 2
        )
        creator["google_reported_roas"] = round(
            creator["google_reported_revenue"] / creator["spend"], 2
        )
        result.append(creator)
    return sorted(result, key=lambda creator: creator["spend"], reverse=True)


def fetch_featured_videos_by_month(
    service, customer_id: str, start: date, end: date, limit: int = 4
) -> list[dict[str, object]]:
    query = f"""
        SELECT
          segments.month,
          asset.youtube_video_asset.youtube_video_id,
          asset.youtube_video_asset.youtube_video_title,
          metrics.cost_micros
        FROM ad_group_ad_asset_view
        WHERE segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'
          AND campaign.advertising_channel_type = 'DEMAND_GEN'
          AND asset.type = 'YOUTUBE_VIDEO'
          AND metrics.cost_micros > 0
    """
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in service.search(customer_id=customer_id, query=query):
        youtube_id = row.asset.youtube_video_asset.youtube_video_id
        if not YOUTUBE_ID_PATTERN.fullmatch(youtube_id):
            continue
        month = row.segments.month[:7]
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
            continue
        key = (month, youtube_id)
        video = grouped.setdefault(
            key,
            {
                "youtube_id": youtube_id,
                "title": row.asset.youtube_video_asset.youtube_video_title[:120],
                "spend": 0.0,
            },
        )
        video["spend"] += row.metrics.cost_micros / 1_000_000

    by_month: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (month, _), video in grouped.items():
        video["spend"] = round(video["spend"], 2)
        by_month[month].append(video)

    result = []
    for month, videos in sorted(by_month.items()):
        videos.sort(key=lambda video: video["spend"], reverse=True)
        month_date = date.fromisoformat(f"{month}-01")
        result.append(
            {
                "month": month,
                "label": month_date.strftime("%B %Y"),
                "videos": videos[:limit],
            }
        )
    return result


def get_shopify_token() -> str:
    token = subprocess.check_output(
        ["op", "read", SHOPIFY_TOKEN_REFERENCE],
        text=True,
        timeout=30,
    ).strip()
    if not token or len(token) > 512:
        raise ValueError("Shopify token is missing or malformed")
    return token


def fetch_shopify_order_values(
    order_ids: Iterable[str], token: str
) -> dict[str, float]:
    query = """query Orders($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on Order {
          legacyResourceId
          netPaymentSet { shopMoney { amount currencyCode } }
          cancelledAt
          test
        }
      }
    }"""
    values: dict[str, float] = {}
    ids = sorted(set(order_ids))
    for offset in range(0, len(ids), 100):
        batch = ids[offset : offset + 100]
        payload = json.dumps(
            {
                "query": query,
                "variables": {
                    "ids": [f"gid://shopify/Order/{order_id}" for order_id in batch]
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            SHOPIFY_ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_SHOPIFY_RESPONSE_BYTES + 1)
        if len(raw) > MAX_SHOPIFY_RESPONSE_BYTES:
            raise ValueError("Shopify response exceeds the 5 MB safety limit")
        document = json.loads(raw)
        if document.get("errors"):
            raise RuntimeError("Shopify returned a GraphQL error")
        nodes = document.get("data", {}).get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("Shopify response is missing the nodes list")
        for node in nodes:
            if not node or node.get("test") or node.get("cancelledAt"):
                continue
            order_id = str(node.get("legacyResourceId", ""))
            if not ORDER_ID_PATTERN.fullmatch(order_id):
                raise ValueError("Shopify returned an invalid order ID")
            money = (node.get("netPaymentSet") or {}).get("shopMoney") or {}
            if money.get("currencyCode") != "USD":
                raise ValueError("Shopify returned a non-USD order")
            try:
                amount = Decimal(str(money["amount"]))
            except (InvalidOperation, KeyError) as error:
                raise ValueError("Shopify returned an invalid order amount") from error
            if amount < 0 or amount > 1_000_000:
                raise ValueError("Shopify returned an out-of-range order amount")
            values[order_id] = float(amount)
    return values


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
    order_values: dict[str, float] | None = None,
    creator_assets: list[dict[str, object]] | None = None,
    featured_videos_by_month: list[dict[str, object]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if not survey_rows:
        raise ValueError("Survey CSV has no responses")
    order_values = order_values or {}
    creator_assets = creator_assets or []
    featured_videos_by_month = featured_videos_by_month or []
    first_date = min(row["date"] for row in survey_rows)
    last_date = max(row["date"] for row in survey_rows)

    survey_by_week = defaultdict(
        lambda: {
            "responses": 0,
            "youtube": 0,
            "youtube_revenue": 0.0,
            "youtube_matched": 0,
            "all_revenue": 0.0,
            "all_matched": 0,
        }
    )
    for row in survey_rows:
        week = survey_by_week[monday(row["date"])]
        week["responses"] += 1
        week["youtube"] += int(row["youtube"])
        order_id = row.get("order_id")
        if order_id in order_values:
            order_value = order_values[order_id]
            week["all_revenue"] += order_value
            week["all_matched"] += 1
            if row["youtube"]:
                week["youtube_revenue"] += order_value
                week["youtube_matched"] += 1

    delivery_by_week = defaultdict(
        lambda: {"spend": 0.0, "impressions": 0, "clicks": 0}
    )
    for row in delivery_rows:
        week = delivery_by_week[monday(row["date"])]
        week["spend"] += row["spend"]
        week["impressions"] += row["impressions"]
        week["clicks"] += row["clicks"]

    weeks = []
    cursor = monday(first_date)
    while cursor <= monday(last_date):
        week_end = cursor + timedelta(days=6)
        if cursor >= first_date and week_end <= last_date:
            survey = survey_by_week[cursor]
            delivery = delivery_by_week[cursor]
            youtube_count = survey["youtube"]
            youtube_revenue = survey["youtube_revenue"]
            week = {
                "week_start": cursor.isoformat(),
                "week_end": week_end.isoformat(),
                "label": f"{cursor.strftime('%b %-d')}–{week_end.strftime('%b %-d')}",
                "survey_responses": survey["responses"],
                "youtube_responses": youtube_count,
                "youtube_spend": round(delivery["spend"], 2),
                "youtube_revenue": round(youtube_revenue, 2),
                "youtube_aov": round(
                    youtube_revenue / survey["youtube_matched"], 2
                )
                if survey["youtube_matched"]
                else None,
                "survey_roas": round(youtube_revenue / delivery["spend"], 2)
                if delivery["spend"]
                else None,
                "cost_per_youtube_response": round(
                    delivery["spend"] / youtube_count, 2
                )
                if youtube_count
                else None,
                "matched_youtube_orders": survey["youtube_matched"],
            }
            if set(week) != PUBLIC_WEEK_FIELDS:
                raise AssertionError("Unexpected public week fields")
            weeks.append(week)
        cursor += timedelta(days=7)

    if not weeks:
        raise ValueError("At least one complete Monday-through-Sunday week is required")

    total_spend = sum(week["youtube_spend"] for week in weeks)
    total_youtube = sum(week["youtube_responses"] for week in weeks)
    total_revenue = sum(week["youtube_revenue"] for week in weeks)
    total_matched = sum(week["matched_youtube_orders"] for week in weeks)
    all_revenue = sum(survey_by_week[monday(date.fromisoformat(week["week_start"]))]["all_revenue"] for week in weeks)
    all_matched = sum(survey_by_week[monday(date.fromisoformat(week["week_start"]))]["all_matched"] for week in weeks)
    youtube_aov = total_revenue / total_matched if total_matched else None
    all_survey_aov = all_revenue / all_matched if all_matched else None
    correlation = pearson(
        (week["youtube_spend"], week["youtube_responses"]) for week in weeks
    )

    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "generated_at": timestamp.isoformat(),
        "data_through": last_date.isoformat(),
        "reporting_window": {
            "start": weeks[0]["week_start"],
            "end": weeks[-1]["week_end"],
            "label": f"{weeks[0]['label'].split('–')[0]}–{weeks[-1]['label'].split('–')[-1]}",
        },
        "summary": {
            "youtube_spend": round(total_spend, 2),
            "youtube_responses": total_youtube,
            "youtube_revenue": round(total_revenue, 2),
            "youtube_aov": round(youtube_aov, 2) if youtube_aov is not None else None,
            "all_survey_aov": round(all_survey_aov, 2)
            if all_survey_aov is not None
            else None,
            "aov_difference": round(youtube_aov - all_survey_aov, 2)
            if youtube_aov is not None and all_survey_aov is not None
            else None,
            "survey_attributed_roas": round(total_revenue / total_spend, 2)
            if total_spend
            else None,
            "cost_per_youtube_response": round(total_spend / total_youtube, 2)
            if total_youtube
            else None,
            "matched_youtube_orders": total_matched,
            "youtube_match_rate": round(total_matched / total_youtube, 4)
            if total_youtube
            else None,
            "same_week_correlation": round(correlation, 2)
            if correlation is not None
            else None,
            "complete_week_count": len(weeks),
        },
        "weeks": weeks,
        "june_creators": creator_assets,
        "featured_videos_by_month": featured_videos_by_month,
        "definitions": {
            "revenue": "Shopify net payments received minus refunds for matched survey orders.",
            "survey_roas": "Matched YouTube survey-order revenue divided by Google Ads spend delivered on YouTube inventory.",
            "caveat": "Survey-attributed first touch, not incremental or platform-attributed revenue.",
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
    shopify_token = get_shopify_token()
    service = google_ads_service(args.google_ads_config)
    start = monday(min(row["date"] for row in survey_rows))
    end = max(row["date"] for row in survey_rows)
    delivery_rows = fetch_youtube_delivery(service, args.customer_id, start, end)
    creator_assets = fetch_june_creator_assets(service, args.customer_id)
    featured_videos_by_month = fetch_featured_videos_by_month(
        service, args.customer_id, start, end
    )
    shopify_values = fetch_shopify_order_values(
        (row["order_id"] for row in survey_rows), shopify_token
    )
    output = build_public_data(
        survey_rows,
        delivery_rows,
        shopify_values,
        creator_assets,
        featured_videos_by_month,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary_output.write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    temporary_output.replace(args.output)


if __name__ == "__main__":
    main()
