# Patriot Crew YouTube Acquisition Tracker

Client-facing weekly comparison of:

- Post-purchase survey orders selecting YouTube as the first place they heard about Patriot Crew
- Google Ads spend delivered on YouTube inventory across all campaign types
- Net Shopify payments for the exact survey orders, used to calculate AOV and survey-attributed ROAS
- June Demand Gen creator videos and Google-reported asset performance

The public site contains aggregate data only. Raw survey exports, Shopify order IDs, and API credentials must never be committed. The local build reads the existing Patriot Crew Shopify token from 1Password and does not pass it to GitHub Actions.

## Update the tracker

```bash
python3 scripts/build_data.py \
  --survey-csv "/path/to/survey.csv" \
  --google-ads-config "/absolute/path/to/google-ads.yaml" \
  --output docs/data.json
```

Run the tests, review the aggregate JSON, then commit and push `docs/data.json`.

```bash
python3 -m unittest discover -s tests -v
python3 -m json.tool docs/data.json >/dev/null
```
