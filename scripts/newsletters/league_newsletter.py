#!/usr/bin/env python3
"""League of Ordinary Gentlemen: independent, read-only Sleeper newsletter.

No valuation model, trade weights, roster data, or production files are modified.
The default mode ONLY builds preview files; --send requires explicit SMTP setup.
Requires Python 3.11+, standard library only.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses
from html import escape
import json
import math
import re
import os
from pathlib import Path
import smtplib
import statistics
import sys
import time
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.sleeper.app/v1"
PHOENIX = ZoneInfo("America/Phoenix")


def e(value):
    return escape(str(value if value is not None else ""), quote=True)


def get_json(path: str):
    """Sleeper data. No auth; retry only transient network failures."""
    url = f"{API}/{path.lstrip('/')}"
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "LOOG-Weekly-Ledger/1.0"})
            with urlopen(req, timeout=22) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def read_repo_json(rel: str, default=None):
    p = ROOT / rel
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def score(row):
    raw = row.get("custom_points")
    if raw is None:
        raw = row.get("points")
    if raw is None:
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("Sleeper returned an invalid matchup score")
    return value


def pairs(rows, strict=False):
    """Group by Sleeper's matchup_id; never pair adjacent roster IDs."""
    grouped = defaultdict(list)
    for row in rows or []:
        mid = row.get("matchup_id")
        if mid is not None:
            grouped[str(mid)].append(row)
    result = [sorted(g, key=lambda x: int(x["roster_id"])) for g in grouped.values() if len(g) == 2]
    result.sort(key=lambda g: int(g[0].get("matchup_id")))
    if strict:
        ids = [int(r["roster_id"]) for g in result for r in g]
        if (len(grouped) != 6 or len(result) != 6 or len(ids) != 12
                or len(set(ids)) != 12 or len(rows or []) != 12):
            raise RuntimeError(f"Expected six complete Sleeper matchups for 12 unique teams, received {len(result)} pairs")
    return result


def compute_median(rows):
    values = [score(row) for row in rows]
    if len(values) != 12 or any(v is None for v in values):
        return None
    return statistics.median(values)


def median_result(value, median):
    if value is None or median is None:
        return "—"
    return "W" if value > median else "L" if value < median else "T"


def user_map(users):
    return {str(u["user_id"]): u for u in users}


def team_names(rosters, users):
    index = user_map(users)
    names = {}
    owners = {}
    for r in rosters:
        rid = int(r["roster_id"])
        owner = str(r.get("owner_id") or "")
        u = index.get(owner, {})
        meta = u.get("metadata") or {}
        names[rid] = (meta.get("team_name") or u.get("display_name") or f"Team {rid}").strip()
        owners[rid] = owner
    return names, owners


def histories(api, season, week, current_id, older_ids):
    """Return paired, completed H2H games by stable owner IDs, oldest first."""
    meetings = []
    form = defaultdict(list)
    seasons = [(*x,) for x in older_ids] + [(season, current_id)]
    for yr, lid in seasons:
        league = api(f"league/{lid}")
        rosters = api(f"league/{lid}/rosters")
        users = api(f"league/{lid}/users")
        names, owners = team_names(rosters, users)
        playoff_start = int((league.get("settings") or {}).get("playoff_week_start") or 15)
        final_week = min(week - 1, playoff_start - 1) if str(yr) == str(season) else playoff_start - 1
        for w in range(1, max(0, final_week) + 1):
            rows = api(f"league/{lid}/matchups/{w}")
            for group in pairs(rows):
                a, b = group
                sa, sb = score(a), score(b)
                if sa is None or sb is None or (sa == 0 and sb == 0):
                    continue
                ra, rb = int(a["roster_id"]), int(b["roster_id"])
                oa, ob = owners.get(ra), owners.get(rb)
                if not oa or not ob or oa == ob:
                    continue
                game = {"season": str(yr), "week": w, "owners": (oa, ob),
                        "teams": (names[ra], names[rb]), "scores": (sa, sb)}
                meetings.append(game)
                if str(yr) == str(season):
                    form[ra].append(sa)
                    form[rb].append(sb)
    meetings.sort(key=lambda x: (int(x["season"]), x["week"]))
    return meetings, form


