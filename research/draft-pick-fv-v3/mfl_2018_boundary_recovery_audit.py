#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
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
PRIOR = OUT / 'mfl_validated_proxy_feasibility_v1.json'
JSON_OUT = OUT / 'mfl_2018_boundary_recovery_v1.json'
MD_OUT = OUT / 'mfl_2018_boundary_recovery_v1.md'
MAN_OUT = OUT / 'mfl_2018_boundary_recovery_manifest_v1.json'

YEAR = 2018
BASE = 'https://api.myfantasyleague.com'
SEARCH_TERMS = [
    'dynasty', 'superflex', 'super flex', '2qb', '2 qb', 'rookie',
    'idp', 'devy', 'empire', 'contract', 'salary', 'taxi',
    'fantasy', 'football', 'league',
]
MAX_PER_TERM = 50
MIN_FULL4 = 25
SLEEP = 1.02

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

def api_url(endpoint: str, **params: Any) -> str:
    q = {'TYPE': endpoint, 'JSON': 1}
    q.update({k: v for k, v in params.items() if v is not None})
    return f'{BASE}/{YEAR}/export?' + urlencode(q)

def request_json(session: requests.Session, url: str, attempts: int, timeout: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    history: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=timeout)
            status = r.status_code
            if status in {404, 410}:
                return None, {'kind': 'permanent_http', 'status': status, 'attempts': attempt, 'history': history + [{'attempt': attempt, 'status': status}]}
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError('non-object JSON')
            time.sleep(SLEEP)
            return data, None
        except requests.HTTPError as exc:
            status = getattr(exc.response, 'status_code', None)
            history.append({'attempt': attempt, 'kind': 'http_error', 'status': status})
            if status is not None and 400 <= status < 500 and status not in {408, 429}:
                return None, {'kind': 'permanent_http', 'status': status, 'attempts': attempt, 'history': history}
        except requests.Timeout:
            history.append({'attempt': attempt, 'kind': 'timeout'})
        except requests.RequestException as exc:
            history.append({'attempt': attempt, 'kind': type(exc).__name__})
        except ValueError:
            history.append({'attempt': attempt, 'kind': 'invalid_json'})
        if attempt < attempts:
            time.sleep(min(2 * attempt, 10))
    return None, {'kind': 'unresolved_transport', 'attempts': attempts, 'history': history}

def search_ids(data: dict[str, Any]) -> list[str]:
    leagues = data.get('leagues')
    if not isinstance(leagues, dict):
        return []
    out = []
    for row in as_list(leagues.get('league')):
        if isinstance(row, dict):
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

def keeper_state(lg: dict[str, Any]) -> str:
    if 'keeperType' not in lg or lg.get('keeperType') is None or norm(lg.get('keeperType')) == '':
        return 'missing'
    v = norm(lg.get('keeperType'))
    if v == 'dynasty': return 'dynasty'
    if v == 'keeper': return 'keeper'
    if v in {'none', 'redraft'}: return 'none'
    return f'other:{v}'

def rookie_pool(lg: dict[str, Any]) -> bool:
    return norm(lg.get('draftPlayerPool')).startswith('rook')

def qualifier(lg: dict[str, Any]) -> tuple[bool, str]:
    if franchise_count(lg) != 12: return False, 'not_12_team'
    if qb_limit(lg) not in {'1-2', '2'}: return False, 'not_superflex'
    if not rookie_pool(lg): return False, 'not_rookie_pool'
    ks = keeper_state(lg)
    if ks == 'dynasty': return True, 'explicit_dynasty'
    if ks == 'missing': return True, 'validated_missing_keeper_proxy'
    return False, f'observed_non_dynasty:{ks}'

def draft_picks(data: dict[str, Any]) -> list[dict[str, Any]]:
    root = data.get('draftResults')
    if not isinstance(root, dict):
        return []
    out = []
    for unit in as_list(root.get('draftUnit')):
        if isinstance(unit, dict):
            out.extend(x for x in as_list(unit.get('draftPick')) if isinstance(x, dict))
    return out

def full4(picks: list[dict[str, Any]]) -> bool:
    c = Counter()
    for p in picks:
        rnd = safe_int(p.get('round'))
        if rnd and str(p.get('player') or '').strip():
            c[rnd] += 1
    return all(c.get(r, 0) >= 12 for r in range(1, 5))

def prior_data() -> tuple[dict[str, Any], dict[str, Any]]:
    d = json.loads(PRIOR.read_text())
    y = next(r for r in d['year_results'] if r['year'] == YEAR)
    assert d['recommendation'] == 'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT'
    assert d['feasibility_heuristics_only']['min_full4_per_year'] == MIN_FULL4
    assert d['discovery_design']['search_terms'] == SEARCH_TERMS
    assert d['discovery_design']['max_per_term'] == MAX_PER_TERM
    assert y['pipeline_counts']['full4'] == 22
    assert y['failure_counts']['league_fetch_failed'] == 24
    return d, y

