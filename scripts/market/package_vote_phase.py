#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'research/package-adjustment-production-candidate-v1/prelaunch-vote-freeze/manifest.json'
EXPECTED_MANIFEST_SHA256 = 'bd6212e19a81ca1f04dfd5823a6246450fe07e6e8d0d3a18b21645ca5f77a99f'

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_timestamp_utc(value):
    s = str(value or '').strip()
    if not s:
        return None
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def load_and_verify_manifest():
    if not MANIFEST.exists():
        return None
    actual = sha256(MANIFEST)
    if actual != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(
            f'Pre-launch vote freeze manifest drift: {actual} != {EXPECTED_MANIFEST_SHA256}'
        )
    doc = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if doc.get('status') != 'package_adjustment_prelaunch_vote_evidence_freeze':
        raise RuntimeError('Unexpected pre-launch vote freeze manifest status')
    if doc.get('frozen') is not True:
        raise RuntimeError('Pre-launch vote freeze manifest is not frozen')
    for key, row in (doc.get('frozen_files') or {}).items():
        p = ROOT / row['snapshot_path']
        if not p.exists():
            raise RuntimeError(f'Missing frozen pre-launch snapshot: {key} {p}')
        actual_file = sha256(p)
        if actual_file != row['sha256']:
            raise RuntimeError(
                f'Frozen pre-launch snapshot drift for {key}: '
                f'{actual_file} != {row["sha256"]}'
            )
    return doc

def partition_rows(rows, version):
    doc = load_and_verify_manifest()
    if doc is None:
        return {
            'vote_phase': 'legacy_unpartitioned',
            'postlaunch_rows': list(rows),
            'prelaunch_rows_excluded': 0,
            'invalid_timestamp_rows_excluded': 0,
            'prelaunch_cutoff_utc': None,
            'prelaunch_cutoff_epoch_ms': None,
            'canonical_prelaunch_snapshot': None,
        }
    version = str(version).lower()
    if version not in {'v3', 'v4'}:
        raise ValueError(f'Unsupported package vote version: {version}')
    cutoff = parse_timestamp_utc(doc['production_launch_cutoff_utc'])
    if cutoff is None:
        raise RuntimeError('Invalid production launch cutoff timestamp')
    post = []
    pre = 0
    invalid = 0
    for row in rows:
        ts = parse_timestamp_utc(row.get('timestamp'))
        if ts is None:
            invalid += 1
            continue
        if ts <= cutoff:
            pre += 1
            continue
        post.append(row)
    evidence = doc['prelaunch_evidence'][version]
    return {
        'vote_phase': 'postlaunch_only',
        'postlaunch_rows': post,
        'prelaunch_rows_excluded': pre,
        'invalid_timestamp_rows_excluded': invalid,
        'prelaunch_cutoff_utc': doc['production_launch_cutoff_utc'],
        'prelaunch_cutoff_epoch_ms': int(doc['production_launch_cutoff_epoch_ms']),
        'canonical_prelaunch_snapshot': evidence['results_snapshot'],
    }