def rivalry(oa, ob, meeting_list):
    theirs = [g for g in meeting_list if set(g["owners"]) == {oa, ob}]
    wins = {oa: 0, ob: 0}
    ties = 0
    for g in theirs:
        a, b = g["owners"]
        x, y = g["scores"]
        if x == y:
            ties += 1
        else:
            wins[a if x > y else b] += 1
    last = theirs[-1] if theirs else None
    last_text = "First documented meeting" if not last else (
        f"Last met {last['season']} Week {last['week']}: "
        f"{last['teams'][0]} {last['scores'][0]:.1f}–{last['scores'][1]:.1f} {last['teams'][1]}")
    return wins[oa], wins[ob], ties, last_text


def point_form(scores):
    if not scores:
        return None
    return 0.55 * statistics.mean(scores[-4:]) + 0.45 * statistics.mean(scores)


def form_probability(a, b):
    """Heuristic, NOT a market/fantasy-platform projection. Need >=3 completed weeks each."""
    if len(a) < 3 or len(b) < 3:
        return None
    ma, mb = point_form(a), point_form(b)
    sa = max(20.0, statistics.stdev(a) if len(a) > 1 else 20.0)
    sb = max(20.0, statistics.stdev(b) if len(b) > 1 else 20.0)
    z = (ma - mb) / math.sqrt(sa * sa + sb * sb)
    return max(0.15, min(0.85, 0.5 * (1 + math.erf(z / math.sqrt(2)))))


def roster_record(r):
    st = r.get("settings") or {}
    return f"{st.get('wins', '?')}-{st.get('losses', '?')}"


def local_player_lookup():
    byid = {}
    raw = read_repo_json("data/league_rosters.json", {}) or {}
    for r in raw.get("rosters", []):
        for section in ("starters", "bench", "taxi", "reserve_ir"):
            for x in r.get(section, []):
                if isinstance(x, dict) and x.get("player_id"):
                    byid[str(x["player_id"])] = x
    return byid


def best_free_agents(rosters, lookup):
    """Retained for old unit-test compatibility. Never read or publish private FA data."""
    return []


def transactions(api, lid, week, lookup, names):
    """Show only source-verifiable named moves; never print placeholder player IDs."""
    output = []
    for w in sorted({max(1, week - 1), week}):
        for t in (api(f"league/{lid}/transactions/{w}") or []):
            if t.get("status") != "complete":
                continue
            typ = t.get("type")
            if typ not in ("trade", "waiver", "free_agent"):
                continue
            involved = [names.get(int(i)) for i in (t.get("roster_ids") or [])]
            involved = [name for name in involved if name]
            if not involved:
                continue

            def verified_names(ids):
                resolved = []
                for pid in (ids or {}):
                    player = lookup.get(str(pid)) or {}
                    name = str(player.get("name") or "").strip()
                    if name and not re.fullmatch(r"Player\s+\d+", name, re.IGNORECASE):
                        resolved.append(name)
                return resolved

            adds = verified_names(t.get("adds"))
            drops = verified_names(t.get("drops"))
            picks = t.get("draft_picks") or []
            details = []
            if adds:
                details.append("added " + ", ".join(adds[:4]))
            if drops and typ != "trade":
                details.append("dropped " + ", ".join(drops[:3]))
            if picks:
                details.append(f"{len(picks)} draft pick(s) involved")
            # A transaction with no verifiable details is omitted, not guessed.
            if not details:
                continue
            teams = " ↔ ".join(involved) if typ == "trade" else ", ".join(involved)
            desc = teams + (": " if typ == "trade" else " ") + "; ".join(details)
            output.append({"id": t.get("transaction_id", ""), "type": typ,
                           "description": desc, "created": int(t.get("created") or 0)})
    unique = {str(x["id"]): x for x in output}
    return sorted(unique.values(), key=lambda x: x["created"], reverse=True)[:8]


