#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math, random, statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHADOW = ROOT/"research/package-adjustment-shadow-v2/package_adjustment_shadow_v2.json"
V3 = ROOT/"research/package-adjustment-v3/package_vote_challenges_v3.json"
V4 = ROOT/"research/package-adjustment-v4/package_vote_challenges_v4.json"
VALUES = ROOT/"scripts/artifacts/generated/value_uncertainty.json"
INDEX = ROOT/"index.html"
OUTDIR = ROOT/"research/package-adjustment-production-candidate-v1"
OUTJSON = OUTDIR/"production_validation.json"
OUTMD = OUTDIR/"production_validation.md"

SEED = 20260908
N_SHAPES = 20000
MEANINGFUL_TARGET_SHARE = 0.06
MIN_MATERIAL_THIRD_PACKAGE_SHARE = 0.15
V4_MARGIN_PP = 0.05

def load(p): return json.loads(p.read_text(encoding="utf-8"))

def pct(xs,q):
    xs=sorted(float(x) for x in xs)
    if not xs: return None
    if len(xs)==1: return xs[0]
    z=(len(xs)-1)*q; lo=int(math.floor(z)); hi=int(math.ceil(z))
    if lo==hi: return xs[lo]
    w=z-lo
    return xs[lo]*(1-w)+xs[hi]*w

def players():
    rows=[]
    for name,row in (load(VALUES).get("players") or {}).items():
        try: fv=float(row.get("center_value"))
        except: continue
        if math.isfinite(fv) and fv>0:
            rows.append({"name":name,"fv":fv,"pos":row.get("pos")})
    if len(rows)<500: raise RuntimeError(f"only {len(rows)} valued players")
    return rows

def v4_support():
    shares=[]; target_shares=[]
    for c in load(V4)["challenges"]:
        vals=sorted((float(p["fv"]) for p in c["package"]), reverse=True)
        total=sum(vals); target=float(c["target_fv"])
        shares.append(vals[-1]/total); target_shares.append(vals[-1]/target)
    p05=pct(shares,.05)
    threshold=max(MIN_MATERIAL_THIRD_PACKAGE_SHARE,
                  math.floor((p05-V4_MARGIN_PP)*100)/100)
    return {
        "observed_smallest_package_share_min":min(shares),
        "observed_smallest_package_share_p05":p05,
        "observed_smallest_package_share_median":statistics.median(shares),
        "observed_smallest_package_share_max":max(shares),
        "observed_smallest_target_share_min":min(target_shares),
        "observed_smallest_target_share_median":statistics.median(target_shares),
        "production_material_third_min_package_share":threshold,
        "support_margin_percentage_points":V4_MARGIN_PP*100,
    }

def m2(shadow,target):
    refs=sorted(shadow["size2"]["reference_points"], key=lambda r:float(r["target_fv"]))
    t=float(target)
    if t<=float(refs[0]["target_fv"]): return float(refs[0]["ratio"]),"clamped_low"
    if t>=float(refs[-1]["target_fv"]): return float(refs[-1]["ratio"]),"clamped_high"
    lt=math.log(t)
    for a,b in zip(refs,refs[1:]):
        af,bf=float(a["target_fv"]),float(b["target_fv"])
        if af<=t<=bf:
            w=(lt-math.log(af))/(math.log(bf)-math.log(af))
            return float(a["ratio"])+w*(float(b["ratio"])-float(a["ratio"])),"interpolated"
    raise AssertionError("m2 interpolation miss")

def classify(shadow,support,target,package):
    t=float(target); vals=[float(v) for v in package if float(v)>0]
    if not vals: return {"supported":False,"reason":"empty"}
    if any(v>=t for v in vals): return {"supported":False,"reason":"equal_or_better_asset"}
    meaningful=[v for v in vals if v>=t*MEANINGFUL_TARGET_SHARE]
    tiny=[v for v in vals if v<t*MEANINGFUL_TARGET_SHARE]
    if len(meaningful)<=1: return {"supported":False,"reason":"effective_1for1"}
    if len(meaningful)>=4: return {"supported":False,"reason":"4plus_meaningful"}
    mult2,status=m2(shadow,t); total=sum(vals)
    if len(meaningful)==2:
        return {"supported":True,"tier":"size2","multiplier":mult2,
                "total":total,"tiny":sum(tiny),"smallest_share":min(vals)/total,
                "interp":status}
    smallest=min(vals)/total
    threshold=float(support["production_material_third_min_package_share"])
    if smallest<threshold:
        return {"supported":True,"tier":"size2_with_small_third","multiplier":mult2,
                "total":total,"tiny":sum(tiny),"smallest_share":smallest,
                "interp":status}
    return {"supported":True,"tier":"size3","multiplier":float(shadow["size3"]["multiplier"]),
            "total":total,"tiny":sum(tiny),"smallest_share":smallest,"interp":"constant"}

