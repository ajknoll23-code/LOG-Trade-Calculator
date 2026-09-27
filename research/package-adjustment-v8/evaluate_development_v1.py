#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

TOPOLOGIES=("2v2","2v3","2v4","3v3","3v4","4v4")
CANDIDATES=("C0_RAW_SUM","C1_TOPOLOGY_SPLIT_V6_TRANSFER")
Q_V6=2.9897594788655337
BETA_BOUNDS=(0.05,25.0)
DELTA_BOUNDS=(-0.75,0.75)
MIN_IMPROVEMENT=0.005
WITHIN_TOPOLOGY=0.002
WORST_TOPOLOGY_REGRESSION=0.010
BOOT_DRAWS=10000
BOOT_SEED=20260926
EXPECTED_VOTERS=50
EXPECTED_CHALLENGES=40
EXPECTED_BALLOTS=2000

def score(vals,topology,candidate):
    x=np.asarray(vals,dtype=float)
    if len(x)<2 or np.any(x<=0):
        raise ValueError("multi-v-multi score requires >=2 strictly positive FVs")
    if candidate=="C0_RAW_SUM":
        return float(x.sum())
    if candidate=="C1_TOPOLOGY_SPLIT_V6_TRANSFER":
        if topology=="2v2":
            return float(x.sum())
        return float(np.power(np.power(x,Q_V6).sum(),1.0/Q_V6))
    raise KeyError(candidate)

def sigmoid(z):
    z=np.clip(z,-50,50)
    return 1/(1+np.exp(-z))

def logloss(y,p):
    p=np.clip(p,1e-12,1-1e-12)
    return -(y*np.log(p)+(1-y)*np.log(1-p))

def deterministic_fold_map(challenges):
    by_top=defaultdict(lambda:defaultdict(list))
    for cid,c in challenges.items():
        by_top[c["topology"]][c["primary_contrast_band"]].append(cid)
    fmap={}
    for topo in TOPOLOGIES:
        fold_counts=[0]*5
        for band in sorted(by_top[topo]):
            ids=sorted(
                by_top[topo][band],
                key=lambda cid:hashlib.sha256(
                    f"v8|20260926|{topo}|{band}|{cid}".encode()
                ).hexdigest(),
            )
            offset=int(hashlib.sha256(f"v8|{topo}|{band}".encode()).hexdigest()[:8],16)%5
            for cid in ids:
                minimum=min(fold_counts)
                choices=[f for f,n in enumerate(fold_counts) if n==minimum]
                fold=min(choices,key=lambda x:(x-offset)%5)
                fmap[cid]=fold
                fold_counts[fold]+=1
    if len(fmap)!=EXPECTED_CHALLENGES:
        raise ValueError(f"expected {EXPECTED_CHALLENGES} fold assignments, got {len(fmap)}")
    for topo in TOPOLOGIES:
        fs={fmap[cid] for cid,c in challenges.items() if c["topology"]==topo}
        if fs!=set(range(5)):
            raise ValueError(f"{topo} does not cover all five folds: {sorted(fs)}")
    return fmap

def validate_dataset(ballots,challenges):
    if len(challenges)!=EXPECTED_CHALLENGES:
        raise ValueError("challenge count drift")
    if len(ballots)!=EXPECTED_BALLOTS:
        raise ValueError(f"expected {EXPECTED_BALLOTS} accepted ballots, got {len(ballots)}")
    pairs=set()
    voters=Counter()
    by_challenge=Counter()
    valid_ids=set(challenges)
    for b in ballots:
        voter=str(b["voter_cluster"])
        cid=str(b["challenge_id"])
        if cid not in valid_ids: raise ValueError(f"unknown challenge {cid}")
        if b["display_left"] not in {"A","B"}: raise ValueError("invalid display_left")
        if not isinstance(b["human_choice_left"],bool): raise ValueError("human_choice_left must be bool")
        pair=(voter,cid)
        if pair in pairs: raise ValueError(f"duplicate voter/challenge {pair}")
        pairs.add(pair); voters[voter]+=1; by_challenge[cid]+=1
    if len(voters)!=EXPECTED_VOTERS:
        raise ValueError(f"expected {EXPECTED_VOTERS} voters, got {len(voters)}")
    if set(voters.values())!={EXPECTED_CHALLENGES}:
        raise ValueError("every accepted voter must answer all 40 challenges")
    if set(by_challenge.values())!={EXPECTED_VOTERS}:
        raise ValueError("every challenge must have exactly 50 voters")
    return {"voters":len(voters),"ballots":len(ballots),"challenges":len(by_challenge)}