def players_of_week(rows, lookup):
    studs, benches = [], []
    for r in rows:
        pts = r.get("players_points") or {}
        if not isinstance(pts, dict):
            continue
        starters = set(str(x) for x in r.get("starters") or [])
        for pid, value in pts.items():
            if not isinstance(value, (int, float)):
                continue
            p = lookup.get(str(pid)) or {}
            if not p.get("name"):
                continue
            entry = {"name": p["name"], "pos": p.get("pos") or p.get("position") or "",
                     "points": float(value), "roster_id": int(r["roster_id"])}
            if str(pid) in starters:
                studs.append(entry)
            elif value >= 20:
                benches.append(entry)
    return sorted(studs, key=lambda x: x["points"], reverse=True)[:6], sorted(benches, key=lambda x: x["points"], reverse=True)[:5]


def build_payload(api, config, edition, week_override=None):
    lid, season = str(config["league_id"]), int(config["season"])
    state = api("state/nfl")
    if str(state.get("season")) != str(season):
        raise RuntimeError("NFL season differs from config.json; update configuration before publishing")
    week = int(week_override or (int(state["week"]) - (edition == "post")))
    if week < 1 or week > 18:
        raise RuntimeError(f"Unpublishable NFL week {week}; use --week for a manual preview")
    league = api(f"league/{lid}")
    if str(league.get("season")) != str(season):
        raise RuntimeError("Sleeper league season does not match config")
    rosters = api(f"league/{lid}/rosters")
    users = api(f"league/{lid}/users")
    names, owners = team_names(rosters, users)
    if len(rosters) != 12 or len(names) != 12 or len(set(owners.values())) != 12:
        raise RuntimeError("Incomplete owner/roster mapping, expected 12 unique teams")
    rows = api(f"league/{lid}/matchups/{week}")
    games = pairs(rows, strict=True)
    current_nfl_week = int(state.get("week") or 0)
    if edition == "post" and week >= current_nfl_week:
        raise RuntimeError("Recap withheld: Sleeper has not advanced beyond the requested NFL week")
    if edition == "post" and (any(score(r) is None for g in games for r in g) or all(score(r) == 0 for g in games for r in g)):
        raise RuntimeError("Sleeper does not yet show finalized scores for all twelve teams")
    paired_ids = {int(r["roster_id"]) for g in games for r in g}
    if paired_ids != set(names):
        raise RuntimeError("Matchups do not cover the same twelve unique league rosters")
    older = []
    th = read_repo_json("data/trade_history.json", {}) or {}
    for s in th.get("seasons", []):
        if int(s.get("season", 0)) < season and s.get("league_id"):
            older.append((int(s["season"]), str(s["league_id"])))
    meeting_list, form = histories(api, season, week + (edition == "post"), lid, older)
    live_rosters = {int(r["roster_id"]): r for r in rosters}
    outgames = []
    median = compute_median(rows) if edition == "post" else None
    for group in games:
        a, b = group
        aid, bid = int(a["roster_id"]), int(b["roster_id"])
        oa, ob = owners[aid], owners[bid]
        wa, wb, ties, last = rivalry(oa, ob, [g for g in meeting_list if not (g["season"] == str(season) and g["week"] == week)])
        pa, pb = point_form(form[aid]), point_form(form[bid])
        prob = form_probability(form[aid], form[bid]) if edition == "pre" else None
        outgames.append({"a": aid, "b": bid, "name_a": names[aid], "name_b": names[bid],
                         "record_a": roster_record(live_rosters[aid]), "record_b": roster_record(live_rosters[bid]),
                         "score_a": score(a), "score_b": score(b), "median_a": median_result(score(a), median),
                         "median_b": median_result(score(b), median), "series_a": wa, "series_b": wb,
                         "series_t": ties, "last": last, "form_a": pa, "form_b": pb, "prob_a": prob,
                         "final": edition == "post"})
    if edition == "post":
        outgames.sort(key=lambda x: abs(x["score_a"] - x["score_b"]))
    lookup = local_player_lookup()
    studs, benches = players_of_week(rows, lookup) if edition == "post" else ([], [])
    return {"edition": edition, "week": week, "season": season, "league": league.get("name") or "League of Ordinary Gentlemen",
            "games": outgames, "median": median, "names": names,
            "transactions": transactions(api, lid, week, lookup, names), "studs": studs, "benches": benches,
            "data_asof": datetime.now(PHOENIX).strftime("%B %-d, %Y %I:%M %p MST"), "league_id": lid}


