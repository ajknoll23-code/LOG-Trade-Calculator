#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
PROXY = OUT / 'mfl_reference_expansion_v1.json'
PRIOR_FEAS = OUT / 'mfl_source_feasibility_v1.json'
JSON_OUT = OUT / 'mfl_validated_proxy_feasibility_v1.json'
MD_OUT = OUT / 'mfl_validated_proxy_feasibility_v1.md'
MAN_OUT = OUT / 'mfl_validated_proxy_feasibility_manifest_v1.json'

YEARS = list(range(2018, 2024))
SEARCH_TERMS = [
    'dynasty', 'superflex', 'super flex', '2qb', '2 qb', 'rookie',
    'idp', 'devy', 'empire', 'contract', 'salary', 'taxi',
    'fantasy', 'football', 'league',
]
BASE = 'https://api.myfantasyleague.com'
MAX_PER_TERM = 50
SLEEP = 1.02

MIN_FULL6_PER_YEAR = 20
MIN_FULL4_PER_YEAR = 25
MIN_IDP_FULL6_PER_YEAR = 5

RECOMMENDATIONS = {
    'GO_MFL_FULL_SIX_ROUND_IDP_CAPABLE',
    'GO_MFL_OFFENSE_SIX_ROUND_IDP_NEEDS_SECOND_SOURCE',
    'GO_MFL_R1_R4_PRIMARY_NEEDS_DEEP_ROUND_SOURCE',
    'DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT',
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


def is_idp(lg: dict[str, Any]) -> bool:
    starters = lg.get('starters')
    if not isinstance(starters, dict):
        return False
    x = starters.get('idp_starters')
    if isinstance(x, str):
        return bool(x.strip())
    return bool(x)


def rookie_pool(lg: dict[str, Any]) -> bool:
    return norm(lg.get('draftPlayerPool')).startswith('rook')


def qualifier(lg: dict[str, Any]) -> tuple[bool, str]:
    if franchise_count(lg) != 12:
        return False, 'not_12_team'
    if qb_limit(lg) not in {'1-2', '2'}:
        return False, 'not_superflex'
    if not rookie_pool(lg):
        return False, 'not_rookie_pool'
    ks = keeper_state(lg)
    if ks == 'dynasty':
        return True, 'explicit_dynasty'
    if ks == 'missing':
        return True, 'validated_missing_keeper_proxy'
    return False, f'observed_non_dynasty:{ks}'


def obvious_mock_name(name: Any) -> bool:
    n = norm(name)
    return any(tok in n for tok in ('mock', 'draft master', 'draftmasters'))


def draft_picks(data: dict[str, Any]) -> list[dict[str, Any]]:
    root = data.get('draftResults')
    if not isinstance(root, dict):
        return []
    out: list[dict[str, Any]] = []
    for unit in as_list(root.get('draftUnit')):
        if isinstance(unit, dict):
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


def guard_proxy() -> tuple[dict[str, Any], dict[str, Any]]:
    proxy = json.loads(PROXY.read_text())
    prior = json.loads(PRIOR_FEAS.read_text())
    c = proxy['calibration']
    assert proxy['recommendation'] == 'ACCEPT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY'
    assert proxy['draft_results_read'] is False
    assert proxy['historical_player_outcomes_read'] is False
    assert proxy['candidate_fit_performed'] is False
    assert proxy['production_change_authorized'] is False
    assert c['proxy_passes_precision_gates'] is True
    assert c['enough_historical_coverage'] is True
    assert c['prior_expansion_overlap_n'] == 0
    assert prior['discovery_design']['search_terms'] == SEARCH_TERMS
    assert prior['discovery_design']['max_per_term'] == MAX_PER_TERM
    h = prior['feasibility_heuristics_only']
    assert h['min_full6_per_year'] == MIN_FULL6_PER_YEAR
    assert h['min_full4_per_year'] == MIN_FULL4_PER_YEAR
    assert h['min_full6_idp_per_year'] == MIN_IDP_FULL6_PER_YEAR
    return proxy, prior


def discover_bounded_union(session: requests.Session, year: int) -> tuple[list[str], dict[str, Any]]:
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
    if errors:
        raise AuditError(f'{year}: leagueSearch failures would redefine discovery frame: {sorted(errors)}')
    ordered = sorted(all_ids, key=lambda x: stable_key(f'{year}|candidate|{x}'))
    return ordered, {
        'term_counts_after_cap': term_counts,
        'search_errors': {},
        'bounded_unique_union_n': len(ordered),
        'selected_for_settings_probe': len(ordered),
        'all_bounded_union_candidates_probed': True,
    }


def probe_year(year: int) -> dict[str, Any]:
    if year not in YEARS:
        raise AuditError(f'unsupported year {year}')
    guard_proxy()
    session = requests.Session()
    session.headers.update({'User-Agent': f'LOG-Trade-Calculator-MFL-Validated-Proxy-{year}/2.0'})
    ids, discovery = discover_bounded_union(session, year)
    counts = Counter()
    failures = Counter()
    qbs = Counter()
    pools = Counter()
    keepers = Counter()
    qualifier_kinds = Counter()
    qualified: list[dict[str, Any]] = []

    print(f'{year}: bounded union {len(ids)} candidates', flush=True)
    for idx, lid in enumerate(ids, start=1):
        try:
            lg = league_obj(get_json(session, api_url(year, 'league', L=lid)))
        except AuditError:
            failures['league_fetch_failed'] += 1
            if idx % 100 == 0:
                print(f'{year}: progress {idx}/{len(ids)} qualified={counts["qualified"]} full4={counts["full4"]} full6={counts["full6"]}', flush=True)
            continue
        if not lg:
            failures['league_missing'] += 1
            if idx % 100 == 0:
                print(f'{year}: progress {idx}/{len(ids)} qualified={counts["qualified"]} full4={counts["full4"]} full6={counts["full6"]}', flush=True)
            continue

        counts['settings_read'] += 1
        qbs[str(qb_limit(lg))] += 1
        pools[str(lg.get('draftPlayerPool'))] += 1
        keepers[keeper_state(lg)] += 1

        ok, qkind = qualifier(lg)
        if franchise_count(lg) == 12:
            counts['team12'] += 1
        if franchise_count(lg) == 12 and qb_limit(lg) in {'1-2', '2'}:
            counts['team12_sf'] += 1
        if franchise_count(lg) == 12 and qb_limit(lg) in {'1-2', '2'} and rookie_pool(lg):
            counts['team12_sf_rookie'] += 1

        if ok:
            counts['qualified'] += 1
            qualifier_kinds[qkind] += 1
            if qkind == 'explicit_dynasty':
                counts['qualified_explicit_dynasty'] += 1
            else:
                counts['qualified_validated_proxy'] += 1
            idp = is_idp(lg)
            if idp:
                counts['qualified_idp'] += 1
            mock_signal = obvious_mock_name(lg.get('name'))
            if mock_signal:
                counts['qualified_obvious_mock_name'] += 1
            try:
                picks = draft_picks(get_json(session, api_url(year, 'draftResults', L=lid)))
            except AuditError:
                failures['draft_fetch_failed'] += 1
                picks = []
                draft_ok = False
            else:
                draft_ok = True
            d = depth(picks)
            if draft_ok:
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
                'qualifier_kind': qkind,
                'keeper_state': keeper_state(lg),
                'idp': idp,
                'obvious_mock_name': mock_signal,
                'qb_limit': qb_limit(lg),
                'draft_player_pool': lg.get('draftPlayerPool'),
                'draft_kind': lg.get('draft_kind'),
                'draft_fetch_ok': draft_ok,
                'depth': d,
            })
        elif franchise_count(lg) == 12 and qb_limit(lg) in {'1-2', '2'} and rookie_pool(lg):
            counts['team12_sf_rookie_rejected_observed_keeper'] += 1
            qualifier_kinds[qkind] += 1

        if idx % 100 == 0:
            print(f'{year}: progress {idx}/{len(ids)} qualified={counts["qualified"]} full4={counts["full4"]} full6={counts["full6"]}', flush=True)

    result = {
        'year': year,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'worker_architecture': 'one_year_per_matrix_job',
        'discovery': discovery,
        'pipeline_counts': dict(counts),
        'failure_counts': dict(failures),
        'qb_limit_distribution': dict(qbs),
        'draft_pool_distribution': dict(pools),
        'keeper_state_distribution': dict(keepers),
        'qualifier_kind_distribution': dict(qualifier_kinds),
        'qualifying_leagues': qualified,
        'heuristics': {
            'full6_primary': counts['full6'] >= MIN_FULL6_PER_YEAR,
            'full4_partial': counts['full4'] >= MIN_FULL4_PER_YEAR,
            'full6_idp': counts['full6_idp'] >= MIN_IDP_FULL6_PER_YEAR,
        },
    }
    print(
        year, 'DONE', 'probed', len(ids), 'qualified', counts['qualified'],
        'explicit', counts['qualified_explicit_dynasty'], 'proxy', counts['qualified_validated_proxy'],
        'full4', counts['full4'], 'full6', counts['full6'], 'full6-IDP', counts['full6_idp'],
        'failures', dict(failures), flush=True,
    )
    return result


