# Patriot Crew YouTube Acquisition Tracker

Client-facing weekly comparison of:

- Post-purchase survey orders selecting YouTube as the first place they heard about Patriot Crew
- Google Ads spend delivered on YouTube inventory across all campaign types

The public site contains aggregate data only. Raw survey exports and Google Ads credentials must never be committed.

## Update the tracker

```bash
python3 scripts/build_data.py \
  --survey-csv "/path/to/survey.csv" \
  --google-ads-config "$HOME/.google-ads.yaml" \
  --output docs/data.json
```

Run the tests, review the aggregate JSON, then commit and push `docs/data.json`.

```bash
python3 -m unittest discover -s tests -v
python3 -m json.tool docs/data.json >/dev/null
```
