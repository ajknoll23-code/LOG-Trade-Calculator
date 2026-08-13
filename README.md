# League of Ordinary Gentlemen — Data Sync

Automates pulling live roster/league data from Sleeper's public API so it's
always one link away instead of a round of screenshots.

## What this does

A GitHub Action runs daily (and on-demand), calls Sleeper's read-only API,
resolves player IDs to real names/positions/ages, and commits the results
into `/data` as plain JSON. From then on, giving Claude your current roster
is one pasted link instead of a screen recording.

## Setup (one-time)

1. **Create the repo.** On GitHub: New repository → name it whatever you
   want (e.g. `loyal-dynasty-data`) → public (raw file links only work
   cleanly on public repos without extra auth headers) → don't initialize
   with a README (you already have one here).

2. **Push these files.**
   ```bash
   cd loyal-repo
   git init
   git add .
   git commit -m "Initial setup"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo-name>.git
   git push -u origin main
   ```

3. **Check `config.json`.** It's already filled in with your league ID and
   username:
   ```json
   {
     "league_id": "1326679131051532288",
     "season": "2026",
     "my_username": "ajk23az",
     "my_team_name": "Landry's Hat"
   }
   ```
   If you ever join a different league or your Sleeper username changes,
   update this file and push — nothing else needs to change.

4. **Enable Actions.** Should be on by default for a new repo. Go to the
   "Actions" tab on GitHub and confirm "Sync Sleeper League Data" is listed.
   Click "Run workflow" to trigger the first sync manually rather than
   waiting for the daily cron.

5. **Confirm it worked.** After the run finishes (~10-20 seconds), you
   should see new files under `/data`:
   - `league_rosters.json` — all 12 teams, fully resolved
   - `my_roster.json` — just your team, in the same shape the trade desk
     tool expects
   - `draft_picks.json` — traded pick ownership
   - `players_cache.json` — the raw ~5MB player pool (cached, refreshed
     at most once/day)
   - `last_synced.json` — timestamp of the last successful run

## Using this with Claude

Once synced, paste the raw file URL as a plain message (GitHub's "raw"
button on any file, or build it as
`https://raw.githubusercontent.com/<you>/<repo>/main/data/my_roster.json`).
Claude can only fetch URLs that appear directly in the conversation — pasting
it yourself is what unlocks the fetch, same as it worked for the direct
Sleeper URLs.

## Schedule

Runs daily at 13:00 UTC (9am ET). Edit the `cron` line in
`.github/workflows/sync.yml` to change this — during the season you may
want it running more often to catch waiver moves same-day.

## Not yet automated

KeepTradeCut and FantasyPros aren't included here — KTC has no official API
(scraping it is fragile and legally gray), and FantasyPros' real API is a
paid product. Screenshots remain the practical path for those until/unless
it's worth revisiting.