def card(g, edition):
    if edition == "pre":
        scoreline = (f"Recent scoring baseline: {g['form_a']:.1f} vs {g['form_b']:.1f} points" if g["form_a"] is not None and g["form_b"] is not None else "Not enough recent scoring data for a form baseline")
        odds = (f"Form-model estimate: {100 * g['prob_a']:.0f}% / {100 * (1 - g['prob_a']):.0f}%" if g["prob_a"] is not None else "Win probability withheld: insufficient games")
        lead = f"<div class='statline'>{e(scoreline)} · {e(odds)}</div>"
    else:
        a, b = g["score_a"], g["score_b"]
        winner = "Tie" if a == b else (g["name_a"] if a > b else g["name_b"])
        lead = f"<div class='result'>{a:.2f} <span>–</span> {b:.2f}</div><div class='statline'>Winner: {e(winner)} · Median: {g['median_a']} / {g['median_b']}</div>"
    series = f"Historical series: {g['series_a']}-{g['series_b']}" + (f"-{g['series_t']} ties" if g["series_t"] else "")
    return f"""<section class='game'><div class='teams'><strong>{e(g['name_a'])}</strong><span class='versus'>VS</span><strong>{e(g['name_b'])}</strong></div>
    <div class='records'><span>{e(g['record_a'])}</span><span>Season record</span><span>{e(g['record_b'])}</span></div>
    {lead}<p class='history'>{e(series)}. {e(g['last'])}</p></section>"""


def list_rows(items):
    return "".join("<li>" + e(x) + "</li>" for x in items)


