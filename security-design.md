# Security design

## Scope and data flow

`Local post-purchase CSV (PII)` + `Google Ads API (credentialed read)` + `Shopify Admin GraphQL API (credentialed read)` → `local aggregation script` → `aggregate JSON only` → `public GitHub Pages site`.

Trust boundaries are the local filesystem to the parser, Google Ads and Shopify to the local process over TLS, the local git checkout to GitHub, and the public browser to GitHub Pages.

## Data classification and storage

- Source CSV fields include customer email, order number, order ID, free-text responses, and dates. These are customer identifiers/content and remain only in the user's existing local download.
- Google Ads configuration contains OAuth credentials and a developer token. The script reads the existing local configuration; credentials are never copied, logged, committed, or sent to the browser.
- Shopify order IDs are customer identifiers used only for an exact local join. The Shopify token is read from the existing 1Password item, used only for a read query, and never copied, logged, committed, or sent to the browser.
- Shopify order value is business-sensitive data. Only aggregate net revenue, matched-order count, average order value, and survey-attributed ROAS are published. Test and cancelled orders are excluded.
- The repository stores only week start/end, aggregate response count, aggregate YouTube response count, percentage share, aggregate YouTube spend, aggregate delivery metrics, and aggregate order-value metrics.
- No row-level response, email, order identifier, free text, or customer-derived pseudonymous identifier is published.
- Aggregate data may remain in git history for longitudinal reporting. The source export is not duplicated into the project.

## Ingestion decisions

- CSV parsing uses Python's standard `csv` module, not executable deserialization.
- The script rejects source files over 10 MB and requires exact named columns before processing.
- Dates must be ISO `YYYY-MM-DD`; malformed records fail the build.
- Duplicate order IDs are deduplicated in memory before aggregation and are never emitted.
- Survey free text is not rendered, stored, searched, logged, or exported.
- Shopify lookups use typed `gid://shopify/Order/<numeric-id>` values created from digits-only survey IDs. Requests are sent only to the fixed `unclesamscloset.myshopify.com` HTTPS endpoint, in bounded batches, with a timeout and response-size cap.
- The Shopify response schema is allowlisted to order ID, current net payment, currency, test status, and cancellation status. Unknown or malformed monetary values fail the build.

## Deployment decisions

- The site is static and read-only with no authentication, forms, uploads, API, cookies, or runtime secrets.
- GitHub Pages provides TLS and deployment provenance through git history and Actions logs.
- The deploy workflow uses read-only repository contents plus Pages deployment permissions; it has no advertising or survey credentials.
- Shopify enrichment runs locally. The GitHub Pages workflow receives no Shopify credential or customer-level order data.
- Content Security Policy restricts the site to its own static assets and disables framing, plugins, forms, and outbound connections.

## STRIDE review

- Spoofing: there is no user identity or privileged browser action. Repository write access remains the deployment identity boundary.
- Tampering: source-controlled aggregate data, branch history, and Pages deployments make changes auditable. JSON schema checks run before deployment.
- Repudiation: commits and Actions runs identify each published change.
- Information disclosure: the main risk is accidental PII publication. The build allowlists output fields, tests reject forbidden source columns/values, and raw exports are gitignored.
- Information disclosure: aggregate revenue is intentionally public at the requested client-facing URL. Exact order values, order IDs, and Shopify credentials remain local and are checked against the repository before deployment.
- Denial of service: GitHub Pages serves bounded static files; the local parser rejects oversized inputs.
- Elevation of privilege: there is no runtime privilege surface. The workflow receives no Google Ads or survey secrets.

## Abuse cases and residual risk

- Abuse twin: publishing a weekly tracker could accidentally expose a customer row. Mitigation: aggregate-only builder, forbidden-field tests, and raw-export gitignore patterns.
- Abuse twin: a malicious CSV formula or HTML string could become script content. Mitigation: free text is discarded before output and page rendering uses numeric/date fields only.
- Abuse twin: a malformed order ID could alter a Shopify query or request arbitrary resources. Mitigation: accept digits only, construct typed Shopify order GIDs, use GraphQL variables, and fix the destination host in code.
- Abuse twin: Shopify could return an oversized or malformed payload. Mitigation: batched IDs, timeout, response-size cap, strict JSON parsing, and required-field validation.
- Residual risk: weekly counts can be small and may be statistically noisy. They are still not attributable to an individual and the UI labels the signal as directional.
- Residual risk: the public page reveals aggregate media spend. This is knowingly accepted because the requested GitHub Pages scorecard is client-facing; campaign and creator-level spend is not published.
- Residual risk: survey-attributed revenue is not incremental revenue and can include organic YouTube discovery. The UI labels the resulting ROAS as survey-attributed, not platform or causal ROAS.
- Residual risk: the existing Shopify access token may have broader store permissions than this read-only query needs. The process performs no mutations; least-privilege token rotation remains a store-admin follow-up.
