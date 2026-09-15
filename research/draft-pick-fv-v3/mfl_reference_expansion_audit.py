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
PRIOR = OUT / 'mfl_schema_qualification_v1.json'
JSON_OUT = OUT / 'mfl_reference_expansion_v1.json'
MD_OUT = OUT / 'mfl_reference_expansion_v1.md'
MAN_OUT = OUT / 'mfl_reference_expansion_manifest_v1.json'

REFERENCE_YEARS = [2020, 2021, 2022, 2023]
SEARCH_TERMS = [
    'dynasty', 'superflex', 'super flex', '2qb', '2 qb', 'rookie',
    'idp', 'devy', 'empire', 'contract', 'salary', 'taxi',
    'fantasy', 'football', 'league',
]
BASE = 'https://api.myfantasyleague.com'
MAX_PER_TERM = 50
PRIOR_CANDIDATES_PER_YEAR = 150
EXPANSION_CANDIDATES_PER_YEAR = 300
SLEEP = 1.02

# These gates are inherited unchanged from the completed schema-qualification audit.
MIN_REFERENCE_ROOKIE_N = 20
MIN_REFERENCE_DYNASTY_N = 15
MIN_POINT_PRECISION = 0.90
MIN_WILSON_LOWER_95 = 0.80
MIN_HISTORICAL_PROXY_CANDIDATES_PER_YEAR = 8

DECISIONS = {
    'ACCEPT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY',
    'REJECT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY',
    'INCONCLUSIVE_REFERENCE_SAMPLE',
    'PROXY_VALIDATED_BUT_HISTORICAL_COVERAGE_THIN',
}


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
    out: list[str] = []
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


def is_sf(lg: dict[str, Any]) -> bool:
    return qb_limit(lg) in {'1-2', '2'}


def rookie_pool(lg: dict[str, Any]) -> bool:
    return norm(lg.get('draftPlayerPool')).startswith('rook')


def keeper_state(lg: dict[str, Any]) -> str:
    if 'keeperType' not in lg or lg.get('keeperType') is None or norm(lg.get('keeperType')) == '':
        return 'missing'
    v = norm(lg.get('keeperType'))
    if v == 'dynasty':
        return 'dynasty'
    if v == 'keeper':
        return 'keeper'
    if v in {'none', 'redraft'}:
        return 'none'
    return f'other:{v}'


