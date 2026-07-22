# Security design

## Scope and data flow

`Local post-purchase CSV (PII)` + `Google Ads API (credentialed read)` → `local aggregation script` → `aggregate JSON only` → `public GitHub Pages site`.

Trust boundaries are the local filesystem to the parser, Google Ads to the local process, the local git checkout to GitHub, and the public browser to GitHub Pages.

## Data classification and storage

- Source CSV fields include customer email, order number, order ID, free-text responses, and dates. These are customer identifiers/content and remain only in the user's existing local download.
- Google Ads configuration contains OAuth credentials and a developer token. The script reads the existing local configuration; credentials are never copied, logged, committed, or sent to the browser.
- The repository stores only week start/end, aggregate response count, aggregate YouTube response count, percentage share, aggregate YouTube spend, and aggregate delivery metrics.
- No row-level response, email, order identifier, free text, or customer-derived pseudonymous identifier is published.
- Aggregate data may remain in git history for longitudinal reporting. The source export is not duplicated into the project.

## Ingestion decisions

- CSV parsing uses Python's standard `csv` module, not executable deserialization.
- The script rejects source files over 10 MB and requires exact named columns before processing.
- Dates must be ISO `YYYY-MM-DD`; malformed records fail the build.
- Duplicate order IDs are deduplicated in memory before aggregation and are never emitted.
- Survey free text is not rendered, stored, searched, logged, or exported.

## Deployment decisions

- The site is static and read-only with no authentication, forms, uploads, API, cookies, or runtime secrets.
- GitHub Pages provides TLS and deployment provenance through git history and Actions logs.
- The deploy workflow uses read-only repository contents plus Pages deployment permissions; it has no advertising or survey credentials.
- Content Security Policy restricts the site to its own static assets and disables framing, plugins, forms, and outbound connections.

## STRIDE review

- Spoofing: there is no user identity or privileged browser action. Repository write access remains the deployment identity boundary.
- Tampering: source-controlled aggregate data, branch history, and Pages deployments make changes auditable. JSON schema checks run before deployment.
- Repudiation: commits and Actions runs identify each published change.
- Information disclosure: the main risk is accidental PII publication. The build allowlists output fields, tests reject forbidden source columns/values, and raw exports are gitignored.
- Denial of service: GitHub Pages serves bounded static files; the local parser rejects oversized inputs.
- Elevation of privilege: there is no runtime privilege surface. The workflow receives no Google Ads or survey secrets.

## Abuse cases and residual risk

- Abuse twin: publishing a weekly tracker could accidentally expose a customer row. Mitigation: aggregate-only builder, forbidden-field tests, and raw-export gitignore patterns.
- Abuse twin: a malicious CSV formula or HTML string could become script content. Mitigation: free text is discarded before output and page rendering uses numeric/date fields only.
- Residual risk: weekly counts can be small and may be statistically noisy. They are still not attributable to an individual and the UI labels the signal as directional.
- Residual risk: the public page reveals aggregate media spend. This is knowingly accepted because the requested GitHub Pages scorecard is client-facing; campaign and creator-level spend is not published.