def adjusted(shadow,support,target,package):
    r=classify(shadow,support,target,package)
    if not r["supported"]:
        return {**r,"adjustment":0.0,"required":float(target)}
    req=float(target)*float(r["multiplier"])
    return {**r,"adjustment":req-float(target),"required":req,
            "coverage":r["total"]/req}

def verdict(a,b):
    a=float(a); b=float(b); diff=a-b
    p=abs(diff)/max(a,b,1)
    if p<.07: return "fair"
    if p<.20: return "slight_A" if diff>0 else "slight_B"
    return "strong_A" if diff>0 else "strong_B"

def rank(v):
    return {"strong_B":-2,"slight_B":-1,"fair":0,"slight_A":1,"strong_A":2}[v]

def replay(shadow,support):
    v3=[c for c in load(V3)["challenges"] if int(c["package_size"])==2]
    v4=[c for c in load(V4)["challenges"] if int(c["package_size"])==3]
    ok2=0; ok3=0; maxerr=0
    for c in v3:
        r=adjusted(shadow,support,c["target_fv"],[p["fv"] for p in c["package"]])
        ok2 += int(r["supported"] and r["tier"]=="size2")
    for c in v4:
        r=adjusted(shadow,support,c["target_fv"],[p["fv"] for p in c["package"]])
        ok3 += int(r["supported"] and r["tier"]=="size3")
        maxerr=max(maxerr,abs(float(r["multiplier"])-float(shadow["size3"]["multiplier"])))
    return {"v3_n":len(v3),"v3_preserved_pct":100*ok2/len(v3),
            "v4_n":len(v4),"v4_preserved_pct":100*ok3/len(v4),
            "v4_max_multiplier_error":maxerr}

def torture(shadow,support):
    T={}
    assert not classify(shadow,support,5000,[4000])["supported"]; T["one_for_one_null"]="PASS"
    assert not classify(shadow,support,5000,[5000,1000])["supported"]; T["equal_or_better_asset_unsupported"]="PASS"
    assert not classify(shadow,support,5000,[1600,1500,1400,1300])["supported"]; T["four_plus_meaningful_unsupported"]="PASS"

    a=adjusted(shadow,support,5000,[3000,2000])
    b=adjusted(shadow,support,5000,[3000,2000,100])
    assert a["tier"]==b["tier"]=="size2" and abs(a["multiplier"]-b["multiplier"])<1e-12
    assert b["total"]>a["total"]; T["tiny_throw_in_does_not_raise_premium"]="PASS"

    th=float(support["production_material_third_min_package_share"])
    top,second=3400.0,2600.0
    s=max(.061,th-.01); x=s*(top+second)/(1-s)
    r=adjusted(shadow,support,5000,[top,second,x])
    assert r["tier"]=="size2_with_small_third"; T["small_third_guard"]="PASS"

    r=adjusted(shadow,support,5000,[4600,3380,2250])
    assert r["tier"]=="size3"; T["v4_like_shape_gets_full_3p"]="PASS"

    pts=[2500,3500,4269.25,5000,5558.25,6078.7,7500,10000]
    ms=[m2(shadow,x)[0] for x in pts]
    assert all(y>=x-1e-12 for x,y in zip(ms,ms[1:])); T["size2_curve_monotonic"]="PASS"
    assert all(float(shadow["size3"]["multiplier"])>x for x in ms); T["size3_above_size2"]="PASS"

    for t in (3000,5000,8000):
        mm=m2(shadow,t)[0]
        assert verdict(t*mm,t*mm)=="fair"
        m3=float(shadow["size3"]["multiplier"])
        assert verdict(t*m3,t*m3)=="fair"
    T["exact_requirement_is_fair"]="PASS"

    for pkg in ([3500,2500],[4000,3200,2300],[3000,2200,700]):
        r=adjusted(shadow,support,5000,pkg)
        if r["supported"]:
            assert rank(verdict(r["required"],sum(pkg)))>=rank(verdict(5000,sum(pkg)))
    T["adjustment_never_moves_verdict_toward_package"]="PASS"

    html=INDEX.read_text(encoding="utf-8")
    assert "if(diffPct < 0.07)" in html and "else if(diffPct < 0.20)" in html
    T["live_verdict_thresholds_verified"]="PASS"
    return T

