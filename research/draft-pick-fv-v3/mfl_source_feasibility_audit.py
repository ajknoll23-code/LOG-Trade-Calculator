#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research' / 'draft-pick-fv-v3'
JSON_OUT = OUT / 'mfl_source_feasibility_v1.json'
MD_OUT = OUT / 'mfl_source_feasibility_v1.md'
MAN_OUT = OUT / 'mfl_source_feasibility_manifest_v1.json'

YEARS = list(range(2018, 2024))
SEARCH_TERMS = [
    'dynasty', 'superflex', 'super flex', '2qb', '2 qb', 'rookie',
    'idp', 'devy', 'empire', 'contract', 'salary', 'taxi',
    'fantasy', 'football', 'league',
]
BASE = 'https://api.myfantasyleague.com'
MAX_PER_TERM = 50
MAX_CANDIDATES_PER_YEAR = 150
SLEEP = 1.02

# Feasibility heuristics only — NOT V3 scientific/model-selection gates.
MIN_FULL6_PER_YEAR = 20
MIN_FULL4_PER_YEAR = 25
MIN_IDP_FULL6_PER_YEAR = 5

class AuditError(RuntimeError):
    pass

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stable_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

def safe_int(x: Any) -> int | None:
    try:
        return int(str(x))
    except (TypeError, ValueError):
        return None

def norm(x: Any) -> str:
    return re.sub(r'\s+', ' ', str(x or '').strip()).lower()

def api_url(year: int, endpoint: str, **params: Any) -> str:
    q = {'TYPE': endpoint, 'JSON': 1}
    q.update({k: v for k, v in params.items() if v is not None})
    return f'{BASE}/{year}/export?' + urlencode(q)