def aggregate(partial_dir: Path) -> dict[str, Any]:
    proxy, prior = guard_proxy()
    results = []
    for year in YEARS:
        p = partial_dir / f'year_{year}.json'
        if not p.exists():
            raise AuditError(f'missing year artifact: {p}')
        r = json.loads(p.read_text())
        if r.get('year') != year:
            raise AuditError(f'year artifact mismatch: {p}')
        if r['discovery']['search_errors']:
            raise AuditError(f'{year}: non-empty search errors')
        results.append(r)

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
        'schema_version': 2,
        'audit_id': 'draft-pick-fv-v3-mfl-validated-proxy-feasibility',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'execution_architecture': {
            'mode': 'checkpointed_year_matrix_then_aggregate',
            'reason': 'v1 monolithic run exceeded the 100-minute GitHub job timeout after completing 2018-2020',
            'scientific_rules_changed': False,
            'years_probed_independently': YEARS,
        },
        'research_only': True,
        'pre_preregistration_source_research': True,
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'draft_results_read_for_source_feasibility_only': True,
        'candidate_fit_performed': False,
        'candidate_scores_computed': False,
        'production_change_authorized': False,
        'years': YEARS,
        'api_endpoints_used': ['leagueSearch', 'league', 'draftResults'],
        'proxy_evidence_sha256': sha256(PROXY),
        'prior_feasibility_sha256': sha256(PRIOR_FEAS),
        'validated_proxy_evidence': {
            'recommendation': proxy['recommendation'],
            'combined_reference_n': proxy['calibration']['combined_reference_n'],
            'combined_dynasty_n': proxy['calibration']['combined_dynasty_n'],
            'combined_nondynasty_n': proxy['calibration']['combined_nondynasty_n'],
            'point_precision': proxy['calibration']['point_precision'],
            'wilson_lower_95': proxy['calibration']['wilson_lower_95'],
            'historical_proxy_candidates': proxy['calibration']['historical_proxy_candidates_inherited'],
        },
        'qualifier': {
            'teams': 12,
            'qb_limit': ['1-2', '2'],
            'draftPlayerPool': 'Rookie*',
            'keeper_rule': 'explicit keeperType=dynasty OR keeperType missing under validated 12-team SF Rookie-only proxy',
            'observed_non_dynasty_keeper_labels_rejected': True,
            'idp': 'reported separately from starters.idp_starters',
        },
        'discovery_design': {
            'search_terms': SEARCH_TERMS,
            'max_per_term': MAX_PER_TERM,
            'probe_entire_bounded_unique_union': True,
            'deterministic_ordering': True,
            'search_failures_are_fatal': True,
            'why_no_150_year_cap': (
                'The prior 150/year cap made the inherited >=20 full6 and >=25 full4 heuristics '
                'impossible in years where too few structurally eligible leagues entered the sample. '
                'This rerun changes discovery breadth, not the validated proxy or feasibility thresholds.'
            ),
            'limitation': (
                'MFL leagueSearch is text-search discovery, not an exhaustive census. This audit probes '
                'the entire unique union returned by the unchanged 15 terms after the unchanged 50-per-term cap.'
            ),
        },
        'feasibility_heuristics_only': {
            'min_full6_per_year': MIN_FULL6_PER_YEAR,
            'min_full4_per_year': MIN_FULL4_PER_YEAR,
            'min_full6_idp_per_year': MIN_IDP_FULL6_PER_YEAR,
            'inherited_unchanged_from_v1': True,
            'not_model_selection_gates': True,
        },
        'year_results': results,
        'summary': {
            'full6_years': full6_years,
            'full4_years': full4_years,
            'full6_idp_years': idp_years,
            'total_qualified': sum(r['pipeline_counts'].get('qualified', 0) for r in results),
            'total_full4': sum(r['pipeline_counts'].get('full4', 0) for r in results),
            'total_full6': sum(r['pipeline_counts'].get('full6', 0) for r in results),
            'total_full6_idp': sum(r['pipeline_counts'].get('full6_idp', 0) for r in results),
            'total_obvious_mock_name': sum(r['pipeline_counts'].get('qualified_obvious_mock_name', 0) for r in results),
            'total_league_fetch_failures': sum(r['failure_counts'].get('league_fetch_failed', 0) for r in results),
            'total_draft_fetch_failures': sum(r['failure_counts'].get('draft_fetch_failed', 0) for r in results),
        },
        'recommendation': rec,
        'next_step': (
            'If recommendation begins GO_MFL, freeze a separate V3 ADP/outcome preregistration before '
            'constructing draft-slot estimates or reading player outcomes. If inconclusive, add a second '
            'historical draft source rather than weakening the validated MFL qualifier or inherited heuristics.'
        ),
    }


