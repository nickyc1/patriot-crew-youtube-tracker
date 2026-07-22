import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scripts.build_data import (
    DATE,
    ORDER_ID,
    SURVEY_OTHER,
    SURVEY_QUESTION,
    build_public_data,
    read_survey,
)


class BuildDataTests(unittest.TestCase):
    def test_csv_is_deduplicated_and_discards_customer_fields(self):
        content = (
            f"{DATE},{ORDER_ID},{SURVEY_QUESTION},{SURVEY_OTHER},Email adress\n"
            "2026-06-08,123,Youtube,,customer@example.com\n"
            "2026-06-08,123,Youtube,,customer@example.com\n"
            "2026-06-09,124,Facebook,,other@example.com\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.csv"
            path.write_text(content, encoding="utf-8")
            rows = read_survey(path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(int(row["youtube"]) for row in rows), 1)
        self.assertNotIn("Email adress", rows[0])
        self.assertNotIn(ORDER_ID, rows[0])
        self.assertEqual(rows[0]["order_id"], "123")

    def test_public_output_contains_aggregates_only(self):
        survey = [
            {"order_id": "101", "date": date(2026, 6, 8), "youtube": True},
            {"order_id": "102", "date": date(2026, 6, 9), "youtube": False},
            {"order_id": "103", "date": date(2026, 6, 15), "youtube": True},
            {"order_id": "104", "date": date(2026, 6, 22), "youtube": True},
        ]
        delivery = [
            {"date": date(2026, 6, 8), "spend": 100.0, "impressions": 1000, "clicks": 10},
            {"date": date(2026, 6, 15), "spend": 200.0, "impressions": 2000, "clicks": 20},
            {"date": date(2026, 6, 22), "spend": 300.0, "impressions": 3000, "clicks": 30},
        ]
        output = build_public_data(
            survey,
            delivery,
            {"101": 125.0, "102": 75.0, "103": 150.0, "104": 175.0},
            [],
            [],
            generated_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
        )
        rendered = str(output).casefold()

        self.assertNotIn("email", rendered)
        self.assertNotIn("order id", rendered)
        self.assertNotIn("customer@example.com", rendered)
        self.assertEqual(output["summary"]["youtube_responses"], 2)
        self.assertEqual(output["summary"]["youtube_revenue"], 275.0)
        self.assertEqual(output["summary"]["youtube_aov"], 137.5)
        self.assertEqual(output["weeks"][0]["youtube_spend"], 100.0)

    def test_partial_weeks_are_not_published(self):
        survey = [
            {"order_id": "101", "date": date(2026, 6, 3), "youtube": True},
            {"order_id": "102", "date": date(2026, 6, 8), "youtube": True},
            {"order_id": "103", "date": date(2026, 6, 15), "youtube": True},
            {"order_id": "104", "date": date(2026, 6, 22), "youtube": True},
        ]
        delivery = [
            {"date": date(2026, 6, 3), "spend": 50.0, "impressions": 1, "clicks": 1},
            {"date": date(2026, 6, 8), "spend": 100.0, "impressions": 1, "clicks": 1},
            {"date": date(2026, 6, 15), "spend": 100.0, "impressions": 1, "clicks": 1},
        ]
        output = build_public_data(survey, delivery)

        self.assertEqual(output["weeks"][0]["week_start"], "2026-06-08")
        self.assertEqual(output["weeks"][-1]["week_end"], "2026-06-21")
        self.assertTrue(all("is_partial" not in week for week in output["weeks"]))


if __name__ == "__main__":
    unittest.main()
