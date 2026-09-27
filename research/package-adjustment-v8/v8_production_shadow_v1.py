#!/usr/bin/env python3
import math

Q_V6=2.9897594788655337
SUPPORTED_TOPOLOGIES={"2v2","2v3","2v4","3v3","3v4","4v4"}

def score_side(values,topology):
    vals=[float(v) for v in values]
    if topology not in SUPPORTED_TOPOLOGIES: raise ValueError("unsupported topology")
    a,b=map(int,topology.split("v"))
    if len(vals) not in {a,b}: raise ValueError("side cardinality does not match topology")
    if any(v<=0 for v in vals): raise ValueError("FV must be positive")
    if topology=="2v2": return sum(vals)
    return sum(v**Q_V6 for v in vals)**(1.0/Q_V6)

def score_trade(side_a,side_b,topology):
    a,b=map(int,topology.split("v"))
    if len(side_a)!=a or len(side_b)!=b: raise ValueError("trade cardinality mismatch")
    sa=score_side(side_a,topology); sb=score_side(side_b,topology)
    return {"score_A":sa,"score_B":sb,"ratio_A_over_B":sa/sb,
            "favored":"A" if sa>sb else ("B" if sb>sa else "TIE")}

def selftest():
    for topology in sorted(SUPPORTED_TOPOLOGIES):
        a,b=map(int,topology.split("v"))
        A=[5000-250*i for i in range(a)]
        B=[4800-225*i for i in range(b)]
        r=score_trade(A,B,topology)
        assert r["score_A"]>0 and r["score_B"]>0
        for vals in (A,B):
            s=score_side(vals,topology)
            sr=score_side(list(reversed(vals)),topology)
            assert abs(s-sr)<1e-9*max(1,s)
            k=3.5
            assert abs(score_side([k*x for x in vals],topology)-k*s)<1e-8*max(1,k*s)
        if topology=="2v2":
            assert abs(score_side(A,topology)-sum(A))<1e-9
    # One-point throw-in increases score but less than raw additive increase for non-2v2.
    x=[5000,3000]
    base=score_side(x,"2v3")
    grown=score_side(x+[1],"2v3")
    assert grown>base and (grown-base)<1.0
    return {"status":"PASS","topologies":sorted(SUPPORTED_TOPOLOGIES),"q":Q_V6}