def discover(session: requests.Session, prior_y: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    term_counts = {}
    all_ids: set[str] = set()
    for term in SEARCH_TERMS:
        data, err = request_json(session, api_url('leagueSearch', SEARCH=term), attempts=6, timeout=20)
        if err or data is None:
            raise AuditError(f'leagueSearch failed for {term}: {err}')
        rows = sorted(set(search_ids(data)), key=lambda x: stable_key(f'{YEAR}|{term}|{x}'))[:MAX_PER_TERM]
        term_counts[term] = len(rows)
        all_ids.update(rows)
    ordered = sorted(all_ids, key=lambda x: stable_key(f'{YEAR}|candidate|{x}'))
    prior_qual_ids = {str(x['league_id']) for x in prior_y['qualifying_leagues']}
    frame = {
        'current_term_counts': term_counts,
        'prior_term_counts': prior_y['discovery']['term_counts_after_cap'],
        'term_counts_match_prior': term_counts == prior_y['discovery']['term_counts_after_cap'],
        'current_union_n': len(ordered),
        'prior_union_n': prior_y['discovery']['bounded_unique_union_n'],
        'union_size_matches_prior': len(ordered) == prior_y['discovery']['bounded_unique_union_n'],
        'prior_successful_qualifying_ids_n': len(prior_qual_ids),
        'prior_successful_qualifying_ids_retained_n': len(prior_qual_ids.intersection(ordered)),
        'all_prior_successful_qualifying_ids_retained': prior_qual_ids.issubset(set(ordered)),
    }
    frame['shape_matches_prior'] = bool(frame['term_counts_match_prior'] and frame['union_size_matches_prior'] and frame['all_prior_successful_qualifying_ids_retained'])
    return ordered, frame

def run() -> dict[str, Any]:
    prior, prior_y = prior_data()
    session = requests.Session()
    session.headers.update({'User-Agent': 'LOG-Trade-Calculator-MFL-2018-Boundary-Recovery/1.0'})
    ids, frame = discover(session, prior_y)

    counts = Counter()
    unresolved_league_ids: list[dict[str, Any]] = []
    permanent_unavailable_league_ids: list[dict[str, Any]] = []
    unresolved_draft_ids: list[dict[str, Any]] = []
    successful_qualifying: list[dict[str, Any]] = []

    for idx, lid in enumerate(ids, 1):
        data, err = request_json(session, api_url('league', L=lid), attempts=4, timeout=18)
        if err:
            if err['kind'] == 'permanent_http':
                permanent_unavailable_league_ids.append({'league_id': lid, 'error': err})
            else:
                unresolved_league_ids.append({'league_id': lid, 'error': err})
            continue
        lg = league_obj(data or {})
        if not lg:
            counts['league_missing'] += 1
            continue
        counts['settings_read'] += 1
        ok, qkind = qualifier(lg)
        if not ok:
            continue
        counts['qualified'] += 1
        draft, derr = request_json(session, api_url('draftResults', L=lid), attempts=4, timeout=18)
        if derr:
            unresolved_draft_ids.append({'league_id': lid, 'qualifier_kind': qkind, 'error': derr})
            continue
        is_full4 = full4(draft_picks(draft or {}))
        if is_full4:
            counts['full4'] += 1
        successful_qualifying.append({'league_id': lid, 'qualifier_kind': qkind, 'full4': is_full4})
        if idx % 100 == 0:
            print(f'pass1 {idx}/{len(ids)} full4={counts["full4"]} unresolved_league={len(unresolved_league_ids)} unresolved_draft={len(unresolved_draft_ids)}', flush=True)

    # Recovery pass: only unresolved transport IDs, with stronger retry budget.
    recovered_leagues: list[str] = []
    still_unresolved_leagues: list[dict[str, Any]] = []
    for row in unresolved_league_ids:
        lid = row['league_id']
        data, err = request_json(session, api_url('league', L=lid), attempts=8, timeout=25)
        if err:
            if err['kind'] == 'permanent_http':
                permanent_unavailable_league_ids.append({'league_id': lid, 'error': err, 'recovery_pass': True})
            else:
                still_unresolved_leagues.append({'league_id': lid, 'error': err})
            continue
        recovered_leagues.append(lid)
        lg = league_obj(data or {})
        if not lg:
            counts['league_missing'] += 1
            continue
        counts['settings_read'] += 1
        ok, qkind = qualifier(lg)
        if not ok:
            continue
        counts['qualified'] += 1
        draft, derr = request_json(session, api_url('draftResults', L=lid), attempts=8, timeout=25)
        if derr:
            unresolved_draft_ids.append({'league_id': lid, 'qualifier_kind': qkind, 'error': derr, 'from_recovered_league': True})
            continue
        is_full4 = full4(draft_picks(draft or {}))
        if is_full4:
            counts['full4'] += 1
        successful_qualifying.append({'league_id': lid, 'qualifier_kind': qkind, 'full4': is_full4, 'recovered': True})

    # Strong retry for draft-only unresolved IDs. Avoid double counting qualification/full4.
    final_unresolved_drafts: list[dict[str, Any]] = []
    already_full4 = {x['league_id'] for x in successful_qualifying if x['full4']}
    success_ids = {x['league_id'] for x in successful_qualifying}
    seen_retry = set()
    for row in unresolved_draft_ids:
        lid = row['league_id']
        if lid in seen_retry:
            continue
        seen_retry.add(lid)
        draft, derr = request_json(session, api_url('draftResults', L=lid), attempts=8, timeout=25)
        if derr:
            final_unresolved_drafts.append({'league_id': lid, 'error': derr})
            continue
        is_full4 = full4(draft_picks(draft or {}))
        if is_full4 and lid not in already_full4:
            counts['full4'] += 1
            already_full4.add(lid)
        if lid not in success_ids:
            successful_qualifying.append({'league_id': lid, 'qualifier_kind': row.get('qualifier_kind'), 'full4': is_full4, 'draft_recovered': True})
            success_ids.add(lid)

    lower = counts['full4']
    # Every unresolved league could theoretically qualify/full4; every unresolved qualified draft could be full4.
    upper = lower + len(still_unresolved_leagues) + len(final_unresolved_drafts)

    if not frame['shape_matches_prior']:
        decision = 'INCONCLUSIVE_DISCOVERY_FRAME_DRIFT'
        inherited_recommendation = 'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT'
    elif lower >= MIN_FULL4:
        decision = 'MFL_2018_FULL4_GATE_RECOVERED'
        inherited_recommendation = 'GO_MFL_R1_R4_PRIMARY_NEEDS_DEEP_ROUND_SOURCE'
    elif upper < MIN_FULL4:
        decision = 'MFL_2018_FULL4_GATE_CONFIRMED_FAILED'
        inherited_recommendation = 'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT'
    else:
        decision = 'MFL_2018_FULL4_GATE_UNRESOLVED_TRANSPORT'
        inherited_recommendation = 'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT'

    return {
        'schema_version': 1,
        'audit_id': 'draft-pick-fv-v3-mfl-2018-boundary-recovery',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'pre_preregistration_source_research': True,
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'draft_results_read_for_source_feasibility_only': True,
        'candidate_fit_performed': False,
        'candidate_scores_computed': False,
        'production_change_authorized': False,
        'prior_feasibility_sha256': sha256(PRIOR),
        'frozen_rule': {'year': YEAR, 'min_full4': MIN_FULL4, 'search_terms': SEARCH_TERMS, 'max_per_term': MAX_PER_TERM},
        'prior_boundary': {
            'full4': prior_y['pipeline_counts']['full4'],
            'qualified': prior_y['pipeline_counts']['qualified'],
            'league_fetch_failed': prior_y['failure_counts'].get('league_fetch_failed', 0),
            'draft_fetch_failed': prior_y['failure_counts'].get('draft_fetch_failed', 0),
            'bounded_union_n': prior_y['discovery']['bounded_unique_union_n'],
        },
        'discovery_frame_replication': frame,
        'recovery': {
            'pass1_unresolved_league_n': len(unresolved_league_ids),
            'recovered_league_n': len(recovered_leagues),
            'permanent_unavailable_league_n': len(permanent_unavailable_league_ids),
            'still_unresolved_league_n': len(still_unresolved_leagues),
            'still_unresolved_draft_n': len(final_unresolved_drafts),
            'permanent_unavailable_league_ids': permanent_unavailable_league_ids,
            'still_unresolved_league_ids': still_unresolved_leagues,
            'still_unresolved_draft_ids': final_unresolved_drafts,
        },
        'result': {
            'settings_read': counts['settings_read'],
            'qualified': counts['qualified'],
            'full4_lower_bound': lower,
            'full4_upper_bound': upper,
            'gate': MIN_FULL4,
            'decision': decision,
            'inherited_source_recommendation': inherited_recommendation,
        },
        'interpretation': (
            'Six-round MFL feasibility was already rejected by the completed six-season audit. '
            'This recovery audit answers only whether 2018 can clear the inherited four-round gate '
            'after explicitly resolving transport uncertainty without changing the qualifier or threshold.'
        ),
    }

def write_outputs(d: dict[str, Any]) -> None:
    JSON_OUT.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    r = d['result']; f = d['discovery_frame_replication']; rec = d['recovery']
    lines = [
        '# Draft Pick FV V3 — MFL 2018 Boundary Recovery Audit', '',
        f"**Decision:** `{r['decision']}`", '',
        f"**Inherited source recommendation:** `{r['inherited_source_recommendation']}`", '',
        'This is a transport-recovery/source-feasibility audit only. No player outcomes, KTC/market data, package votes, candidate fitting, or production changes are permitted.', '',
        '## Frozen boundary', '',
        f"- Prior 2018 full-4 count: **{d['prior_boundary']['full4']}**", 
        f"- Required full-4 count: **{r['gate']}**",
        f"- Prior unresolved league fetches: **{d['prior_boundary']['league_fetch_failed']}**", '',
        '## Discovery-frame replication', '',
        f"- Union size: **{f['current_union_n']}** (prior {f['prior_union_n']})",
        f"- Term counts match prior: **{f['term_counts_match_prior']}**",
        f"- All prior successful qualifying IDs retained: **{f['all_prior_successful_qualifying_ids_retained']}**",
        f"- Frame shape matches prior: **{f['shape_matches_prior']}**", '',
        '## Recovery result', '',
        f"- Full-4 lower bound: **{r['full4_lower_bound']}**",
        f"- Full-4 conservative upper bound: **{r['full4_upper_bound']}**",
        f"- Pass-1 unresolved league requests: **{rec['pass1_unresolved_league_n']}**",
        f"- Recovered league requests: **{rec['recovered_league_n']}**",
        f"- Permanent unavailable league requests: **{rec['permanent_unavailable_league_n']}**",
        f"- Still unresolved league requests: **{rec['still_unresolved_league_n']}**",
        f"- Still unresolved draft requests: **{rec['still_unresolved_draft_n']}**", '',
        d['interpretation'], '',
    ]
    MD_OUT.write_text('\n'.join(lines))
    manifest = {
        'schema_version': 1,
        'audit_id': d['audit_id'],
        'status': 'mfl_2018_boundary_recovery_complete',
        'decision': r['decision'],
        'inherited_source_recommendation': r['inherited_source_recommendation'],
        'files': {
            str(JSON_OUT.relative_to(ROOT)): {'sha256': sha256(JSON_OUT)},
            str(MD_OUT.relative_to(ROOT)): {'sha256': sha256(MD_OUT)},
        },
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'candidate_fit_performed': False,
        'production_change_authorized': False,
    }
    MAN_OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')

def selftest() -> None:
    lg = {'franchises': {'count': '12'}, 'draftPlayerPool': 'Rookie', 'starters': {'position': [{'name': 'QB', 'limit': '1-2'}]}}
    assert qualifier(lg) == (True, 'validated_missing_keeper_proxy')
    assert full4([{'round': str(r), 'player': f'{r}-{i}'} for r in range(1,5) for i in range(12)])
    assert not full4([{'round': str(r), 'player': f'{r}-{i}'} for r in range(1,4) for i in range(12)])
    print('PASS: 2018 boundary recovery self-test')

def check() -> None:
    d = json.loads(JSON_OUT.read_text())
    m = json.loads(MAN_OUT.read_text())
    assert d['historical_player_outcomes_read'] is False
    assert d['market_or_ktc_data_read'] is False
    assert d['package_vote_data_read'] is False
    assert d['candidate_fit_performed'] is False
    assert d['candidate_scores_computed'] is False
    assert d['production_change_authorized'] is False
    assert d['frozen_rule']['min_full4'] == 25
    assert d['prior_boundary']['full4'] == 22
    assert d['prior_boundary']['league_fetch_failed'] == 24
    assert d['result']['full4_lower_bound'] <= d['result']['full4_upper_bound']
    assert d['result']['decision'] in {
        'MFL_2018_FULL4_GATE_RECOVERED',
        'MFL_2018_FULL4_GATE_CONFIRMED_FAILED',
        'MFL_2018_FULL4_GATE_UNRESOLVED_TRANSPORT',
        'INCONCLUSIVE_DISCOVERY_FRAME_DRIFT',
    }
    for rel, info in m['files'].items():
        assert sha256(ROOT / rel) == info['sha256']
    print('PASS:', d['result']['decision'])

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        selftest(); return
    if args.check:
        check(); return
    d = run()
    write_outputs(d)
    print(json.dumps({'decision': d['result']['decision'], 'source_recommendation': d['result']['inherited_source_recommendation'], 'result': d['result'], 'frame': d['discovery_frame_replication'], 'recovery': {k:v for k,v in d['recovery'].items() if not k.endswith('_ids')}}, indent=2))

if __name__ == '__main__':
    main()
