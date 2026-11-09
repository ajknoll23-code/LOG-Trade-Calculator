#!/usr/bin/env python3
"""Build a read-only IDP season usage snapshot from owner-supplied CSV.

Only matches player identities when name AND NFL team resolve unambiguously
against the latest LOG Sleeper free-agent/roster snapshots. Does not touch FV.
"""
import argparse
import csv
import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HEADERS = [
    'PLAYER','POSITION','TEAM','GAMES PLAYED','TOTAL DEFENSIVE SNAPS',
    'TACKLE RATE','BOX RATE','SLOT RATE','DEEP RATE','DL RATE','WIDE CB RATE',
]
POS = {'LB', 'S', 'CB', 'ED', 'DI'}
RATE_MAP = {
    'TACKLE RATE':'tackle_rate_pct', 'BOX RATE':'box_rate_pct',
    'SLOT RATE':'slot_rate_pct', 'DEEP RATE':'deep_rate_pct',
    'DL RATE':'dl_rate_pct','WIDE CB RATE':'wide_cb_rate_pct',
}


def name_key(value, strip_suffix=False):
    raw = unicodedata.normalize('NFKD', value)
    raw = ''.join(c for c in raw if not unicodedata.combining(c)).lower()
    bits = re.findall(r'[a-z0-9]+', raw)
    if strip_suffix and bits and bits[-1] in ('jr','sr','ii','iii','iv','v'):
        bits.pop()
    return ''.join(bits)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def all_roster_players(roster):
    for team in roster['rosters']:
        for slot in ('starters','bench','taxi','reserve_ir'):
            yield from team.get(slot, [])


def known_players(free, roster):
    if str(free.get('league_id')) != str(roster.get('league_id')):
        raise ValueError('League IDs do not match')
    free_players = free.get('free_agents', [])
    if not isinstance(free_players, list) or len(free_players) < 500:
        raise ValueError('Free-agent pool is incomplete')
    if len(roster.get('rosters', [])) != 12:
        raise ValueError('Expected 12 current LOG rosters')
    indexed = defaultdict(dict)
    ids_seen = set()
    for p in list(free_players) + list(all_roster_players(roster)):
        pid = str(p.get('player_id', '')).strip()
        team = str(p.get('team') or '').strip().upper()
        name = str(p.get('name') or '').strip()
        if not (pid.isdigit() and name and team):
            continue
        # Repeats with the same stable Sleeper ID are fine, conflicting records are not.
        if pid in ids_seen:
            continue
        ids_seen.add(pid)
        for relaxed in (False, True):
            k = (team, name_key(name, relaxed), relaxed)
            indexed[k][pid] = (pid, name)
    return indexed


def resolve(indexed, team, name):
    for relaxed, label in ((False,'exact_name_team'),(True,'suffix_normalized_name_team')):
        choices = indexed.get((team,name_key(name,relaxed),relaxed), {})
        if len(choices) == 1:
            return next(iter(choices)),label
        if len(choices) > 1:
            return None,'ambiguous_identity'
    return None,'unmatched_identity'


def percent(s, required=False):
    s = s.strip()
    if not s:
        if required:
            raise ValueError('Missing required rate')
        return None
    if not s.endswith('%'):
        raise ValueError('Expected percentage string: '+repr(s))
    v = float(s[:-1])
    if not 0 <= v <= 100:
        raise ValueError('Percentage outside 0–100: '+repr(s))
    return round(v, 2)


