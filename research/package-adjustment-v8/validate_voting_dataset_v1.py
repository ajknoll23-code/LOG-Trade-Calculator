#!/usr/bin/env python3
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path

def maturity_summary(ballots,challenge_ids):
    # OUTCOME-BLIND BY CONSTRUCTION: intentionally never reads human_choice_left.
    accepted=[b for b in ballots if b.get("accepted_session") is True]
    pairs={(str(b["voter_cluster"]),str(b["challenge_id"])) for b in accepted}
    voters=Counter(v for v,_ in pairs)
    challenges=Counter(c for _,c in pairs)
    complete=sum(1 for n in voters.values() if n==40)
    return {"accepted_pair_count":len(pairs),"distinct_voters":len(voters),
            "distinct_challenges":len(challenges),"complete_voters":complete,
            "minimum_challenge_coverage":min(challenges.values()) if challenges else 0,
            "mature":len(voters)==50 and complete==50 and len(pairs)==2000
                     and set(challenges)==set(challenge_ids) and set(challenges.values())=={50}}

def validate(ballots,schedule,challenge_ids):
    accepted=[b for b in ballots if b.get("accepted_session") is True]
    if len(accepted)!=2000: raise ValueError("accepted dataset must contain exactly 2000 ballots")
    seen=set(); voters=defaultdict(list)
    for b in accepted:
        required=("voter_cluster","challenge_id","accepted_voter_slot","display_left",
                  "display_order","human_choice_left","accepted_session")
        for k in required:
            if k not in b: raise ValueError(f"missing {k}")
        if not isinstance(b["human_choice_left"],bool): raise ValueError("human_choice_left must be bool")
        voter=str(b["voter_cluster"]); cid=str(b["challenge_id"])
        pair=(voter,cid)
        if pair in seen: raise ValueError(f"duplicate voter/challenge {pair}")
        seen.add(pair); voters[voter].append(b)
    if len(voters)!=50: raise ValueError("must contain exactly 50 accepted voters")
    used_slots=set()
    for voter,rows in voters.items():
        if len(rows)!=40: raise ValueError(f"{voter} incomplete")
        slots={int(r["accepted_voter_slot"]) for r in rows}
        if len(slots)!=1: raise ValueError(f"{voter} has multiple voter slots")
        slot=slots.pop()
        if slot in used_slots: raise ValueError(f"duplicate accepted voter slot {slot}")
        used_slots.add(slot)
        spec=schedule["slots"][str(slot)]
        if {r["challenge_id"] for r in rows}!=set(challenge_ids): raise ValueError(f"{voter} challenge set mismatch")
        for r in rows:
            cid=r["challenge_id"]
            if r["display_left"]!=spec["display_left_by_challenge"][cid]:
                raise ValueError(f"{voter}/{cid} side randomization mismatch")
            expected_order=spec["challenge_order"].index(cid)
            if int(r["display_order"])!=expected_order:
                raise ValueError(f"{voter}/{cid} order mismatch")
    if used_slots!=set(range(1,51)): raise ValueError("accepted voter slots must be exactly 1..50")
    m=maturity_summary(accepted,challenge_ids)
    if not m["mature"]: raise ValueError(f"dataset not mature: {m}")
    return {"status":"PASS","voters":50,"ballots":2000,"challenges":40,
            "randomization_schedule_verified":True,"maturity":m}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data",required=True);ap.add_argument("--schedule",required=True)
    ap.add_argument("--catalog",required=True);args=ap.parse_args()
    data=json.loads(Path(args.data).read_text()); schedule=json.loads(Path(args.schedule).read_text())
    catalog=json.loads(Path(args.catalog).read_text()); ids=[c["id"] for c in catalog["challenges"]]
    print(json.dumps(validate(data["ballots"],schedule,ids),indent=2,sort_keys=True))
if __name__=="__main__":main()