def synth(shadow,support):
    rng=random.Random(SEED); ps=players()
    targets=[p for p in ps if p["fv"]>=2500]
    rows=[]; tries=0
    while len(rows)<N_SHAPES and tries<N_SHAPES*40:
        tries+=1
        t=rng.choice(targets)
        lower=[p for p in ps if p["fv"]<t["fv"]]
        if len(lower)<8: continue
        n=rng.choices([2,3,4],[45,45,10])[0]
        pkg=rng.sample(lower,n); vals=[p["fv"] for p in pkg]
        r=adjusted(shadow,support,t["fv"],vals)
        raw=verdict(t["fv"],sum(vals))
        adj=verdict(r["required"] if r["supported"] else t["fv"],sum(vals))
        if r["supported"]:
            assert math.isfinite(r["multiplier"]) and r["multiplier"]>=1
            assert r["adjustment"]>=-1e-9
            assert rank(adj)>=rank(raw)
        rows.append({"supported":r["supported"],"tier":r.get("tier"),"reason":r.get("reason"),
                     "raw":raw,"adj":adj,"changed":raw!=adj,
                     "multiplier":r.get("multiplier")})
    if len(rows)!=N_SHAPES: raise RuntimeError(f"only {len(rows)} shapes")
    sup=[r for r in rows if r["supported"]]
    tiers=Counter(r["tier"] for r in sup)
    reasons=Counter(r["reason"] for r in rows if not r["supported"])
    matrix=Counter((r["raw"],r["adj"]) for r in sup)
    return {"seed":SEED,"shape_count":len(rows),"supported_shape_count":len(sup),
            "supported_pct":100*len(sup)/len(rows),
            "tier_counts":dict(sorted(tiers.items())),
            "unsupported_reason_counts":dict(sorted(reasons.items())),
            "verdict_changed_pct":100*sum(r["changed"] for r in sup)/max(1,len(sup)),
            "transition_matrix":{f"{a} -> {b}":n for (a,b),n in sorted(matrix.items())},
            "min_multiplier":min(float(r["multiplier"]) for r in sup),
            "max_multiplier":max(float(r["multiplier"]) for r in sup),
            "direction_invariant":True}

def build():
    shadow=load(SHADOW)
    assert shadow["status"]=="research_only_shadow"
    assert shadow["schema_version"]==2
    assert shadow["torture_tests_all_passed"] is True
    support=v4_support(); rep=replay(shadow,support); tests=torture(shadow,support); syn=synth(shadow,support)
    gates={
        "source_torture_tests":shadow["torture_tests_all_passed"] is True,
        "production_torture_tests":all(v=="PASS" for v in tests.values()),
        "v3_replay_100pct":rep["v3_preserved_pct"]==100.0,
        "v4_replay_100pct":rep["v4_preserved_pct"]==100.0,
        "v4_multiplier_exact":rep["v4_max_multiplier_error"]<1e-12,
        "20k_synthetic_shapes":syn["shape_count"]>=N_SHAPES,
        "direction_invariant":syn["direction_invariant"] is True,
        "live_verdict_thresholds":tests["live_verdict_thresholds_verified"]=="PASS",
    }
    ok=all(gates.values())
    return {
        "schema_version":1,
        "status":"controlled_launch_validation",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "consumer_changed":False,
        "fundamental_value_consumer_changed":False,
        "market_value_consumer_changed":False,
        "team_utility_consumer_changed":False,
        "trade_verdict_consumer_changed":False,
        "production_formula_enabled":False,
        "candidate":{
            "name":"package-adjustment-production-candidate-v1",
            "size2_source":"V3 ratio_plus_size_target",
            "size3_source":"V4 ratio_only",
            "size3_full_multiplier":shadow["size3"]["multiplier"],
            "material_third_min_package_share":support["production_material_third_min_package_share"],
            "small_third_policy":"third player adds full FV but retains size2 premium tier",
            "unsupported_live_shapes":["1-for-1","multi-v-multi","draft picks","4+ meaningful players",
                                       "package asset >= concentrated target FV"],
            "team_utility_remains_separate":True,
        },
        "v4_composition_support":support,
        "frozen_experiment_replay":rep,
        "torture_tests":tests,
        "synthetic_regression":syn,
        "launch_gates":{"passed":gates,"all_passed":ok},
        "recommendation":{
            "controlled_launch_recommended":ok,
            "automatic_launch_performed":False,
            "prospective_trade_count_is_not_a_prelaunch_gate":True,
            "postlaunch_monitoring_required":True,
        },
    }