def write_outputs(d: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    pe = d['validated_proxy_evidence']
    lines = [
        '# Draft Pick FV V3 — MFL Validated-Proxy Feasibility Audit', '',
        f"**Recommendation:** `{d['recommendation']}`", '',
        'This remains pre-preregistration source research. Draft results are read only to measure source depth/completeness. No player outcomes, market/KTC values, package votes, or candidate model scores are read.', '',
        '## Execution architecture', '',
        '- Each season was probed in an independent GitHub Actions matrix job and saved as an artifact.',
        '- The six season artifacts were aggregated only after all six completed.',
        '- This execution-only change was made after the monolithic job hit GitHub\'s 100-minute timeout; scientific rules are unchanged.', '',
        '## Frozen proxy evidence', '',
        f"- Reference leagues: **{pe['combined_reference_n']}**",
        f"- Explicit dynasty: **{pe['combined_dynasty_n']}**",
        f"- Non-dynasty: **{pe['combined_nondynasty_n']}**",
        f"- Precision: **{pe['point_precision']:.3f}**",
        f"- Wilson 95% lower bound: **{pe['wilson_lower_95']:.3f}**", '',
        '## Per-season feasibility', '',
        '| Year | Probed | Qualified | Explicit | Proxy | Full 4 | Full 6 | Full 6 IDP | League fetch fail | Draft fetch fail |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in d['year_results']:
        c, f = r['pipeline_counts'], r['failure_counts']
        lines.append(
            f"| {r['year']} | {r['discovery']['selected_for_settings_probe']} | {c.get('qualified',0)} | "
            f"{c.get('qualified_explicit_dynasty',0)} | {c.get('qualified_validated_proxy',0)} | "
            f"{c.get('full4',0)} | {c.get('full6',0)} | {c.get('full6_idp',0)} | "
            f"{f.get('league_fetch_failed',0)} | {f.get('draft_fetch_failed',0)} |"
        )
    lines += [
        '', '## Inherited feasibility heuristics', '',
        f'- Full six-round primary: >= {MIN_FULL6_PER_YEAR} complete qualifying drafts in every season.',
        f'- Four-round partial: >= {MIN_FULL4_PER_YEAR} complete qualifying drafts in every season.',
        f'- Full six-round IDP: >= {MIN_IDP_FULL6_PER_YEAR} complete qualifying IDP drafts in every season.', '',
        f"Full-6 years: **{d['summary']['full6_years']}**",
        f"Full-4 years: **{d['summary']['full4_years']}**",
        f"Full-6 IDP years: **{d['summary']['full6_idp_years']}**", '',
        'A green workflow means the audit executed correctly. The scientific source decision is the recommendation above.', '',
        f"**Next step:** {d['next_step']}",
    ]
    MD_OUT.write_text('\n'.join(lines) + '\n')
    manifest = {
        'schema_version': 2,
        'audit_id': d['audit_id'],
        'status': 'validated_proxy_source_feasibility_complete',
        'recommendation': d['recommendation'],
        'files': {
            str(Path(__file__).resolve().relative_to(ROOT)): {'sha256': sha256(Path(__file__).resolve())},
            str(JSON_OUT.relative_to(ROOT)): {'sha256': sha256(JSON_OUT)},
            str(MD_OUT.relative_to(ROOT)): {'sha256': sha256(MD_OUT)},
        },
        'draft_results_read_for_source_feasibility_only': True,
        'historical_player_outcomes_read': False,
        'market_or_ktc_data_read': False,
        'package_vote_data_read': False,
        'candidate_fit_performed': False,
        'production_change_authorized': False,
    }
    MAN_OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


def selftest() -> None:
    explicit = {
        'keeperType': 'dynasty', 'draftPlayerPool': 'Rookie', 'franchises': {'count': '12'},
        'starters': {'position': [{'name': 'QB', 'limit': '1-2'}], 'idp_starters': '6'},
    }
    missing = dict(explicit); missing.pop('keeperType')
    keeper = dict(explicit); keeper['keeperType'] = 'keeper'
    redraft = dict(explicit); redraft['keeperType'] = 'none'
    veteran = dict(explicit); veteran['draftPlayerPool'] = 'Both'
    assert qualifier(explicit) == (True, 'explicit_dynasty')
    assert qualifier(missing) == (True, 'validated_missing_keeper_proxy')
    assert qualifier(keeper)[0] is False
    assert qualifier(redraft)[0] is False
    assert qualifier(veteran)[0] is False
    assert is_idp(explicit)
    picks = [{'round': str(r), 'player': f'{r}-{n}'} for r in range(1, 7) for n in range(12)]
    assert depth(picks)['full6']
    assert search_ids({'leagues': {'league': {'id': '123'}}}) == ['123']
    assert obvious_mock_name('TwoQBs Rookie Mock 1')
    assert not obvious_mock_name('HomeTown Dynasty League')
    print('PASS: V3 MFL validated-proxy matrix auditor self-test')


def check() -> None:
    d = json.loads(JSON_OUT.read_text())
    m = json.loads(MAN_OUT.read_text())
    assert d['historical_player_outcomes_read'] is False
    assert d['market_or_ktc_data_read'] is False
    assert d['package_vote_data_read'] is False
    assert d['candidate_fit_performed'] is False
    assert d['candidate_scores_computed'] is False
    assert d['production_change_authorized'] is False
    assert d['draft_results_read_for_source_feasibility_only'] is True
    assert d['years'] == YEARS
    assert d['recommendation'] in RECOMMENDATIONS
    assert len(d['year_results']) == 6
    assert d['execution_architecture']['scientific_rules_changed'] is False
    assert d['discovery_design']['probe_entire_bounded_unique_union'] is True
    assert d['feasibility_heuristics_only']['inherited_unchanged_from_v1'] is True
    assert d['validated_proxy_evidence']['combined_reference_n'] >= 20
    assert d['validated_proxy_evidence']['combined_dynasty_n'] >= 15
    assert d['validated_proxy_evidence']['wilson_lower_95'] >= 0.80
    for r in d['year_results']:
        assert r['discovery']['all_bounded_union_candidates_probed'] is True
        assert r['discovery']['selected_for_settings_probe'] == r['discovery']['bounded_unique_union_n']
        assert r['discovery']['search_errors'] == {}
    for rel, rec in m['files'].items():
        assert sha256(ROOT / rel) == rec['sha256']
    print('PASS:', d['recommendation'])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--year', type=int)
    ap.add_argument('--out')
    ap.add_argument('--aggregate')
    args = ap.parse_args()
    if args.selftest:
        selftest(); return
    if args.check:
        check(); return
    if args.year is not None:
        if not args.out:
            raise SystemExit('--out required with --year')
        r = probe_year(args.year)
        Path(args.out).write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
        return
    if args.aggregate:
        d = aggregate(Path(args.aggregate))
        write_outputs(d)
        print(json.dumps({
            'recommendation': d['recommendation'],
            'summary': d['summary'],
            'years': [{
                'year': r['year'], 'probed': r['discovery']['selected_for_settings_probe'],
                'qualified': r['pipeline_counts'].get('qualified',0),
                'full4': r['pipeline_counts'].get('full4',0),
                'full6': r['pipeline_counts'].get('full6',0),
                'full6_idp': r['pipeline_counts'].get('full6_idp',0),
                'failures': r['failure_counts'],
            } for r in d['year_results']],
        }, indent=2))
        return
    raise SystemExit('choose --selftest, --check, --year, or --aggregate')


if __name__ == '__main__':
    main()