def wilson_lower(successes: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    phat = successes / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (center - margin) / denom


def prior_year(prior: dict[str, Any], year: int) -> dict[str, Any]:
    for r in prior['year_results']:
        if r['year'] == year:
            return r
    raise AuditError(f'prior result missing year {year}')


def discover_expansion(
    session: requests.Session,
    prior: dict[str, Any],
    year: int,
) -> tuple[list[str], dict[str, Any]]:
    term_counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    all_ids: set[str] = set()

    for term in SEARCH_TERMS:
        try:
            rows = search_ids(get_json(session, api_url(year, 'leagueSearch', SEARCH=term)))
        except AuditError as exc:
            rows = []
            errors[term] = str(exc)
        rows = sorted(set(rows), key=lambda x: stable_key(f'{year}|{term}|{x}'))[:MAX_PER_TERM]
        term_counts[term] = len(rows)
        all_ids.update(rows)

    # MFL leagueSearch is a live discovery index. Its raw result counts can
    # legitimately drift between runs even for historical seasons. The prior
    # audit did not persist all 150 sampled IDs, so exact reconstruction of
    # yesterday's discovery universe is impossible once that live index moves.
    # Treat that drift as metadata, not corruption. Keep the frozen search
    # terms/caps/hash ordering, start after the current deterministic first 150,
    # and explicitly exclude every prior 12T-SF ID that *was* persisted.
    ordered = sorted(all_ids, key=lambda x: stable_key(f'{year}|candidate|{x}'))
    current_head = ordered[:PRIOR_CANDIDATES_PER_YEAR]

    p = prior_year(prior, year)
    pd = p['discovery']
    known_prior_sf = {str(x['league_id']) for x in p['team12_sf_rows']}

    candidate_tail = ordered[PRIOR_CANDIDATES_PER_YEAR:]
    expansion_pool = [lid for lid in candidate_tail if lid not in known_prior_sf]
    expansion_selected = expansion_pool[:EXPANSION_CANDIDATES_PER_YEAR]

    term_count_drift = {
        term: {
            'prior': int(pd['term_counts_after_cap'].get(term, 0)),
            'current': int(term_counts.get(term, 0)),
        }
        for term in SEARCH_TERMS
        if int(pd['term_counts_after_cap'].get(term, 0)) != int(term_counts.get(term, 0))
    }
    prior_sf_in_current_union = known_prior_sf & set(ordered)
    prior_sf_in_current_head = known_prior_sf & set(current_head)
    prior_sf_in_current_tail = known_prior_sf & set(candidate_tail)

    if set(expansion_selected) & known_prior_sf:
        raise AuditError(f'{year}: prior 12T-SF exclusion failed')

    return expansion_selected, {
        'term_counts_after_cap': term_counts,
        'search_errors': errors,
        'current_unique_union': len(ordered),
        'prior_unique_union': int(pd['unique_union_before_year_cap']),
        'union_size_drift': len(ordered) - int(pd['unique_union_before_year_cap']),
        'term_count_drift': term_count_drift,
        'live_search_drift_observed': bool(term_count_drift) or len(ordered) != int(pd['unique_union_before_year_cap']),
        'current_head_n': len(current_head),
        'prior_12t_sf_ids_known_n': len(known_prior_sf),
        'prior_12t_sf_ids_in_current_union_n': len(prior_sf_in_current_union),
        'prior_12t_sf_ids_in_current_head_n': len(prior_sf_in_current_head),
        'prior_12t_sf_ids_excluded_from_tail_n': len(prior_sf_in_current_tail),
        'expansion_pool_available_n': len(expansion_pool),
        'selected_for_expansion_probe': len(expansion_selected),
        'expansion_slice_start_zero_based': PRIOR_CANDIDATES_PER_YEAR,
        'prior_persisted_12t_sf_ids_explicitly_excluded': True,
        'sampling_contract': (
            'Use the unchanged MFL search terms/caps and SHA256-stable ordering on the live discovery snapshot; '
            'skip the current first 150 IDs, exclude all persisted prior 12T-SF IDs, and probe up to the next 300 IDs.'
        ),
    }


def probe_year(session: requests.Session, prior: dict[str, Any], year: int) -> dict[str, Any]:
    ids, discovery = discover_expansion(session, prior, year)
    failures = Counter()
    counts = Counter()
    reference_rows: list[dict[str, Any]] = []

    for idx, lid in enumerate(ids, start=1):
        try:
            lg = league_obj(get_json(session, api_url(year, 'league', L=lid)))
        except AuditError:
            failures['league_fetch_failed'] += 1
            continue
        if not lg:
            failures['league_missing'] += 1
            continue

        counts['settings_read'] += 1
        if franchise_count(lg) != 12:
            continue
        counts['team12'] += 1
        if not is_sf(lg):
            continue
        counts['team12_sf'] += 1
        if not rookie_pool(lg):
            continue
        counts['team12_sf_rookie'] += 1

        kstate = keeper_state(lg)
        if kstate == 'missing':
            counts['team12_sf_rookie_keeper_missing'] += 1
        elif kstate.startswith('other:'):
            counts['team12_sf_rookie_keeper_other'] += 1
        else:
            counts['team12_sf_rookie_keeper_observed'] += 1
            if kstate == 'dynasty':
                counts['team12_sf_rookie_reference_dynasty'] += 1
            else:
                counts['team12_sf_rookie_reference_nondynasty'] += 1
            reference_rows.append({
                'year': year,
                'league_id': lid,
                'keeper_state': kstate,
                'draft_player_pool': lg.get('draftPlayerPool'),
                'qb_limit': qb_limit(lg),
            })

        if idx % 50 == 0:
            print(
                year,
                'progress', idx, '/', len(ids),
                'observed-reference', len(reference_rows),
                flush=True,
            )

    return {
        'year': year,
        'discovery': discovery,
        'failure_counts': dict(failures),
        'pipeline_counts': dict(counts),
        'reference_rows': reference_rows,
    }


def extract_prior_reference(prior: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in prior['year_results']:
        if r['year'] not in REFERENCE_YEARS:
            continue
        for x in r['team12_sf_rows']:
            if not x['rookie_pool']:
                continue
            ks = x['keeper_state']
            if ks == 'missing' or ks.startswith('other:'):
                continue
            rows.append({
                'year': r['year'],
                'league_id': str(x['league_id']),
                'keeper_state': ks,
                'source': 'prior_150_per_year',
            })
    return rows


def calibrate(prior: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    prior_rows = extract_prior_reference(prior)
    expansion_rows = [
        {**x, 'league_id': str(x['league_id']), 'source': 'supplemental_live_snapshot_up_to_300_per_year'}
        for r in results
        for x in r['reference_rows']
    ]

    combined_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for row in prior_rows + expansion_rows:
        key = (int(row['year']), str(row['league_id']))
        if key in combined_by_key and combined_by_key[key]['keeper_state'] != row['keeper_state']:
            raise AuditError(f'conflicting keeper state for {key}')
        combined_by_key[key] = row
    combined = list(combined_by_key.values())

    prior_keys = {(x['year'], x['league_id']) for x in prior_rows}
    expansion_keys = {(x['year'], x['league_id']) for x in expansion_rows}
    overlap_n = len(prior_keys & expansion_keys)
    if overlap_n != 0:
        raise AuditError(f'expansion overlapped prior labeled reference rows: {overlap_n}')

    successes = sum(1 for x in combined if x['keeper_state'] == 'dynasty')
    n = len(combined)
    precision = successes / n if n else None
    lower = wilson_lower(successes, n)
    nondynasty = Counter(x['keeper_state'] for x in combined if x['keeper_state'] != 'dynasty')

    inherited_hist = prior['calibration']['historical_missing_keeper_rookie_proxy_candidates']
    enough_historical = all(
        inherited_hist[str(y)] >= MIN_HISTORICAL_PROXY_CANDIDATES_PER_YEAR
        for y in [2018, 2019]
    )
    enough_reference = n >= MIN_REFERENCE_ROOKIE_N and successes >= MIN_REFERENCE_DYNASTY_N
    proxy_passes = (
        enough_reference
        and precision is not None and precision >= MIN_POINT_PRECISION
        and lower is not None and lower >= MIN_WILSON_LOWER_95
    )

    if not enough_reference:
        decision = 'INCONCLUSIVE_REFERENCE_SAMPLE'
    elif not proxy_passes:
        decision = 'REJECT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY'
    elif not enough_historical:
        decision = 'PROXY_VALIDATED_BUT_HISTORICAL_COVERAGE_THIN'
    else:
        decision = 'ACCEPT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY'

    return {
        'prior_reference_n': len(prior_rows),
        'expansion_reference_n': len(expansion_rows),
        'combined_reference_n': n,
        'combined_dynasty_n': successes,
        'combined_nondynasty_n': n - successes,
        'combined_nondynasty_states': dict(nondynasty),
        'point_precision': precision,
        'wilson_lower_95': lower,
        'prior_expansion_overlap_n': overlap_n,
        'historical_proxy_candidates_inherited': inherited_hist,
        'gates': {
            'min_reference_rookie_n': MIN_REFERENCE_ROOKIE_N,
            'min_reference_dynasty_n': MIN_REFERENCE_DYNASTY_N,
            'min_point_precision': MIN_POINT_PRECISION,
            'min_wilson_lower_95': MIN_WILSON_LOWER_95,
            'min_historical_proxy_candidates_per_year': MIN_HISTORICAL_PROXY_CANDIDATES_PER_YEAR,
        },
        'enough_reference': enough_reference,
        'proxy_passes_precision_gates': proxy_passes,
        'enough_historical_coverage': enough_historical,
        'decision': decision,
    }


def validate_prior(prior: dict[str, Any]) -> None:
    assert prior['recommendation'] == 'INCONCLUSIVE_REFERENCE_SAMPLE'
    assert prior['decision_rule_frozen_before_execution'] is True
    assert prior['historical_player_outcomes_read'] is False
    assert prior['market_or_ktc_data_read'] is False
    assert prior['package_vote_data_read'] is False
    assert prior['draft_results_read'] is False
    assert prior['candidate_fit_performed'] is False
    assert prior['candidate_scores_computed'] is False
    assert prior['production_change_authorized'] is False
    assert prior['reference_years'] == REFERENCE_YEARS
    assert prior['discovery_design']['search_terms'] == SEARCH_TERMS
    assert prior['discovery_design']['max_per_term'] == MAX_PER_TERM
    assert prior['discovery_design']['max_candidates_per_year'] == PRIOR_CANDIDATES_PER_YEAR

    c = prior['calibration']
    assert c['gates'] == {
        'min_historical_proxy_candidates_per_year': MIN_HISTORICAL_PROXY_CANDIDATES_PER_YEAR,
        'min_point_precision': MIN_POINT_PRECISION,
        'min_reference_dynasty_n': MIN_REFERENCE_DYNASTY_N,
        'min_reference_rookie_n': MIN_REFERENCE_ROOKIE_N,
        'min_wilson_lower_95': MIN_WILSON_LOWER_95,
    }
    assert c['enough_historical_coverage'] is True
    assert c['reference_rookie_n'] == 9
    assert c['reference_dynasty_n'] == 9


def run() -> dict[str, Any]:
    prior = json.loads(PRIOR.read_text())
    validate_prior(prior)

    session = requests.Session()
    session.headers.update({'User-Agent': 'LOG-Trade-Calculator-MFL-Reference-Expansion/1.0'})

    results = []
    for year in REFERENCE_YEARS:
        print(f'--- {year} reference expansion ---', flush=True)
        r = probe_year(session, prior, year)
        results.append(r)
        c = r['pipeline_counts']
        print(
            year,
            'expansion-probed', r['discovery']['selected_for_expansion_probe'],
            '12T-SF-rookie', c.get('team12_sf_rookie', 0),
            'observed-reference', c.get('team12_sf_rookie_keeper_observed', 0),
            'dynasty', c.get('team12_sf_rookie_reference_dynasty', 0),
            'nondynasty', c.get('team12_sf_rookie_reference_nondynasty', 0),
            flush=True,
        )

    cal = calibrate(prior, results)
    return {
        'schema_version': 1,
        'audit_id': 'draft-pick-fv-v3-mfl-reference-expansion',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'pre_preregistration_source_research': True,
        'decision_rule_inherited_unchanged': True,
        'expansion_design_frozen_before_execution': True,
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'draft_results_read': False,
        'candidate_fit_performed': False,
        'candidate_scores_computed': False,
        'production_change_authorized': False,
        'reference_years': REFERENCE_YEARS,
        'api_endpoints_used': ['leagueSearch', 'league'],
        'prior_schema_qualification_sha256': sha256(PRIOR),
        'expansion_design': {
            'search_terms': SEARCH_TERMS,
            'max_per_term': MAX_PER_TERM,
            'prior_candidates_per_year': PRIOR_CANDIDATES_PER_YEAR,
            'expansion_candidates_per_year': EXPANSION_CANDIDATES_PER_YEAR,
            'sampling_contract': (
                'Use unchanged search terms/caps and SHA256-stable ordering on the live MFL discovery snapshot; '
                'skip the current first 150, exclude persisted prior 12T-SF IDs, and probe up to 300 additional IDs/year.'
            ),
            'no_targeted_dynasty_enrichment': True,
            'no_gate_changes': True,
        },
        'year_results': results,
        'calibration': cal,
        'recommendation': cal['decision'],
        'next_step': (
            'If ACCEPT: rerun MFL draft-source feasibility using the now-validated fallback '
            'qualifier explicit keeperType=dynasty OR keeperType missing + Rookie-only draft. '
            'If REJECT: do not weaken the dynasty qualifier; add a second draft source. '
            'If still INCONCLUSIVE: expand metadata-only evidence again or add an independent '
            'metadata source before any draft-result or player-outcome modeling.'
        ),
    }


def write_outputs(d: dict[str, Any]) -> None:
    JSON_OUT.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    c = d['calibration']
    precision = 'n/a' if c['point_precision'] is None else f"{c['point_precision']:.3f}"
    lower = 'n/a' if c['wilson_lower_95'] is None else f"{c['wilson_lower_95']:.3f}"

    lines = [
        '# Draft Pick FV V3 — MFL Reference Expansion Audit',
        '',
        f"**Recommendation:** `{d['recommendation']}`",
        '',
        'This audit reads MFL league metadata only. It does **not** read draft results, player outcomes, KTC/market data, package votes, or candidate model scores.',
        '',
        '## Frozen expansion design',
        '',
        '- Reference years: **2020–2023**',
        f'- Original deterministic sample: **{PRIOR_CANDIDATES_PER_YEAR} candidates/year**',
        f'- Expansion: **up to {EXPANSION_CANDIDATES_PER_YEAR} additional candidates/year** from the live discovery snapshot after the current first {PRIOR_CANDIDATES_PER_YEAR}, with persisted prior 12T-SF IDs excluded',
        '- Search terms, per-term cap, proxy definition, and scientific gates are unchanged.',
        '- Live MFL search-index drift is recorded diagnostically rather than treated as a fatal error.',
        '- No dynasty-targeted enrichment is used.',
        '',
        '## Combined proxy evidence',
        '',
        f"- Prior labeled reference rows: **{c['prior_reference_n']}**",
        f"- New labeled reference rows: **{c['expansion_reference_n']}**",
        f"- Combined labeled reference rows: **{c['combined_reference_n']}** (gate >= {MIN_REFERENCE_ROOKIE_N})",
        f"- Explicit dynasty among combined rows: **{c['combined_dynasty_n']}** (gate >= {MIN_REFERENCE_DYNASTY_N})",
        f"- Point precision: **{precision}** (gate >= {MIN_POINT_PRECISION:.2f})",
        f"- Wilson 95% lower bound: **{lower}** (gate >= {MIN_WILSON_LOWER_95:.2f})",
        '',
        '## Expansion by year',
        '',
        '| Year | Expansion probed | 12T SF Rookie | Labeled reference | Dynasty | Non-dynasty |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for r in d['year_results']:
        pc = r['pipeline_counts']
        lines.append(
            f"| {r['year']} | {r['discovery']['selected_for_expansion_probe']} | "
            f"{pc.get('team12_sf_rookie', 0)} | {pc.get('team12_sf_rookie_keeper_observed', 0)} | "
            f"{pc.get('team12_sf_rookie_reference_dynasty', 0)} | "
            f"{pc.get('team12_sf_rookie_reference_nondynasty', 0)} |"
        )

    lines += [
        '',
        '## Interpretation guard',
        '',
        'A green workflow means the expansion audit executed correctly. The scientific source decision is the recommendation above.',
        '',
        f"**Next step:** {d['next_step']}",
    ]
    MD_OUT.write_text('\n'.join(lines) + '\n')

    manifest = {
        'schema_version': 1,
        'audit_id': d['audit_id'],
        'status': 'mfl_reference_expansion_complete',
        'recommendation': d['recommendation'],
        'files': {
            str(JSON_OUT.relative_to(ROOT)): {'sha256': sha256(JSON_OUT)},
            str(MD_OUT.relative_to(ROOT)): {'sha256': sha256(MD_OUT)},
        },
        'draft_results_read': False,
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
        'starters': {'position': [{'name': 'QB', 'limit': '1-2'}]},
    }
    assert franchise_count(league) == 12
    assert is_sf(league)
    assert rookie_pool(league)
    assert keeper_state(league) == 'dynasty'
    assert wilson_lower(20, 20) is not None and wilson_lower(20, 20) > 0.80
    assert wilson_lower(9, 9) is not None and wilson_lower(9, 9) < 0.80
    print('PASS: V3 MFL reference expansion self-test')


def check() -> None:
    d = json.loads(JSON_OUT.read_text())
    m = json.loads(MAN_OUT.read_text())
    assert d['historical_player_outcomes_read'] is False
    assert d['market_or_ktc_data_read'] is False
    assert d['package_vote_data_read'] is False
    assert d['draft_results_read'] is False
    assert d['candidate_fit_performed'] is False
    assert d['candidate_scores_computed'] is False
    assert d['production_change_authorized'] is False
    assert d['decision_rule_inherited_unchanged'] is True
    assert d['expansion_design_frozen_before_execution'] is True
    assert d['api_endpoints_used'] == ['leagueSearch', 'league']
    assert d['expansion_design']['expansion_candidates_per_year'] == 300
    assert d['recommendation'] in DECISIONS
    assert len(d['year_results']) == 4
    assert d['calibration']['prior_expansion_overlap_n'] == 0
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
    c = d['calibration']
    print(json.dumps({
        'recommendation': d['recommendation'],
        'prior_reference_n': c['prior_reference_n'],
        'expansion_reference_n': c['expansion_reference_n'],
        'combined_reference_n': c['combined_reference_n'],
        'combined_dynasty_n': c['combined_dynasty_n'],
        'point_precision': c['point_precision'],
        'wilson_lower_95': c['wilson_lower_95'],
    }, indent=2))


if __name__ == '__main__':
    main()