def report(d):
    c=d["candidate"]; s=d["synthetic_regression"]; v=d["v4_composition_support"]; r=d["frozen_experiment_replay"]
    lines=[
        "# Package Adjustment — Production Candidate V1 Validation","",
        "**No live calculator consumer changed in this validation run.**","",
        f"- Controlled launch recommended: `{d['recommendation']['controlled_launch_recommended']}`",
        f"- Synthetic shapes: `{s['shape_count']}`",
        f"- Supported shapes: `{s['supported_shape_count']}` ({s['supported_pct']:.1f}%)",
        f"- Supported verdicts changed: `{s['verdict_changed_pct']:.1f}%`","",
        "## Candidate","",
        "- 2-player premium: frozen V3 target-sensitive curve.",
        f"- Full 3-player premium: frozen V4 `{float(c['size3_full_multiplier']):.3f}x`.",
        f"- Full 3-player premium requires smallest player >= `{100*float(c['material_third_min_package_share']):.0f}%` of package player FV.",
        "- Smaller third players still add full FV but do not escalate the premium tier.","",
        "## V4 composition support","",
        f"- smallest-piece package-share min: `{100*v['observed_smallest_package_share_min']:.1f}%`",
        f"- p05: `{100*v['observed_smallest_package_share_p05']:.1f}%`",
        f"- median: `{100*v['observed_smallest_package_share_median']:.1f}%`","",
        "## Frozen replay","",
        f"- V3 2-player preservation: `{r['v3_preserved_pct']:.1f}%`",
        f"- V4 3-player preservation: `{r['v4_preserved_pct']:.1f}%`","",
        "## Launch gates","",
    ]
    lines += [f"- {k}: `{v}`" for k,v in d["launch_gates"]["passed"].items()]
    lines += ["","## Torture tests",""]
    lines += [f"- {k}: `{v}`" for k,v in d["torture_tests"].items()]
    lines += ["","## Posture","",
              "If every launch gate is green, this candidate is eligible for a controlled live launch. "
              "Future completed trades are monitoring evidence, not a prelaunch requirement.",""]
    OUTMD.write_text("\n".join(lines),encoding="utf-8")

def selftest():
    assert verdict(100,100)=="fair"
    assert verdict(106,100)=="fair"
    assert verdict(110,100)=="slight_A"
    assert verdict(130,100)=="strong_A"
    print("Package Adjustment production validation self-test passed.")

def check():
    d=load(OUTJSON)
    assert d["status"]=="controlled_launch_validation"
    assert d["launch_gates"]["all_passed"] is True
    assert d["recommendation"]["controlled_launch_recommended"] is True
    assert d["recommendation"]["automatic_launch_performed"] is False
    assert d["production_formula_enabled"] is False
    print("Package Adjustment production validation check passed.")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--write",action="store_true")
    ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    if a.selftest: selftest(); return
    if a.check: check(); return
    if not a.write: raise SystemExit("use --selftest, --write, or --check")
    d=build(); OUTDIR.mkdir(parents=True,exist_ok=True)
    OUTJSON.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    report(d)
    print("Launch gates:",d["launch_gates"]["all_passed"])
    print("Controlled launch recommended:",d["recommendation"]["controlled_launch_recommended"])
    print("Material third share floor:",d["candidate"]["material_third_min_package_share"])

if __name__=="__main__":
    main()
