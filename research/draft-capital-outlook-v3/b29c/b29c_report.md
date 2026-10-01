# Draft Capital Outlook V3 — B29C Completion Gap Audit

Decision: **PASS_B29C_GAP_CLASSIFICATION_ONLY_NO_SCIENCE_DECISION**

This stage classifies the already-frozen B29 unresolved flags only. It does not retry sources, add sources, change candidate sets, alter K/N rules, open 2027, open historical actual capital, compute associations, or change production.

## Per-year unresolved causes

| Year | Candidate cap | Channel trunc. | Unmeasurable rows | Channel errors | K60 LB | K32 LB |
|---:|:---:|---:|---:|---:|---:|---:|
| 2013 | YES | YES | 7 | 29 | 0 | 0 |
| 2014 | YES | YES | 16 | 29 | 0 | 0 |
| 2015 | no | YES | 3 | 90 | 0 | 1 |
| 2016 | no | YES | 10 | 70 | 0 | 2 |
| 2017 | no | YES | 8 | 89 | 0 | 1 |
| 2018 | no | YES | 64 | 89 | 0 | 0 |
| 2019 | no | YES | 109 | 89 | 0 | 1 |
| 2020 | no | YES | 315 | 89 | 0 | 0 |
| 2021 | no | YES | 366 | 85 | 0 | 1 |
| 2022 | no | YES | 271 | 69 | 0 | 0 |
| 2023 | no | YES | 280 | 49 | 1 | 1 |
| 2024 | no | YES | 310 | 49 | 1 | 3 |
| 2025 | no | YES | 161 | 89 | 0 | 3 |
| 2026 | no | YES | 89 | 69 | 1 | 2 |

## Most common unmeasurable reason/status fields

- 1904 × `capture_status=UNRESOLVED`
- 1874 × `capture_error=live_http_403`
- 105 × `capture={mode,sha256,url}`
- 105 × `capture_status=CAPTURED`
- 26 × `capture_error=live_http_404`
- 4 × `capture_error=HTTP 500`

## Most common channel errors

- 33 × `ReadTimeout: HTTPSConnectionPool(host='web.archive.org', port=443): Read timed out. (read timeout=35)`
- 20 × `CC-MAIN-2016-44:HTTP 504`
- 20 × `CC-MAIN-2017-34:HTTP 504`
- 20 × `CC-MAIN-2021-39:HTTP 504`
- 20 × `CC-MAIN-2022-40:HTTP 504`
- 20 × `CC-MAIN-2023-40:HTTP 504`
- 19 × `CC-MAIN-2017-39:HTTP 504`
- 19 × `CC-MAIN-2024-38:HTTP 504`
- 19 × `CC-MAIN-2025-43:HTTP 504`
- 18 × `CC-MAIN-2015-40:HTTP 504`
- 18 × `CC-MAIN-2016-40:HTTP 504`
- 18 × `CC-MAIN-2025-38:HTTP 504`
- 17 × `CC-MAIN-2017-43:HTTP 504`
- 17 × `CC-MAIN-2021-43:HTTP 504`
- 17 × `CC-MAIN-2024-46:HTTP 504`
- 14 × `https://www.nfl.com/sitemap/ways-to-watch-links:HTTP 500`
- 14 × `https://espn.com/sitemap.xml:HTTP 202`
- 14 × `https://espn.com/sitemap_index.xml:HTTP 202`
- 14 × `https://www.espn.com/sitemap.xml:HTTP 202`
- 14 × `https://usatoday.com/sitemap.xml:HTTP 402`
- 14 × `https://usatoday.com/sitemap_index.xml:HTTP 402`
- 14 × `https://www.usatoday.com/money/blueprint/sitemap-news.xml:HTTP 402`
- 14 × `https://www.usatoday.com/money/blueprint/sitemap.xml:HTTP 402`
- 14 × `https://www.usatoday.com/news-sitemap.xml:HTTP 402`
- 14 × `https://www.usatoday.com/online-betting/news-sitemap.xml:HTTP 402`