def get_json(session: requests.Session, url: str, retries: int = 4) -> dict[str, Any]:
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise AuditError('non-object JSON')
            time.sleep(SLEEP)
            return data
        except (requests.RequestException, ValueError, AuditError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    raise AuditError(f'{url}: {last}')

def search_ids(data: dict[str, Any]) -> list[str]:
    leagues = data.get('leagues')
    if not isinstance(leagues, dict):
        return []
    out = []
    for row in as_list(leagues.get('league')):
        if not isinstance(row, dict):
            continue
        lid = row.get('id') or row.get('league_id') or row.get('leagueId')
        if lid is not None:
            out.append(str(lid))
    return out

def league_obj(data: dict[str, Any]) -> dict[str, Any] | None:
    x = data.get('league')
    return x if isinstance(x, dict) else None

def franchise_count(lg: dict[str, Any]) -> int | None:
    f = lg.get('franchises')
    return safe_int(f.get('count')) if isinstance(f, dict) else None

def qb_limit(lg: dict[str, Any]) -> str | None:
    starters = lg.get('starters')
    if not isinstance(starters, dict):
        return None
    for row in as_list(starters.get('position')):
        if isinstance(row, dict) and str(row.get('name', '')).upper() == 'QB':
            v = str(row.get('limit', '')).strip()
            return v or None
    return None

def is_idp(lg: dict[str, Any]) -> bool:
    starters = lg.get('starters')
    if not isinstance(starters, dict):
        return False
    x = starters.get('idp_starters')
    if isinstance(x, str):
        return bool(x.strip())
    return bool(x)

def qualifies_settings(lg: dict[str, Any]) -> bool:
    keeper = norm(lg.get('keeperType'))
    pool = norm(lg.get('draftPlayerPool'))
    return (
        franchise_count(lg) == 12
        and keeper == 'dynasty'
        and qb_limit(lg) in {'1-2', '2'}
        and pool.startswith('rook')
    )

def draft_picks(data: dict[str, Any]) -> list[dict[str, Any]]:
    root = data.get('draftResults')
    if not isinstance(root, dict):
        return []
    out = []
    for unit in as_list(root.get('draftUnit')):
        if not isinstance(unit, dict):
            continue
        out.extend(x for x in as_list(unit.get('draftPick')) if isinstance(x, dict))
    return out

def depth(picks: list[dict[str, Any]]) -> dict[str, Any]:
    filled = Counter()
    for p in picks:
        rnd = safe_int(p.get('round'))
        if rnd and str(p.get('player') or '').strip():
            filled[rnd] += 1

    def complete(n: int) -> bool:
        return all(filled.get(r, 0) >= 12 for r in range(1, n + 1))

    return {
        'filled_by_round': {str(r): filled.get(r, 0) for r in range(1, 7)},
        'full4': complete(4),
        'full5': complete(5),
        'full6': complete(6),
    }

def discover(session: requests.Session, year: int) -> tuple[list[str], dict[str, Any]]:
    term_counts = {}
    all_ids = set()
    errors = {}
    for term in SEARCH_TERMS:
        try:
            rows = search_ids(get_json(session, api_url(year, 'leagueSearch', SEARCH=term)))
        except AuditError as exc:
            rows = []
            errors[term] = str(exc)
        rows = sorted(set(rows), key=lambda x: stable_key(f'{year}|{term}|{x}'))[:MAX_PER_TERM]
        term_counts[term] = len(rows)
        all_ids.update(rows)

    ordered = sorted(all_ids, key=lambda x: stable_key(f'{year}|candidate|{x}'))
    selected = ordered[:MAX_CANDIDATES_PER_YEAR]
    return selected, {
        'term_counts_after_cap': term_counts,
        'search_errors': errors,
        'unique_union_before_year_cap': len(ordered),
        'selected_for_settings_probe': len(selected),
    }

def probe_year(session: requests.Session, year: int) -> dict[str, Any]:
    ids, discovery = discover(session, year)
    counts = Counter()
    failures = Counter()
    qbs = Counter()
    pools = Counter()
    keepers = Counter()
    qualified = []

    for lid in ids:
        try:
            lg = league_obj(get_json(session, api_url(year, 'league', L=lid)))
        except AuditError:
            failures['league_fetch_failed'] += 1
            continue
        if not lg:
            failures['league_missing'] += 1
            continue

        counts['settings_read'] += 1
        qbs[str(qb_limit(lg))] += 1
        pools[str(lg.get('draftPlayerPool'))] += 1
        keepers[str(lg.get('keeperType'))] += 1

        if franchise_count(lg) == 12:
            counts['team12'] += 1
        else:
            continue
        if norm(lg.get('keeperType')) == 'dynasty':
            counts['team12_dynasty'] += 1
        else:
            continue
        if qb_limit(lg) in {'1-2', '2'}:
            counts['team12_dynasty_sf'] += 1
        else:
            continue
        if norm(lg.get('draftPlayerPool')).startswith('rook'):
            counts['team12_dynasty_sf_rookie'] += 1
        else:
            continue

        idp = is_idp(lg)
        if idp:
            counts['team12_dynasty_sf_rookie_idp'] += 1

        try:
            picks = draft_picks(get_json(session, api_url(year, 'draftResults', L=lid)))
        except AuditError:
            failures['draft_fetch_failed'] += 1
            continue

        d = depth(picks)
        if d['full4']:
            counts['full4'] += 1
            if idp:
                counts['full4_idp'] += 1
        if d['full5']:
            counts['full5'] += 1
            if idp:
                counts['full5_idp'] += 1
        if d['full6']:
            counts['full6'] += 1
            if idp:
                counts['full6_idp'] += 1

        qualified.append({
            'league_id': lid,
            'name': lg.get('name'),
            'idp': idp,
            'qb_limit': qb_limit(lg),
            'draft_player_pool': lg.get('draftPlayerPool'),
            'draft_kind': lg.get('draft_kind'),
            'depth': d,
        })

    return {
        'year': year,
        'discovery': discovery,
        'pipeline_counts': dict(counts),
        'failure_counts': dict(failures),
        'qb_limit_distribution': dict(qbs),
        'draft_pool_distribution': dict(pools),
        'keeper_type_distribution': dict(keepers),
        'qualifying_leagues': qualified,
        'heuristics': {
            'full6_primary': counts['full6'] >= MIN_FULL6_PER_YEAR,
            'full4_partial': counts['full4'] >= MIN_FULL4_PER_YEAR,
            'full6_idp': counts['full6_idp'] >= MIN_IDP_FULL6_PER_YEAR,
        },
    }

def run() -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({'User-Agent': 'LOG-Trade-Calculator-MFL-Feasibility/1.0'})
    results = []
    for year in YEARS:
        print(f'--- {year} ---', flush=True)
        r = probe_year(session, year)
        results.append(r)
        c = r['pipeline_counts']
        print(
            year,
            'probed', r['discovery']['selected_for_settings_probe'],
            'rookie-SF', c.get('team12_dynasty_sf_rookie', 0),
            'full4', c.get('full4', 0),
            'full6', c.get('full6', 0),
            'full6-IDP', c.get('full6_idp', 0),
            flush=True,
        )

    full6_years = [r['year'] for r in results if r['heuristics']['full6_primary']]
    full4_years = [r['year'] for r in results if r['heuristics']['full4_partial']]
    idp_years = [r['year'] for r in results if r['heuristics']['full6_idp']]

    if len(full6_years) == 6 and len(idp_years) == 6:
        rec = 'GO_MFL_FULL_SIX_ROUND_IDP_CAPABLE'
    elif len(full6_years) == 6:
        rec = 'GO_MFL_OFFENSE_SIX_ROUND_IDP_NEEDS_SECOND_SOURCE'
    elif len(full4_years) == 6:
        rec = 'GO_MFL_R1_R4_PRIMARY_NEEDS_DEEP_ROUND_SOURCE'
    else:
        rec = 'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT'

    return {
        'schema_version': 1,
        'audit_id': 'draft-pick-fv-v3-mfl-source-feasibility',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'pre_preregistration_source_research': True,
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'candidate_fit_performed': False,
        'candidate_scores_computed': False,
        'production_change_authorized': False,
        'years': YEARS,
        'api_endpoints_used': ['leagueSearch', 'league', 'draftResults'],
        'qualifier': {
            'teams': 12,
            'keeperType': 'dynasty',
            'qb_limit': ['1-2', '2'],
            'draftPlayerPool': 'Rookie*',
            'idp': 'reported separately from starters.idp_starters',
        },
        'discovery_design': {
            'search_terms': SEARCH_TERMS,
            'max_per_term': MAX_PER_TERM,
            'max_candidates_per_year': MAX_CANDIDATES_PER_YEAR,
            'deterministic_sampling': True,
            'limitation': (
                'MFL leagueSearch is text-search discovery, not an exhaustive census. '
                'A strong positive result can establish practical feasibility; a weak '
                'result is inconclusive rather than proof that qualifying leagues do not exist.'
            ),
        },
        'feasibility_heuristics_only': {
            'min_full6_per_year': MIN_FULL6_PER_YEAR,
            'min_full4_per_year': MIN_FULL4_PER_YEAR,
            'min_full6_idp_per_year': MIN_IDP_FULL6_PER_YEAR,
            'not_model_selection_gates': True,
        },
        'year_results': results,
        'summary': {
            'full6_years': full6_years,
            'full4_years': full4_years,
            'full6_idp_years': idp_years,
        },
        'recommendation': rec,
        'next_step': (
            'If recommendation begins GO_MFL, freeze a separate V3 preregistration '
            'before building ADP or reading outcomes. If inconclusive, expand discovery '
            'or add a second draft source; do not weaken V1/V2 gates.'
        ),
    }

def write_outputs(d: dict[str, Any]) -> None:
    JSON_OUT.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')

    lines = [
        '# Draft Pick FV V3 — MFL Source Feasibility Audit',
        '',
        f"**Recommendation:** `{d['recommendation']}`",
        '',
        'This is pre-preregistration source research. No fantasy outcomes, market/KTC values, package votes, or candidate predictions were read.',
        '',
        '## Discovery limitation',
        '',
        d['discovery_design']['limitation'],
        '',
        '## Per-season discovery',
        '',
        '| Year | Candidates probed | 12T dynasty SF rookie | Full 4 | Full 6 | Full 6 IDP |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for r in d['year_results']:
        c = r['pipeline_counts']
        lines.append(
            f"| {r['year']} | {r['discovery']['selected_for_settings_probe']} | "
            f"{c.get('team12_dynasty_sf_rookie', 0)} | {c.get('full4', 0)} | "
            f"{c.get('full6', 0)} | {c.get('full6_idp', 0)} |"
        )

    lines += [
        '',
        '## Heuristics used for source feasibility only',
        '',
        f'- Full six-round primary: >= {MIN_FULL6_PER_YEAR} qualifying leagues in each season.',
        f'- Four-round partial: >= {MIN_FULL4_PER_YEAR} qualifying leagues in each season.',
        f'- Full six-round IDP: >= {MIN_IDP_FULL6_PER_YEAR} qualifying IDP leagues in each season.',
        '',
        f"Full-6 years: **{d['summary']['full6_years']}**",
        f"Full-4 years: **{d['summary']['full4_years']}**",
        f"Full-6 IDP years: **{d['summary']['full6_idp_years']}**",
        '',
        'A Green workflow means the audit executed correctly, not that MFL passed feasibility.',
        '',
        f"**Next step:** {d['next_step']}",
    ]
    MD_OUT.write_text('\n'.join(lines) + '\n')

    manifest = {
        'schema_version': 1,
        'audit_id': d['audit_id'],
        'status': 'source_feasibility_audit_complete',
        'recommendation': d['recommendation'],
        'files': {
            str(JSON_OUT.relative_to(ROOT)): {'sha256': sha256(JSON_OUT)},
            str(MD_OUT.relative_to(ROOT)): {'sha256': sha256(MD_OUT)},
        },
        'historical_player_outcomes_read': False,
        'candidate_fit_performed': False,
        'production_change_authorized': False,
    }
    MAN_OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')

def selftest() -> None:
    league = {
        'keeperType': 'dynasty',
        'draftPlayerPool': 'Rookie',
        'franchises': {'count': '12'},
        'starters': {
            'position': [{'name': 'QB', 'limit': '1-2'}],
            'idp_starters': '6',
        },
    }
    assert qualifies_settings(league)
    assert is_idp(league)
    picks = [
        {'round': str(r), 'player': f'{r}-{n}'}
        for r in range(1, 7)
        for n in range(12)
    ]
    assert depth(picks)['full6']
    assert search_ids({'leagues': {'league': {'id': '123'}}}) == ['123']
    print('PASS: V3 MFL source auditor self-test')

def check() -> None:
    d = json.loads(JSON_OUT.read_text())
    m = json.loads(MAN_OUT.read_text())
    assert d['historical_player_outcomes_read'] is False
    assert d['market_or_ktc_data_read'] is False
    assert d['package_vote_data_read'] is False
    assert d['candidate_fit_performed'] is False
    assert d['candidate_scores_computed'] is False
    assert d['production_change_authorized'] is False
    assert d['years'] == YEARS
    assert len(d['year_results']) == 6
    assert d['recommendation'] in {
        'GO_MFL_FULL_SIX_ROUND_IDP_CAPABLE',
        'GO_MFL_OFFENSE_SIX_ROUND_IDP_NEEDS_SECOND_SOURCE',
        'GO_MFL_R1_R4_PRIMARY_NEEDS_DEEP_ROUND_SOURCE',
        'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT',
    }
    for rel, rec in m['files'].items():
        assert sha256(ROOT / rel) == rec['sha256']
    print('PASS:', d['recommendation'])

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if args.check:
        check()
        return
    d = run()
    write_outputs(d)
    print(json.dumps({
        'recommendation': d['recommendation'],
        'summary': d['summary'],
        'years': [
            {
                'year': r['year'],
                'probed': r['discovery']['selected_for_settings_probe'],
                'rookie_sf': r['pipeline_counts'].get('team12_dynasty_sf_rookie', 0),
                'full4': r['pipeline_counts'].get('full4', 0),
                'full6': r['pipeline_counts'].get('full6', 0),
                'full6_idp': r['pipeline_counts'].get('full6_idp', 0),
            }
            for r in d['year_results']
        ],
    }, indent=2))

if __name__ == '__main__':
    main()
