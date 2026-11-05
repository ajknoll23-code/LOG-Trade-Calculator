# LOOG Weekly Newsletter — Release A-NL01R2

Two independent, email-friendly newsletters for the 12-team League of Ordinary Gentlemen dynasty league. **No production values, frozen studies, or core calculator source are changed.**

- **Tuesday, 8 AM Arizona:** `THE AFTERMATH` — prior-week six matchup finals, league median outcomes, biggest starter scores when Sleeper has player points, notable bench performances, recent league moves and a live-ownership-checked free-agent watchlist.
- **Thursday, 8 AM Arizona:** `THE WEEKLY WAR ROOM` — six current matchups, records, historical head-to-head summaries, recent scoring-form estimates, recent moves and a free-agent watchlist.

Source: public read-only Sleeper NFL API, historical league IDs already indexed by the repo, and existing local player/FA metadata. Rivalry records are matched by stable Sleeper owner IDs and do not invent missing history. Predictions are transparent historical-form heuristics, **not betting odds**. Neither edition claims verified injuries, playoff odds, or legal lineup optimization.

## Install (GitHub workflow permission-safe procedure)

GitHub's built-in Actions bot can commit source files but does **not** have permission to add a workflow file. The original A-NL00R2 APPLY was rejected at `git push` for that reason; the repository was not changed. **Do not retry its APPLY.**

1. Upload `A-NL00R3.yml` to `.github/workflows/` on `main` using your GitHub account.
2. Run **A-NL00R3 — PREVIEW_ONLY**. It verifies the exact newsletter files, runs 12 offline tests, and renders six live Sleeper Week 9 previews and six Week 8 final matchups. It cannot send emails.
3. When preview is green, run **A-NL00R3 — APPLY_CONTENT_ONLY**. It commits only these three files: `scripts/newsletters/league_newsletter.py`, `tests/newsletters/test_newsletter.py`, and `docs/LOOG-newsletter-setup.md`. It **never** commits anything under `.github/`.
4. Separately upload **`A-NL01R2.yml`** using your GitHub account to `.github/workflows/A-NL01R2.yml`. This is the only workflow file you must manually install after the content-only apply.
5. Once A-NL01R2 is verified, manually delete the obsolete installer workflows `A-NL00R1.yml`, `A-NL00R2.yml`, and `A-NL00R3.yml` via GitHub's web editor. The Actions bot cannot retire them because that also requires workflow permissions. Their successful historical run logs are preserved.

The installed scheduled workflow is **A-NL01R2 - LOOG Weekly War Room and Aftermath**. With email settings unset, scheduled runs produce reports only and **never send**. GitHub Actions does not automatically extract ZIP files as repository contents.

## Launch without sending emails

1. `Actions` → `A-NL01R2` → `Run workflow`, branch `main`, **edition `pre`**, **week `9`**, **send_email `false`**.
2. Download the `LOOG-newsletter-pre-...` artifact from the run. Inspect the `.html`, `.txt`, and `.json` files. Check team names, all six games, historical H2H, free agents, and scorer data. **This is a true Sleeper API validation**; local tests use synthetic data.
3. Repeat with **edition `post`**, **week `8`**, **send_email `false`**. Make sure all 12 actual final scores and the league median match Sleeper.
4. Only after the preview is approved, configure verified recipient addresses and the authorized sender's SMTP account under **Settings → Secrets and variables → Actions**:
   - Secrets: `NEWSLETTER_TO` (comma-separated opt-in addresses), `NEWSLETTER_FROM`, `SMTP_HOST`, `SMTP_PORT` (465 or 587), `SMTP_USER`, `SMTP_PASSWORD`.
   - Repository variables `NEWSLETTER_SEND_ENABLED` **and** `NEWSLETTER_LAUNCH_APPROVED` must both be set to `true` before any scheduled email can send. Leave both absent/false until ready for automated league-wide sending.
5. Test delivery to your own email first using a manual run with `send_email=true`. **Manual true sends an email; preview mode never sends.** Then enable **both** `NEWSLETTER_SEND_ENABLED=true` and `NEWSLETTER_LAUNCH_APPROVED=true` to allow Tuesday and Thursday scheduled runs to send automatically.

Recipient addresses are sent via **Bcc** and not printed or committed. The email's To header is the sender. Addresses/SMTP credentials are never saved in a generated artifact. To unsubscribe someone, remove their address from `NEWSLETTER_TO`; the footer instructs them to reply to request removal. This is manual list management, not a formal one-click unsubscribe service. Avoid multiple manual sends for the same edition/week.

## Safeguards

- Strict 12 unique teams / 6 Sleeper matchup IDs, correct season and league ID.
- Tuesday recap refuses to render until Sleeper NFL state has advanced beyond the week; all twelve scores must be present.
- No speculative player-of-week or bench substitutions when the API does not provide individual scores.
- Free-agent ranks are hidden if cached utility and canonical free-agent data have different Sleeper sync timestamps, counts, or league ID. Ownership always verified against the live Sleeper rosters.
- Existing frozen research and production values cannot be modified by this read-only workflow; GitHub token has `contents: read`.
- Private email sending requires complete SMTP settings and an explicit manual send or enabling the repository variable.
- The original live preview run 42093320891 passed on November 5, 2026. A-NL00R2 must separately pass its refreshed live preview before installation.

Run offline tests with `python3 -m unittest discover -s tests/newsletters -v` and `python3 scripts/newsletters/league_newsletter.py --selftest`.

## Schedule details

GitHub Actions IANA scheduling uses `America/Phoenix` (`cron: 0 8 * * 2` and `0 8 * * 4`); scheduled jobs can be slightly delayed. If Week 9 Thursday 8 AM is already past, manually run `pre`, `week=9` to preview; **do not pretend it was sent earlier**. The Tuesday `post` job will recap the previous NFL week when Sleeper advances its week state.

## Transaction display quality

The R2 update shows only names actually resolved from the repository player cache. Unknown player IDs are omitted from move descriptions, and records with no verifiable player or draft-pick details are excluded rather than guessed. Drop-only transactions use natural phrasing. This changes editorial display only, not Sleeper transactions or calculator data.