def rows_for(ballots,challenges,candidate,allowed):
    rows=[]
    for b in ballots:
        cid=str(b["challenge_id"])
        if cid not in allowed: continue
        c=challenges[cid]
        sa=score([a["fv"] for a in c["side_A"]["assets"]],c["topology"],candidate)
        sb=score([a["fv"] for a in c["side_B"]["assets"]],c["topology"],candidate)
        sl,sr=(sa,sb) if b["display_left"]=="A" else (sb,sa)
        rows.append({
            "challenge_id":cid,
            "topology":c["topology"],
            "voter":str(b["voter_cluster"]),
            "x":math.log(sl/sr),
            "y":1.0 if b["human_choice_left"] else 0.0,
        })
    return rows

def weights(rows):
    by_top=defaultdict(set); by_ch=defaultdict(list)
    for i,r in enumerate(rows):
        by_top[r["topology"]].add(r["challenge_id"])
        by_ch[r["challenge_id"]].append(i)
    w=np.zeros(len(rows),dtype=float)
    for topo in sorted(by_top):
        cids=sorted(by_top[topo])
        for cid in cids:
            ids=by_ch[cid]
            each=1.0/len(by_top)/len(cids)/len(ids)
            for i in ids:w[i]=each
    if abs(float(w.sum())-1.0)>1e-9: raise ValueError("weights do not sum to 1")
    return w

def fit_model(ballots,challenges,candidate,allowed,delta_fixed=None):
    rows=rows_for(ballots,challenges,candidate,allowed)
    w=weights(rows)
    x=np.asarray([r["x"] for r in rows],dtype=float)
    y=np.asarray([r["y"] for r in rows],dtype=float)
    def objective(v):
        beta=float(v[0])
        delta=0.0 if delta_fixed is not None else float(v[1])
        p=sigmoid(beta*x+delta)
        return float(np.sum(w*logloss(y,p)))
    starts=((1.0,0.0),(0.25,0.0),(2.0,0.0),(5.0,0.0))
    best=None
    for beta0,delta0 in starts:
        if delta_fixed is None:
            x0=np.array([beta0,delta0]); bounds=(BETA_BOUNDS,DELTA_BOUNDS)
        else:
            x0=np.array([beta0]); bounds=(BETA_BOUNDS,)
        res=minimize(objective,x0,method="L-BFGS-B",bounds=bounds,
                     options={"maxiter":1000,"ftol":1e-12,"gtol":1e-9})
        if np.isfinite(res.fun) and (best is None or res.fun<best.fun):
            best=res
    if best is None: raise RuntimeError("optimizer failed")
    beta=float(best.x[0])
    delta=0.0 if delta_fixed is not None else float(best.x[1])
    return {"beta":beta,"delta_left":delta,"training_loss":float(best.fun),
            "optimizer_success":bool(best.success),"optimizer_message":str(best.message)}

def predict(ballots,challenges,candidate,fit,allowed):
    out=[]
    for r in rows_for(ballots,challenges,candidate,allowed):
        p=float(sigmoid(fit["beta"]*r["x"]+fit["delta_left"]))
        out.append({**r,"p":p,"loss":float(logloss(r["y"],p))})
    return out

def macro_loss(preds):
    by=defaultdict(lambda:defaultdict(list))
    for r in preds:by[r["topology"]][r["challenge_id"]].append(r["loss"])
    return float(np.mean([
        np.mean([np.mean(v) for v in by[topo].values()])
        for topo in sorted(by)
    ]))

def topology_losses(preds):
    by=defaultdict(lambda:defaultdict(list))
    for r in preds:by[r["topology"]][r["challenge_id"]].append(r["loss"])
    return {topo:float(np.mean([np.mean(v) for v in by[topo].values()]))
            for topo in TOPOLOGIES if by[topo]}

def cv(ballots,challenges,fmap,candidate,delta_fixed=None,excluded=frozenset()):
    active=set(challenges)-set(excluded)
    all_oof=[]; folds=[]
    for f in range(5):
        valid={cid for cid in active if fmap[cid]==f}
        train=active-valid
        if not valid or not train: raise ValueError("empty CV split")
        fit=fit_model(ballots,challenges,candidate,train,delta_fixed)
        pred=predict(ballots,challenges,candidate,fit,valid)
        all_oof.extend(pred)
        folds.append({"fold":f,"loss":macro_loss(pred),"validation_challenges":sorted(valid)})
    return {"candidate":candidate,"primary_cv_loss":macro_loss(all_oof),
            "topology_losses":topology_losses(all_oof),"folds":folds,"oof":all_oof}

