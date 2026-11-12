#!/usr/bin/env python3
"""LOG NL59: hash-only editorial originality ledger; raw PDFs are NOT placed in GitHub.

Identity is pinned to reviewed PDF SHA256s. Prose is tokenized and hashed, not exposed.
This does not approve publication; the four-predecessor and human gates still apply.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

TEAM_NAMES = [
    '<respectable team name>', 'serious gourmet shit','just run power','toddy2times',
    'sunday brunson','cock mchorse','pullham bluecocks','apex predators',
    'narroway farms m714','narroway farms','jersey bagels',"landry's hat",'moose knuckles',
]
GENERIC_MARKERS = ['THE STAKES', 'WHAT HAPPENED', 'THE EVIDENCE', 'AT A GLANCE',
                   'COMBINED RECORD','3-WEEK AVG','V7 POWER RANK','PLAYER SPOTLIGHT',
                   'THE FINAL VERDICT','MY PICK & FINAL WORD','FINAL', 'WEEKLY MEDIAN',
                   'MEDIAN RESULTS']
N=11


def sha(b):return hashlib.sha256(b).hexdigest()


def canonical(text: str, mask_numbers:bool):
    t=' '.join(text.lower().replace('\u2019',"'").split())
    for name in sorted(TEAM_NAMES,key=len,reverse=True):
        t=re.sub(re.escape(name), ' team ', t, flags=re.IGNORECASE)
    if mask_numbers:
        t=re.sub(r'\b\d+(?:[.,]\d+)*\b',' number ',t)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?",t)


def hash_phrase(s,mask_numbers):return sha(' '.join(canonical(s,mask_numbers)).encode())


def article_sections(page,kind,number):
    lines=page.get_text().splitlines()
    marker='WHAT HAPPENED' if kind=='Aftermath' else 'THE STAKES'
    footer='THE FINAL VERDICT' if kind=='Aftermath' else 'MY PICK & FINAL WORD'
    if marker not in lines or footer not in lines:
        raise ValueError(f'Missing required {kind} headings for article {number}')
    body_i=lines.index(marker);verdict_i=lines.index(footer)
    if verdict_i<=body_i:raise ValueError('Invalid body/verdict ordering')
    source_i=next((i for i in range(verdict_i+1,len(lines)) if lines[i].startswith('SOURCE')),None)
    if source_i is None:raise ValueError('Missing editorial source attribution')
    pre=lines[:body_i]
    if kind=='Aftermath':
        # Older Aftermath editions have no per-page LOG marker; newer ones do.
        log_idx=next((i for i,v in enumerate(pre) if re.fullmatch(r'LOG / \d+',v)),None)
        if log_idx is not None:head_lines=pre[log_idx+1:]
        else:
            header_idx=next((i for i,v in enumerate(pre) if v.startswith('AFTERMATH') and 'WEEK' in v),None)
            if header_idx is None:raise ValueError('Missing Aftermath page edition identity')
            head_lines=pre[header_idx+1:]
    else:
        wk_idx=next((i for i,v in enumerate(pre) if v.startswith('WAR ROOM') and 'WEEK' in v),None)
        if wk_idx is None:raise ValueError('Missing War Room week marker')
        head_lines=pre[wk_idx+1:]
    # The first line bearing VS/VS. begins the teams; preceding lines are headline.
    v=next((i for i in range(len(head_lines)-1,-1,-1) if re.search(r'\bvs\.?(?:\s|$)',head_lines[i],re.IGNORECASE)),None)
    if v is None or v==0:raise ValueError('Cannot identify headline independently of team matchup')
    headline=' '.join(head_lines[:v])
    story=' '.join(lines[body_i+1:verdict_i])
    for m in GENERIC_MARKERS:story=story.replace(m,' ')
    verdict=' '.join(lines[verdict_i+1:source_i])
    if len(canonical(story,False))<45 or len(canonical(verdict,False))<5:
        raise ValueError('Editorial prose too short')
    return headline,story,verdict


def issue_fingerprint(raw,edition,week,identity):
    if fitz is None:raise RuntimeError('Install pymupdf to extract approved owner source PDFs')
    with fitz.open(stream=raw,filetype='pdf') as pdf:
        if len(pdf)!=11:raise ValueError('Expected 11-page approved PDF')
        if identity not in pdf[0].get_text():raise ValueError('Wrong issue identity')
        items=[]
        for i in range(1,7):
            pg=pdf[i].get_text()
            if f'MATCHUP {i:02d} / 06' not in pg:raise ValueError('Missing matchup header')
            headline,story,verdict=article_sections(pdf[i],edition,i)
            ngrams=set()
            for mask in (False, True):
                tokens=canonical(story+' '+verdict,mask)
                ngrams.update(sha(' '.join(tokens[j:j+N]).encode()) for j in range(len(tokens)-N+1))
            items.append({'number':i,'headline_hash':hash_phrase(headline,True),
                          'verdict_hash':hash_phrase(verdict,True),
                          'long_phrase_hashes':sorted(ngrams),
                          'token_count':len(canonical(story+' '+verdict,False))})
    return {'edition':edition,'week':week,'pdf_sha256':sha(raw),'pdf_bytes':len(raw),
            'page_count':11,'articles':items,
            'headline_verdict_plaintext_stored':False,'raw_article_text_stored':False}


def compare(candidate,prior):
    flags=[]
    for a in candidate['articles']:
        for b in prior['articles']:
            if a['headline_hash']==b['headline_hash']: flags.append(('headline',a['number'],b['number']))
            if a['verdict_hash']==b['verdict_hash']:flags.append(('verdict',a['number'],b['number']))
            n=len(set(a['long_phrase_hashes']).intersection(b['long_phrase_hashes']))
            if n:flags.append(('long_phrase',a['number'],b['number'],n))
    return flags


def validate(ledger):
    if ledger['schema']!='LOG.NL59.FINGERPRINT_ARCHIVE.v1':raise AssertionError('Bad schema')
    if ledger.get('archive_type')!='SHA256_ONLY_NO_PDF_TEXT':raise AssertionError('Non-private content declared')
    if ledger.get('production_change') is not False or ledger.get('release_authorized') is not False:raise AssertionError('Improper release state')
    if ledger['editorial_mix'] != [75,15,10]:raise AssertionError('Wrong editorial mix')
    editions=ledger['editions'];want={('Aftermath',8),('Aftermath',9),('War Room',9),('War Room',10)}
    if {(e['edition'],e['week']) for e in editions}!=want:raise AssertionError('Missing or duplicate editorial editions')
    if any(len(e['articles'])!=6 or e['page_count']!=11 for e in editions):raise AssertionError('Invalid number of articles/pages')
    pinned={('Aftermath',8):'5ae01d8758ddbfbc98f91983dad5984c69ce9c0b7752130b60fd99f19d6c3098',
            ('Aftermath',9):'d245e75afdfbfaf53b16c731ad0b2ee6b1fae1aa4413ec1ec7847edac301127c',
            ('War Room',9):'6a4c6f39267fe393102580df5361f4b945cb993445f021ddbb1a42d06a015308',
            ('War Room',10):'48e3bd62e8f77e4b7e55e3e43fea17f42bb682b5f91607afb082f764bdbfc1e5'}
    for e in editions:
        if (e['edition'],e['week']) in pinned and e['pdf_sha256']!=pinned[(e['edition'],e['week'])]:
            raise AssertionError('Owner-approved PDF hash drift')
        for art in e['articles']:
            if len(art['long_phrase_hashes'])<20:raise AssertionError('Missing long-phrase fingerprint evidence')
            if any(len(x)!=64 or not re.fullmatch(r'[a-f0-9]{64}',x) for x in [art['headline_hash'],art['verdict_hash'],*art['long_phrase_hashes']]):raise AssertionError('Malformed hash')
    out=[]
    for kind in ('Aftermath','War Room'):
        arr=sorted((e for e in editions if e['edition']==kind),key=lambda x:x['week'])
        flags=compare(arr[-1],arr[0]);out.append({'edition':kind,'candidate_week':arr[-1]['week'],
            'prior_week':arr[0]['week'],'comparison_pairs':36,
            'flags':len(flags),'sample_flags':flags[:10],
            'older_history_missing':True,'publication_gate':'BLOCKED_MISSING_3_PRIOR_EDITIONS'})
    return out


def generate(root:Path):
    with zipfile.ZipFile(root/'NL47-W9-W8-approved-artifact.zip') as a:
        old_after=a.read('LOG-W08-Aftermath-V7-Offense-IDP-Final.pdf')
        old_war=a.read('LOG-W09-War-Room-V7-Offense-IDP-Final.pdf')
    new_after=(root/'LOG-W09-Aftermath-PUBLISHED.pdf').read_bytes()
    new_war=(root/'LOG-W10-War-Room-PUBLICATION-EDITION.pdf').read_bytes()
    editions=[issue_fingerprint(old_after,'Aftermath',8,'WEEK 8'),
              issue_fingerprint(new_after,'Aftermath',9,'WEEK 9'),
              issue_fingerprint(old_war,'War Room',9,'WEEK 9'),
              issue_fingerprint(new_war,'War Room',10,'WEEK 10')]
    return {'schema':'LOG.NL59.FINGERPRINT_ARCHIVE.v1','archive_type':'SHA256_ONLY_NO_PDF_TEXT',
            'description':'Fingerprints of approved PDF article text; source PDFs and their prose are not included',
            'editorial_mix':[75,15,10],
            'accuracy_rule':'100% of factual claims require sourced validation',
            'production_change':False,'release_authorized':False,
            'archived_pdf_count':4,'owner_approved_source_weeks':[9,10],
            'source_notes':['Week 8 Aftermath and Week 9 War Room: successful NL47 release artifact 42759460126',
                            'Week 9 Aftermath and Week 10 War Room: separately user-approved PDFs, checked locally'],
            'editions':editions,
            'known_history_gaps':{'Aftermath':[5,6,7], 'War Room':[6,7,8]},
            'history_policy':'four immediately preceding editions of SAME newsletter are required; reject incomplete coverage',
            'human_editorial_approval_required':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--generate',type=Path);p.add_argument('--validate',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.generate:
        l=generate(a.generate)
        print(json.dumps(validate(l),indent=2))
        if a.output:a.output.write_text(json.dumps(l,separators=(',',':')))
    elif a.validate:
        l=json.loads(a.validate.read_text());print(json.dumps(validate(l),indent=2))
    else:p.error('--generate or --validate required')

if __name__=='__main__':main()