def render_html(payload):
    preview = payload["edition"] == "pre"
    heading = "THE WEEKLY WAR ROOM" if preview else "THE AFTERMATH"
    subtitle = "Thursday matchup preview" if preview else "Tuesday results recap"
    allgames = "".join(card(g, payload["edition"]) for g in payload["games"])
    best = payload["games"][0] if not preview else None
    side = ""
    if best:
        side += f"<section class='feature'><h2>Closest Matchup</h2><p>{e(best['name_a'])} vs {e(best['name_b'])}: " \
                f"a {abs(best['score_a']-best['score_b']):.2f}-point margin.</p></section>"
    if payload["median"] is not None:
        side += f"<p class='median'>League median: <strong>{payload['median']:.2f}</strong> points. Median W/L is shown for each team above.</p>"
    if payload["studs"]:
        side += "<section><h2>Sunday Heroes</h2><ul>" + list_rows([f"{p['name']} ({payload['names'].get(p['roster_id'])}): {p['points']:.2f} points" for p in payload["studs"]]) + "</ul></section>"
    if payload["benches"]:
        side += "<section><h2>Bench Fireworks</h2><p class='fine'>High-scoring reserves; not an assertion that a legal lineup swap was available.</p><ul>" + list_rows([f"{p['name']} ({payload['names'].get(p['roster_id'])}): {p['points']:.2f} bench points" for p in payload["benches"]]) + "</ul></section>"
    if payload["transactions"]:
        side += "<section><h2>Trade & Waiver Wire</h2><ul>" + list_rows([x["description"] for x in payload["transactions"][:6]]) + "</ul></section>"
    caveat = "Projections are transparent, historical-score form estimates, not betting odds, sportsbook lines, or proprietary player FVs." if preview else "Scores are from Sleeper. No assertion about optimized lineups is made without reliable eligibility analysis."
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{e(payload['league'])} | {heading} | Week {payload['week']}</title><style>
    body{{margin:0;background:#f4f1e9;color:#202923;font:16px/1.55 system-ui,-apple-system,Segoe UI,Arial,sans-serif}}
    .wrap{{max-width:650px;margin:auto;background:white;min-height:100vh}}header{{background:#092e25;color:#fff;padding:38px 28px 30px}}
    .kicker{{letter-spacing:3px;color:#d5b665;font-size:12px;font-weight:800}}h1{{font-family:Georgia,serif;font-size:38px;margin:12px 0 8px;line-height:1.05}}
    header p{{color:#c9dbd4;margin:7px 0}}main{{padding:25px}}h2{{font:700 25px Georgia,serif;color:#113e31;margin:26px 0 12px}}
    .game{{background:#0b3228;color:#fff;border-radius:13px;padding:19px 18px;margin:16px 0}}
    .game:nth-of-type(even){{background:#194438}}.teams{{display:grid;grid-template-columns:1fr 35px 1fr;align-items:center;gap:9px;text-align:center;font-size:17px}}
    .versus{{color:#d8b663;font-weight:900}}.records{{display:grid;grid-template-columns:1fr 1.3fr 1fr;text-align:center;font-size:14px;border-block:1px solid #537167;padding:6px;margin-top:14px}}
    .records span:nth-child(2){{color:#b9cbc4;font-size:12px}}.result{{font-size:32px;font-weight:800;color:#f2ca70;text-align:center;margin-top:12px}}
    .result span{{font-weight:400;color:white}}.statline{{color:#e4e1ce;text-align:center;font-size:13px;margin-top:10px}}
    .history{{margin-bottom:0;border-top:1px solid #537167;padding-top:12px;font-size:13px;color:#c9dbd3}}
    section.feature{{border-left:4px solid #d4b55c;padding:1px 15px;background:#faf6e9}}ul{{padding-left:21px}}li{{margin:9px 0}}
    .median{{background:#e9f3ef;padding:14px;border-radius:8px}}.fine{{font-size:12px;color:#59665e}}footer{{padding:26px;font-size:12px;background:#eef2ed;color:#485950}}
    @media(max-width:440px){{main{{padding:15px}}.teams{{font-size:14px}}h1{{font-size:32px}}}}
    </style></head><body><div class='wrap'><header><div class='kicker'>LEAGUE OF ORDINARY GENTLEMEN</div>
    <h1>{heading}</h1><p>2026 Week {payload['week']} · {e(subtitle)}</p><p>{e(payload['league'])}</p></header><main>
    <section class='feature'><p>{'Every team faces an opponent and the league median this week, so two wins are possible.' if preview else 'Final head-to-head results and league-median results are shown separately for all 12 teams.'}</p></section>
    <h2>All Six Matchups</h2>{allgames}{side}</main><footer>Data checked: {e(payload['data_asof'])}. {e(caveat)}
    <p>Editorial coverage only. Independent of the frozen legacy dynasty valuation engine. This independent newsletter is not affiliated with Sleeper.</p></footer></div></body></html>"""


def render_text(payload):
    head = "THE WEEKLY WAR ROOM" if payload["edition"] == "pre" else "THE AFTERMATH"
    lines = [f"{payload['league']} | {head} | {payload['season']} Week {payload['week']}", "=" * 55, ""]
    for g in payload["games"]:
        lines.append(f"{g['name_a']} ({g['record_a']}) vs {g['name_b']} ({g['record_b']})")
        if payload["edition"] == "post":
            lines.append(f"Final: {g['score_a']:.2f} to {g['score_b']:.2f}; median W/L {g['median_a']}/{g['median_b']}")
        else:
            lines.append("Recent scoring baseline: " + (f"{g['form_a']:.1f} vs {g['form_b']:.1f}" if g['form_a'] is not None and g['form_b'] is not None else "not available"))
            lines.append("Form-model win estimate: " + (f"{g['prob_a']*100:.0f}% / {(1-g['prob_a'])*100:.0f}%" if g['prob_a'] is not None else "not enough history"))
        lines.extend([f"All-time H2H: {g['series_a']}-{g['series_b']}; {g['last']}", ""])
    if payload["median"] is not None:
        lines.append(f"League median: {payload['median']:.2f}")
    for title, entries in (("Weekly MVPs", [f"{p['name']} {p['points']:.2f}" for p in payload['studs']]), ("Recent moves", [x['description'] for x in payload['transactions']])):
        if entries:
            lines.extend(["", title.upper()] + ["- " + x for x in entries])
    lines.append("\nSources: Sleeper league API and completed league transactions. Generated " + payload["data_asof"])
    return "\n".join(lines) + "\n"


def send_email(subject, html, plain):
    required = ["NEWSLETTER_TO", "NEWSLETTER_FROM", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Email blocked; missing settings: " + ", ".join(missing))
    addresses = [a.strip() for _, a in getaddresses([os.environ["NEWSLETTER_TO"]])]
    if (not addresses or len(set(addresses)) != len(addresses)
            or any("@" not in a or "\r" in a or "\n" in a for a in addresses)):
        raise RuntimeError("Email blocked: invalid or duplicated newsletter recipients")
    sender = os.environ["NEWSLETTER_FROM"].strip()
    if "@" not in sender or "\r" in sender or "\n" in sender:
        raise RuntimeError("Email blocked: invalid sender address")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = sender
    msg["Bcc"] = ", ".join(addresses)
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT") or "465")
    if port not in (465, 587):
        raise RuntimeError("Email blocked: only SMTP 465 (SSL) and 587 (STARTTLS) supported")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as client:
            client.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            client.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as client:
            client.starttls()
            client.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            client.send_message(msg)


def selftest():
    sample = [{"roster_id": i, "matchup_id": (i+1)//2, "points": float(i)} for i in range(1, 13)]
    assert len(pairs(sample, strict=True)) == 6
    assert compute_median(sample) == 6.5
    assert median_result(6.0, 6.5) == "L" and median_result(7, 6.5) == "W"
    assert form_probability([100, 120], [100, 80]) is None
    assert form_probability([150, 150, 150], [75, 75, 75]) > .5
    g = [{"season": "2024", "week": 1, "owners": ("a", "b"), "teams": ("A", "B"), "scores": (120, 100)}]
    assert rivalry("a", "b", g)[:3] == (1, 0, 0)
    try:
        pairs(sample[:10], strict=True)
        raise AssertionError("Incomplete matchups must fail closed")
    except RuntimeError:
        pass
    print("SELFTEST GREEN: pairing, median, no unsupported prediction, rivalry, completeness")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--edition", choices=["pre", "post"], default="pre")
    p.add_argument("--week", type=int, help="Manual week override; keep official season")
    p.add_argument("--output-dir", type=Path, default=Path("out/newsletters"))
    p.add_argument("--send", action="store_true", help="Explicitly authorize SMTP send; requires secrets")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    cfg = read_repo_json("config.json")
    if not cfg or not cfg.get("league_id"):
        raise RuntimeError("config.json missing/invalid; run from actual repository")
    payload = build_payload(get_json, cfg, args.edition, args.week)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{payload['season']}-W{payload['week']:02d}-{'preview' if args.edition == 'pre' else 'recap'}"
    html = render_html(payload)
    plain = render_text(payload)
    html_path = args.output_dir / (stem + ".html")
    text_path = args.output_dir / (stem + ".txt")
    html_path.write_text(html, encoding="utf-8")
    text_path.write_text(plain, encoding="utf-8")
    (args.output_dir / (stem + ".json")).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"CREATED: {html_path}, {text_path}; 6 validated matchups; SEND={args.send}")
    if args.send:
        subject = f"🏈 LOOG Week {payload['week']} — {'Matchups & Rivalries' if args.edition == 'pre' else 'The Aftermath'}"
        send_email(subject, html, plain)
        print("EMAIL SENT")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("NEWSLETTER FAILED CLOSED:", exc, file=sys.stderr)
        raise SystemExit(1)