def align_diff(cand,c0):
    a={(r["voter"],r["challenge_id"]):r for r in cand["oof"]}
    b={(r["voter"],r["challenge_id"]):r for r in c0["oof"]}
    if set(a)!=set(b): raise ValueError("OOF rows are not paired")
    return [{"voter":k[0],"challenge_id":k[1],"topology":a[k]["topology"],
             "diff":a[k]["loss"]-b[k]["loss"]} for k in sorted(a)]

def crossed_bootstrap(diff_rows,challenges):
    voters=sorted({r["voter"] for r in diff_rows})
    cids=sorted({r["challenge_id"] for r in diff_rows})
    by=defaultdict(dict); topo={cid:challenges[cid]["topology"] for cid in cids}
    for r in diff_rows:by[r["challenge_id"]][r["voter"]]=r["diff"]
    rng=np.random.default_rng(BOOT_SEED)
    vals=np.empty(BOOT_DRAWS,dtype=float)
    for d in range(BOOT_DRAWS):
        vs=rng.choice(voters,size=len(voters),replace=True)
        cs=rng.choice(cids,size=len(cids),replace=True)
        vm=Counter(vs); cm=Counter(cs); top_ch=defaultdict(list)
        for cid,mult in cm.items():
            per=by[cid]
            denom=sum(vm[v] for v in per)
            if denom==0:continue
            mean=sum(vm[v]*per[v] for v in per)/denom
            top_ch[topo[cid]].extend([mean]*mult)
        vals[d]=float(np.mean([np.mean(top_ch[t]) for t in TOPOLOGIES if top_ch[t]]))
    return {"draws":BOOT_DRAWS,"seed":BOOT_SEED,"mean":float(np.mean(vals)),
            "one_sided_95_ucb":float(np.quantile(vals,0.95)),
            "p_fraction_lt_zero":float(np.mean(vals<0))}

def player_map(challenges):
    out=defaultdict(set)
    for cid,c in challenges.items():
        for side in ("side_A","side_B"):
            for p in c[side]["assets"]:out[p["key"]].add(cid)
    return {k:sorted(v) for k,v in sorted(out.items())}

def invariants():
    for topology in TOPOLOGIES:
        vals=[1000,700] if topology.startswith("2v") else [1000,700,400]
        for candidate in CANDIDATES:
            s=score(vals,topology,candidate)
            assert s>0
            assert abs(score(list(reversed(vals)),topology,candidate)-s)<1e-9
            k=3.7
            assert abs(score([k*v for v in vals],topology,candidate)-k*s)<1e-8*max(1,k*s)
    assert score([100,200],"2v2","C0_RAW_SUM")==300
    assert score([100,200],"2v2","C1_TOPOLOGY_SPLIT_V6_TRANSFER")==300
    assert score([100,200,300],"2v3","C1_TOPOLOGY_SPLIT_V6_TRANSFER") < 600
    return True

