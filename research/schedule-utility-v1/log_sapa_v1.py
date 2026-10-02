#!/usr/bin/env python3
"""LOG-SAPA V1: frozen Schedule Utility V1 predictor construction.

This is NOT 4for4 aFPA. Phase 1D uses synthetic data only.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
import math, statistics
from typing import Mapping, Sequence, Iterable

METRIC_ID = "LOG-SAPA-V1"
LOOKBACK_WEEKS = 10
MIN_OPPONENT_COMPARISON_GAMES = 2
MIN_DEFENSE_ADJUSTED_GAMES = 3
SUPPORTED_SCORING = {"HALF_PPR": 0.5, "PPR": 1.0}
POS_ALIAS = {"QB":"QB","RB":"RB","FB":"RB","HB":"RB","WR":"WR","TE":"TE"}
STAT_FIELDS = (
    "passing_yards","passing_tds","passing_interceptions",
    "rushing_yards","rushing_tds","receiving_yards","receiving_tds","receptions",
    "passing_2pt_conversions","rushing_2pt_conversions","receiving_2pt_conversions",
    "sack_fumbles_lost","rushing_fumbles_lost","receiving_fumbles_lost",
)

def num(v):
    if v is None or v == "": return 0.0
    x=float(v)
    if not math.isfinite(x): raise ValueError("non-finite")
    return x

def canonical_position(v):
    if v is None: return None
    return POS_ALIAS.get(str(v).strip().upper())

def score_player_row(row: Mapping[str, object], scoring_mode: str) -> float:
    if scoring_mode not in SUPPORTED_SCORING: raise ValueError("unsupported scoring")
    missing=[k for k in STAT_FIELDS if k not in row]
    if missing: raise KeyError(f"missing fields: {missing}")
    r=SUPPORTED_SCORING[scoring_mode]
    return (
        .04*num(row["passing_yards"]) + 4*num(row["passing_tds"])
        -2*num(row["passing_interceptions"])
        +.1*(num(row["rushing_yards"])+num(row["receiving_yards"]))
        +6*(num(row["rushing_tds"])+num(row["receiving_tds"]))
        +r*num(row["receptions"])
        +2*(num(row["passing_2pt_conversions"])+num(row["rushing_2pt_conversions"])+num(row["receiving_2pt_conversions"]))
        -2*(num(row["sack_fumbles_lost"])+num(row["rushing_fumbles_lost"])+num(row["receiving_fumbles_lost"]))
    )

@dataclass(frozen=True)
class GamePositionPoints:
    season:int; week:int; offense_team:str; defense_team:str
    position:str; scoring_mode:str; points:float

def aggregate_player_rows(player_rows: Iterable[Mapping[str,object]],
                          schedule_edges: Mapping[tuple[int,int,str],str],
                          scoring_mode: str):
    totals=defaultdict(float)
    for row in player_rows:
        if str(row.get("season_type","")).upper() not in {"REG","REGULAR"}: continue
        season,week=int(row["season"]),int(row["week"])
        off=str(row["recent_team"]).strip().upper()
        pg,p=canonical_position(row.get("position_group")),canonical_position(row.get("position"))
        if pg and p and pg!=p: raise ValueError("canonical position conflict")
        pos=pg or p
        if pos is None: continue
        deff=schedule_edges.get((season,week,off))
        if deff is None: raise KeyError("missing schedule edge")
        totals[(season,week,off,deff,pos)] += score_player_row(row,scoring_mode)
    return [GamePositionPoints(s,w,o,d,p,scoring_mode,pts)
            for (s,w,o,d,p),pts in sorted(totals.items())]

def mean(xs):
    if not xs: raise ValueError("empty mean")
    return statistics.fmean(xs)

def compute_log_sapa(game_rows: Sequence[GamePositionPoints], *, season:int,
                     target_week:int, position:str, scoring_mode:str):
    if target_week < 4 or target_week > 18: raise ValueError("target week outside V1")
    if scoring_mode not in SUPPORTED_SCORING: raise ValueError("unsupported scoring")
    position=canonical_position(position)
    if position not in {"QB","RB","WR","TE"}: raise ValueError("unsupported position")
    lo=max(1,target_week-LOOKBACK_WEEKS)
    hist=[r for r in game_rows if r.season==season and lo<=r.week<target_week
          and r.position==position and r.scoring_mode==scoring_mode]
    if not hist: raise ValueError("no history")
    league=mean([r.points for r in hist])
    by_off,by_def=defaultdict(list),defaultdict(list)
    for r in hist:
        by_off[r.offense_team].append(r); by_def[r.defense_team].append(r)
    out={}
    for d,games in sorted(by_def.items()):
        residuals=[]; unavailable=0
        for g in games:
            comp=[x.points for x in by_off[g.offense_team] if x.defense_team!=d]
            if len(comp)<MIN_OPPONENT_COMPARISON_GAMES:
                unavailable+=1; continue
            residuals.append(g.points-mean(comp))
        if len(residuals)<MIN_DEFENSE_ADJUSTED_GAMES:
            out[d]={"status":"UNAVAILABLE_INSUFFICIENT_ADJUSTED_GAMES","log_sapa":None,
                    "eligible_adjusted_games":len(residuals),"unavailable_defense_games":unavailable}
        else:
            effect=mean(residuals)
            out[d]={"status":"AVAILABLE","log_sapa":league+effect,
                    "league_baseline":league,"defense_effect":effect,
                    "eligible_adjusted_games":len(residuals),"unavailable_defense_games":unavailable}
    return out

def rank_to_matchup_score(values: Mapping[str,float|None]):
    avail=[(t,float(v)) for t,v in values.items() if v is not None and math.isfinite(float(v))]
    if len(avail)<2: return {t:None for t in values}
    ordered=sorted(avail,key=lambda x:(x[1],x[0])); n=len(ordered); ranks={}; i=0
    while i<n:
        j=i+1
        while j<n and ordered[j][1]==ordered[i][1]: j+=1
        ar=((i+1)+j)/2
        for k in range(i,j): ranks[ordered[k][0]]=ar
        i=j
    return {t:(None if t not in ranks else 2*((ranks[t]-1)/(n-1))-1) for t in values}

def window_composite(scores: Sequence[float|None]):
    if not scores or any(v is None for v in scores): return None
    return mean([float(v) for v in scores])

def selftest():
    z={k:0 for k in STAT_FIELDS}
    q=dict(z); q.update(passing_yards=250,passing_tds=2,passing_interceptions=1,rushing_yards=20,rushing_tds=1)
    assert abs(score_player_row(q,"HALF_PPR")-24.0)<1e-12
    r=dict(z); r.update(receiving_yards=80,receiving_tds=1,receptions=6)
    assert abs(score_player_row(r,"HALF_PPR")-17.0)<1e-12
    assert abs(score_player_row(r,"PPR")-20.0)<1e-12
    assert canonical_position("FB")=="RB" and canonical_position("K") is None
    ranks=rank_to_matchup_score({"A":10.0,"B":20.0,"C":20.0,"D":40.0,"E":None})
    assert ranks["A"]==-1.0 and ranks["D"]==1.0 and abs(ranks["B"])<1e-12 and ranks["E"] is None
    assert window_composite([1,0,-1])==0 and window_composite([1,None]) is None
    print("PASS: LOG-SAPA V1 synthetic selftest")

if __name__=="__main__": selftest()
