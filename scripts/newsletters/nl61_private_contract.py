#!/usr/bin/env python3
"""NL61: verify an approved editorial text bundle from an Actions secret.

Never logs or uploads editorial text. This does not authorize release.
"""
import argparse
import base64
import copy
import gzip
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

from nl59_fingerprint_engine import canonical, hash_phrase, sha, N, validate as nl59_validate

ISSUES = (('Aftermath', 9), ('War Room', 10))
CONTRACT_SCHEMA = 'LOG.NL61.PRIVATE_OWNER_APPROVED_EDITORIAL.v1'


def canonical_json(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def decode_secret(encoded):
    if not encoded or len(encoded)>65536:
        raise ValueError('Private approved editorial secret is missing or unreasonably large')
    if not re.fullmatch(r'[A-Za-z0-9+/=\s]+', encoded):
        raise ValueError('Private payload is not Base64')
    packed=base64.b64decode(''.join(encoded.split()), validate=True)
    if len(packed)>50000:raise ValueError('Private payload compressed size exceeds bound')
    raw=gzip.decompress(packed)
    if len(raw)>120000:raise ValueError('Private payload uncompressed size exceeds bound')
    return json.loads(raw)


def article_fingerprint(article):
    # These transformations are exactly the NL59 extraction algorithm.
    assert set(article)=={'number','headline','story','verdict'},'Unexpected article fields'
    if not isinstance(article['number'],int):raise ValueError('Invalid article number')
    for key in ('headline','story','verdict'):
        v=article[key]
        if not isinstance(v,str) or not v.strip() or len(v)>12000:
            raise ValueError('Incomplete editorial text')
    ngrams=set()
    for mask in (False,True):
        tokens=canonical(article['story']+' '+article['verdict'],mask)
        ngrams.update(sha(' '.join(tokens[j:j+N]).encode()) for j in range(len(tokens)-N+1))
    return {'number':article['number'],'headline_hash':hash_phrase(article['headline'],True),
            'verdict_hash':hash_phrase(article['verdict'],True),
            'long_phrase_hashes':sorted(ngrams),
            'token_count':len(canonical(article['story']+' '+article['verdict'],False))}


def verify(payload,ledger,pinned_payload_sha):
    if payload.get('schema')!=CONTRACT_SCHEMA or payload.get('editorial_mix')!=[75,15,10]:
        raise ValueError('Private editorial schema or 75/15/10 mix invalid')
    if payload.get('owner_review')!='APPROVED_SHARED_PDFS' or payload.get('release_authorized') is not False:
        raise ValueError('Owner approval state or release safety invalid')
    if not isinstance(payload.get('issues'),list) or len(payload['issues'])!=2:
        raise ValueError('Need exactly two issues')
    if not hmac.compare_digest(sha(canonical_json(payload)),pinned_payload_sha):
        raise ValueError('Private bundle identity differs from owner-approved PDF extraction')
    nl59_validate(ledger)
    expected={(x['edition'],x['week']):x for x in ledger['editions']}
    results=[]
    seen=set()
    for issue in payload['issues']:
        if set(issue)!={'edition','week','pdf_sha256','articles'}:raise ValueError('Unrecognized private issue fields')
        key=(issue['edition'],issue['week'])
        if key not in ISSUES or key in seen:raise ValueError('Unapproved or duplicate edition/week')
        seen.add(key)
        historical=expected[key]
        if issue['pdf_sha256']!=historical['pdf_sha256']:raise ValueError('Owner-approved PDF SHA mismatch')
        arts=issue['articles']
        if len(arts)!=6 or [a['number'] for a in arts]!=list(range(1,7)):
            raise ValueError('Expected six numbered articles')
        for a,b in zip(arts,historical['articles']):
            produced=article_fingerprint(a)
            if produced!=b:raise ValueError(f'Owner-approved article fingerprint mismatch: {key} #{a["number"]}')
        results.append({'edition':issue['edition'],'week':issue['week'],
                        'verified_articles':len(arts),'approved_pdf_sha256':historical['pdf_sha256'],
                        'editorial_identity_match':True,'missing_historical_weeks':ledger['known_history_gaps'].get(issue['edition'],[]),
                        'release_gate':'BLOCKED_MISSING_HISTORY_AND_HUMAN_APPROVAL'})
    if seen!=set(ISSUES):raise ValueError('Missing required owner-approved issue')
    return {'workflow':'A-NL61R1','status':'PRIVATE_EDITORIAL_HANDOFF_VERIFIED',
            'private_issues_verified':len(results),'private_articles_verified':12,
            'public_editorial_text_exported':False,'production_changed':False,
            'automatic_release_authorized':False,'issues':results}


def self_test(payload,ledger,pinned):
    good=verify(payload,ledger,pinned)
    assert good['private_articles_verified']==12
    variants=[]
    for name,fn in [
        ('headline tamper',lambda x:x['issues'][0]['articles'][0].__setitem__('headline','Forged headline')),
        ('narrative tamper',lambda x:x['issues'][0]['articles'][0].__setitem__('story','Forged narrative')),
        ('verdict tamper',lambda x:x['issues'][1]['articles'][1].__setitem__('verdict','Forged verdict')),
        ('PDF hash tamper',lambda x:x['issues'][0].__setitem__('pdf_sha256','0'*64)),
        ('wrong week',lambda x:x['issues'][0].__setitem__('week',10)),
        ('missing article',lambda x:x['issues'][1]['articles'].pop()),
        ('wrong mix',lambda x:x.__setitem__('editorial_mix',[55,15,30])),
        ('release forgery',lambda x:x.__setitem__('release_authorized',True)),
        ('extra issue',lambda x:x['issues'].append(copy.deepcopy(x['issues'][0]))),
        ('swapped article',lambda x:x['issues'][0]['articles'].__setitem__(0,copy.deepcopy(x['issues'][1]['articles'][0]))),
    ]:
        changed=copy.deepcopy(payload);fn(changed)
        try:verify(changed,ledger,pinned)
        except (ValueError,AssertionError,KeyError,TypeError):pass
        else:raise AssertionError('Adversarial test improperly passed: '+name)
        variants.append(name)
    bad_led=copy.deepcopy(ledger);bad_led['editorial_mix']=[55,15,30]
    try:verify(payload,bad_led,pinned)
    except (ValueError,AssertionError):pass
    else:raise AssertionError('Tampered ledger was accepted')
    variants.append('tampered ledger')
    for malformed in ('', 'abcd', '@@@'):
        try:decode_secret(malformed)
        except (ValueError,UnicodeError,EOFError,TypeError,json.JSONDecodeError,base64.binascii.Error, OSError):pass
        else:raise AssertionError('Malformed secret was accepted')
    variants.append('missing/malformed secret')
    return variants


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    # Absolutely do not print, store or upload the decoded secret text.
    payload=decode_secret(os.environ.get('LOG_APPROVED_EDITORIAL_BUNDLE_B64',''))
    ledger=json.loads(args.ledger.read_text())
    result=verify(payload,ledger,args.sha256)
    tests=self_test(payload,ledger,args.sha256)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'NL61R1-PRIVATE-HANDOFF-PREVIEW.json').write_text(json.dumps({'validation':result,'adversarial_tests':len(tests)},indent=2))
    md=["# NL61R1 — Private approved editorial handoff (preview)","",
        "**12/12 owner-approved articles verified against NL59 fingerprints.**",
        "","No editorial prose or PDFs uploaded to GitHub. No changes to production or automatic publication.",
        "","| Edition | Verified articles | History coverage | Release |", "|---|---:|---|---|",]
    for i in result['issues']:
        md.append(f"| {i['edition']} W{i['week']} | 6/6 | Missing {', '.join(str(x) for x in i['missing_historical_weeks'])} | BLOCKED |")
    md.extend(['',f'{len(tests)} adversarial tests passed.','',
        'The private bundle is available only in runner memory for this read-only job.',
        'A future controlled builder must explicitly consume validated editorial text and repeat these checks.',
        'Green means safe private handoff, not permission to release newsletters.'])
    (args.out/'NL61R1-PRIVATE-HANDOFF-PREVIEW.md').write_text('\n'.join(md)+'\n')
    print('PASS NL61: 12 owner-approved articles matched NL59 fingerprint identities; '+str(len(tests))+' adversarial tests passed; no publication authorization')

if __name__=='__main__':main()