def evaluate(ballots,challenges):
    validate_dataset(ballots,challenges)
    fmap=deterministic_fold_map(challenges)
    c0=cv(ballots,challenges,fmap,"C0_RAW_SUM")
    c1=cv(ballots,challenges,fmap,"C1_TOPOLOGY_SPLIT_V6_TRANSFER")
    improvement=c0["primary_cv_loss"]-c1["primary_cv_loss"]
    fold_imp=[c0["folds"][i]["loss"]-c1["folds"][i]["loss"] for i in range(5)]
    topo_delta={t:c1["topology_losses"][t]-c0["topology_losses"][t] for t in TOPOLOGIES}
    boot=crossed_bootstrap(align_diff(c1,c0),challenges)

    c0z=cv(ballots,challenges,fmap,"C0_RAW_SUM",delta_fixed=0.0)
    c1z=cv(ballots,challenges,fmap,"C1_TOPOLOGY_SPLIT_V6_TRANSFER",delta_fixed=0.0)
    primary_rank=sorted(CANDIDATES,key=lambda c:({"C0_RAW_SUM":c0,"C1_TOPOLOGY_SPLIT_V6_TRANSFER":c1}[c]["primary_cv_loss"],c))
    zero_rank=sorted(CANDIDATES,key=lambda c:({"C0_RAW_SUM":c0z,"C1_TOPOLOGY_SPLIT_V6_TRANSFER":c1z}[c]["primary_cv_loss"],c))

    pmap=player_map(challenges)
    lopo={}
    for key,excluded in pmap.items():
        a=cv(ballots,challenges,fmap,"C0_RAW_SUM",excluded=set(excluded))
        b=cv(ballots,challenges,fmap,"C1_TOPOLOGY_SPLIT_V6_TRANSFER",excluded=set(excluded))
        lopo[key]=a["primary_cv_loss"]-b["primary_cv_loss"]

    gates={
        "combined_cv_improvement_ge_0_005":improvement>=MIN_IMPROVEMENT-1e-12,
        "folds_improved_ge_4":sum(x>0 for x in fold_imp)>=4,
        "all_6_topologies_improve_or_within_0_002":
            sum(v<=WITHIN_TOPOLOGY+1e-12 for v in topo_delta.values())==6,
        "worst_topology_regression_le_0_010":
            max(topo_delta.values())<=WORST_TOPOLOGY_REGRESSION+1e-12,
        "bootstrap_one_sided_95_ucb_lt_0":boot["one_sided_95_ucb"]<0,
        "delta_left_zero_ranking_unchanged":primary_rank==zero_rank,
        "leave_one_player_out_positive_every_player":min(lopo.values())>0,
        "mathematical_invariants_pass":invariants(),
    }
    return {
        "schema_version":1,
        "study_id":"package-adjustment-v8-topology-split-multi-v-multi",
        "candidate":"C1_TOPOLOGY_SPLIT_V6_TRANSFER",
        "c0_cv_loss":c0["primary_cv_loss"],
        "candidate_cv_loss":c1["primary_cv_loss"],
        "improvement_vs_c0":improvement,
        "fold_improvements":fold_imp,
        "folds_improved":sum(x>0 for x in fold_imp),
        "topology_candidate_minus_c0":topo_delta,
        "worst_topology_regression":max(topo_delta.values()),
        "bootstrap":boot,
        "delta_left_zero_sensitivity":{"primary_rank":primary_rank,"delta_zero_rank":zero_rank,
                                       "ranking_unchanged":primary_rank==zero_rank},
        "leave_one_player_out":{"players":len(lopo),"minimum_improvement_vs_c0":min(lopo.values()),
                                "all_positive":min(lopo.values())>0,"by_player":lopo},
        "gates":gates,
        "decision":"PASS_DEVELOPMENT_BUILD_FRESH_CONFIRMATION_POWER"
            if all(gates.values()) else "STOP_V8_TOPOLOGY_SPLIT_NO_DEVELOPMENT_CONFIRMATION",
        "confirmation_catalog_generated":False,
        "production_change_authorized":False,
    }

def load_catalog(path):
    doc=json.loads(Path(path).read_text())
    return {str(c["id"]):c for c in doc["challenges"]}

def selftest(catalog_path):
    challenges=load_catalog(catalog_path)
    fmap=deterministic_fold_map(challenges)
    assert len(fmap)==40
    assert set(fmap.values())==set(range(5))
    assert invariants()
    # Dataset validation fixture with exactly 50x40, independent of outcomes.
    ballots=[]
    for v in range(50):
        for i,cid in enumerate(sorted(challenges)):
            ballots.append({"voter_cluster":f"synthetic_{v:02d}","challenge_id":cid,
                            "display_left":"A" if (v+i)%2==0 else "B",
                            "human_choice_left":bool((v*7+i*11)%2)})
    summary=validate_dataset(ballots,challenges)
    assert summary=={"voters":50,"ballots":2000,"challenges":40}
    c0=cv(ballots,challenges,fmap,"C0_RAW_SUM")
    c1=cv(ballots,challenges,fmap,"C1_TOPOLOGY_SPLIT_V6_TRANSFER")
    assert math.isfinite(c0["primary_cv_loss"])
    assert math.isfinite(c1["primary_cv_loss"])
    assert len(c0["folds"])==len(c1["folds"])==5
    return {"status":"PASS","fold_map":dict(sorted(fmap.items())),
            "synthetic_dataset_validation":summary,"math_invariants":True,
            "synthetic_cv_smoke":{"c0_loss":c0["primary_cv_loss"],
                                  "c1_loss":c1["primary_cv_loss"],
                                  "folds_each":5}}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",required=True)
    ap.add_argument("--data")
    ap.add_argument("--output")
    ap.add_argument("--selftest",action="store_true")
    args=ap.parse_args()
    if args.selftest:
        print(json.dumps(selftest(args.catalog),indent=2,sort_keys=True));return
    if not args.data or not args.output: raise SystemExit("--data and --output required outside --selftest")
    challenges=load_catalog(args.catalog)
    data=json.loads(Path(args.data).read_text())
    ballots=data["ballots"]
    result=evaluate(ballots,challenges)
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"decision":result["decision"],"gates":result["gates"]},indent=2))
if __name__=="__main__":main()