def build(source, free, roster):
    raw = Path(source).read_bytes()
    rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    if not rows or list(rows[0]) != HEADERS:
        raise ValueError('CSV header changed: aborting rather than misreading metrics')
    if len(rows) != 436:
        raise ValueError('Expected 436 rows from the owner-provided 2026 snapshot')
    ids = known_players(read_json(free),read_json(roster))
    out, seen = [], set()
    for i, r in enumerate(rows, 2):
        try:
            name,team,pos = r['PLAYER'].strip(),r['TEAM'].strip().upper(),r['POSITION'].strip().upper()
            if not name or not re.fullmatch(r'[A-Z]{2,3}',team) or pos not in POS:
                raise ValueError('Invalid player/team/position')
            row_key = (name_key(name),team,pos)
            if row_key in seen:
                raise ValueError('Duplicate player/team/position')
            seen.add(row_key)
            games,snaps=int(r['GAMES PLAYED']),int(r['TOTAL DEFENSIVE SNAPS'])
            if not 1<=games<=20 or not 200<=snaps<=2000:
                raise ValueError('Invalid games or defensive snaps')
            metrics={dst:percent(r[src]) for src,dst in RATE_MAP.items()}
            total_align=sum(metrics[x] for x in ('box_rate_pct','slot_rate_pct','deep_rate_pct','dl_rate_pct','wide_cb_rate_pct'))
            if not 98<=total_align<=102:
                raise ValueError('Alignment sum inconsistent with 100%')
            pid,matched_by=resolve(ids,team,name)
            out.append({
                'name':name,'team_at_source':team,'position':pos,
                'games_played':games,'defensive_snaps':snaps,
                'snaps_per_game':round(snaps/games,1),
                **metrics,'sleeper_id':pid,'identity_status':matched_by
            })
        except Exception as err:
            raise ValueError(f'CSV line {i} ({r.get("PLAYER", "unknown")}): {err}') from err
    c=Counter(p['position'] for p in out)
    if dict(c) != {'LB':75,'ED':91,'DI':93,'S':85,'CB':92}:
        raise ValueError('Unexpected position population: '+str(dict(c)))
    # Season and snapshot date are owner-supplied metadata; no invented week-range.
    baseline={}
    for position in ('LB','S','CB','ED','DI'):
        pool=[p['tackle_rate_pct'] for p in out if p['position']==position and p['tackle_rate_pct'] is not None]
        baseline[position]={
            'players':c[position], 'with_tackle_rate':len(pool),
            'median_tackle_rate_pct':round(statistics.median(pool),2),
            'at_least_10_pct':sum(x>=10 for x in pool),
            'at_least_12_pct':sum(x>=12 for x in pool),
            'at_least_15_pct':sum(x>=15 for x in pool)
        }
    statuses=Counter(p['identity_status'] for p in out)
    return {
        'schema_version':1,
        'source':'Owner-provided 2026 IDP defensive alignment/tackle rate CSV',
        'source_received_date':'2026-11-09',
        'source_week_range':'not_stated_in_csv',
        'source_sha256':hashlib.sha256(raw).hexdigest(),
        'minimum_defensive_snaps_in_source':200,
        'metric_units':'percentage_points',
        'policy':'READ_ONLY_RESEARCH_NOT_FV_OR_PROJECTION',
        'data_notes':[
            'Tackle rate is supplied by the source CSV; do not back-calculate solo/assist totals.',
            'The CSV provides season aggregates, not consecutive weekly observations, pressure rates, or snap share.',
            'NULL tackle rate is missing data, never zero.',
            'Match requires a unique Sleeper ID plus matching team; unresolved identities are not shown as confirmed available.'
        ],
        'counts':{'players':len(out),'positions':dict(c),'identity_status':dict(statuses)},
        'baseline':baseline,
        'players':out
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default='research/idp-opportunity/source/2026-11-09-idp-season-usage.csv')
    ap.add_argument('--free',default='data/free_agents.json')
    ap.add_argument('--rosters',default='data/league_rosters.json')
    ap.add_argument('--out',default='data/idp_usage_2026_season.json')
    args=ap.parse_args()
    document=build(args.source,args.free,args.rosters)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(document,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Validated source SHA:',document['source_sha256'])
    print('Players:',document['counts']['players'])
    print('Population by position:',document['counts']['positions'])
    print('Sleeper identity:',document['counts']['identity_status'])
    print('Tackle-rate median, position:',{k:v['median_tackle_rate_pct'] for k,v in document['baseline'].items()})
    print('Wrote',dest)

if __name__=='__main__':
    main()
