#!/usr/bin/env python3
"""Successor-aware historical IDP release-integrity audit.

This validates frozen V1/CAL02/CAL15/CAL22 evidence and the current
canonical value population without requiring later approved production
multipliers to equal a prior release's deployed-table SHA.

For frozen IDP V1 model-delta and exact-preservation invariants, the
adjacent repo_regression_checks.py suite is also required by CI.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "validation"))
import snapshot_values  # noqa: E402


def doc(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(value: str, label: str) -> None:
    assert isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), label


def run():
    # Immutable original IDP V1 evidence, never regenerated from current sources.
    baseline = doc("model/releases/idp-v1/prod_mult_pre_v1_baseline.json")
    patch = doc("model/releases/idp-v1/idp_v1_prod_mult_patch.json")
    bridge = doc("model/releases/idp-v1/idp_v1_model_delta_transport_candidate.json")
    assert baseline["entry_count"] == len(baseline["values"]) == 823
    assert len(bridge["players"]) == 404
    assert patch["changed_entry_count"] == len(patch["entries"])
    assert len({row["key"] for row in patch["entries"]}) == len(patch["entries"])
    assert all(row["key"] in baseline["values"] for row in patch["entries"])

    # CAL02 is an immutable historical layer; its deployed SHA is NOT
    # the expected SHA for today's later CAL15/CAL22/CAL26 model.
    cal02 = doc("model/releases/cal02-dl-residual-reset-v1/release.json")
    assert cal02["release_id"] == "cal02-migrated-dl-lineage-residual-reset-v1"
    assert cal02["scope"]["old_releases_rewritten"] is False
    assert cal02["scope"]["market_method_changed"] is False
    frozen_path = ROOT / cal02["frozen_candidate_path"]
    assert frozen_path.is_file(), "Missing original CAL02 frozen candidate"
    assert sha(frozen_path) == cal02["frozen_candidate_sha256"], "CAL02 frozen candidate SHA drift"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    assert set(cal02["players"]) == set(frozen["players"])
    assert len(cal02["players"]) == 21
    for key, record in cal02["players"].items():
        f = frozen["players"][key]
        assert f["position"] == "DL", (key, "CAL02 position drift")
        assert abs(float(record["old_raw_prod_mult"]) - float(f["control"]["raw_prod_mult"])) < 1e-10, key
        assert abs(float(record["new_raw_prod_mult"]) - float(f["c0_reset"]["raw_prod_mult"])) < 1e-10, key
    for name in ("deployed_prod_mult_canonical_sha256", "legacy_prod_mult_canonical_sha256"):
        require_digest(cal02[name], name)

    # Approved later history is checked for its own immutable shape and
    # provenance, without claiming its once-live digest is the current digest.
    cal15 = doc("model/releases/cal15-idp-2026-horizon-bounded-v1/release.json")
    assert cal15["release_id"] == "cal15-idp-2026-horizon-bounded-v1"
    assert cal15["changed_players"] == len(cal15["changed_rows"]) == 175
    assert len({r["player"] for r in cal15["changed_rows"]}) == 175
    assert all(r["player"] in baseline["values"] for r in cal15["changed_rows"])
    for name in ("base_index_sha256", "candidate_index_sha256"):
        require_digest(cal15[name], name)
    assert cal15["base_index_sha256"] != cal15["candidate_index_sha256"]

    cal22 = doc("model/releases/cal22-legacy-048-raw-floor-continuity-v1/release.json")
    assert cal22["release_id"] == "cal22-legacy-048-raw-floor-continuity-v1"
    assert cal22["guard_key_count"] == len(set(cal22["frozen_keys"])) == 48
    assert cal22["no_current_price_changes"] is True
    assert cal22["market_value_untouched"] is True
    for name in ("base_index_sha256", "candidate_index_sha256"):
        require_digest(cal22[name], name)

    cfg = snapshot_values.load_from_html(ROOT / "index.html")
    values = snapshot_values.compute_all_values(cfg)
    assert len(values) == len(cfg["player_db"]) == 565
    assert set(cal22["frozen_keys"]) <= set(cfg["player_db"])
    assert set(cfg["prod_mult"]) == set(baseline["values"]), "PROD_MULT key population unexpectedly changed"
    print("PASS historical IDP V1 frozen original: 823 multipliers, 404 candidate IDPs")
    print("PASS CAL02 frozen SHA and 21 historical reset rows (without comparing to later live hash)")
    print("PASS CAL15 175 historical successor rows; CAL22 48 immutable no-repricing guards")
    print("PASS current canonical FV population: 565; no production mutation")


if __name__ == "__main__":
    run()
