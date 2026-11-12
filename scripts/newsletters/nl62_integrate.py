#!/usr/bin/env python3
"""NL62 protected integration proof: private approved JSON -> PDF -> fingerprints.

Run *only* after a human has approved the GitHub Environment. The code never
publishes PDFs; it writes hashes-only QA output, and requires the known cold
start gaps to remain explicitly blocked.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,re,sys,tempfile
from pathlib import Path
import fitz

from nl59_fingerprint_engine import issue_fingerprint,compare
from nl61_private_contract import verify,article_fingerprint,canonical_json
from nl62_renderer import approved_pages,json_reflow,verify_pdf_pages
from nl58_score_validator import validate_data

FILES={'Aftermath':('Week9-Aftermath-OWNER-APPROVED.pdf',9),
       'War Room':('Week10-WarRoom-OWNER-APPROVED.pdf',10)}

def sha(data):return hashlib.sha256(data).hexdigest()

def load(p):return json.loads(Path(p).read_text('utf-8'))

def current_edition_metadata(meta,edition,week):
    if meta.get('schema')!='LOG.NL62.ARTICLE_METADATA.v1':raise ValueError('Incorrect editorial metadata schema')
    a=[x for x in meta.get('issues',[]) if x.get('edition')==edition and x.get('week')==week]
    if len(a)!=1 or len(a[0].get('articles',[]))!=6:raise ValueError('Missing/ambiguous editorial page metadata')
    arts=a[0]['articles']
    for row in arts:
        if set(row)!={'teams','source'}:raise ValueError('Unrecognized metadata')
        if not isinstance(row['teams'],str) or len(row['teams'])>200 or len(row['teams'])<8:raise ValueError('Invalid matchup teams')
        if not isinstance(row['source'],str) or not row['source'].startswith('SOURCE '):raise ValueError('Invalid source credit')
        if len(row['source'])>850:raise ValueError('Oversized source credit')
    return arts

def reference_team_source_check(source_path,meta,kind):
    """Source credits and teams must originate from approved private PDF."""
    with fitz.open(source_path) as d:
        for i,entry in enumerate(meta,1):
            txt=' '.join(d[i].get_text().split()).replace('🐴','').replace(' VS. ',' vs. ').lower()
            team=' '.join(entry['teams'].lower().split())
            if team not in txt:raise ValueError(f'{kind} #{i}: teams differ from approved issue')
            lines=d[i].get_text().splitlines()
            source_ix=next((j for j,x in enumerate(lines) if x.startswith('SOURCE')),None)
            if source_ix is None:raise ValueError('Approved source has no SOURCE label')
            original=[]
            for line in lines[source_ix:]:
                if original and (line.startswith('LOG') or re.fullmatch(r'\d\d? / 11',line)):break
                original.append(line)
            actual=' '.join(' '.join(original).split())
            supplied=' '.join(entry['source'].split())
            if actual!=supplied:raise ValueError(f'{kind} #{i}: source credit not identical to approved PDF')

def run(private:Path,ledger_path:Path,data_root:Path,war_week:int,nl44_id,nl45_id,out:Path):
    if war_week!=10:raise ValueError('NL62 bootstrap is pinned to Week 10 and its Week 9 Aftermath')
    ledger=load(ledger_path)
    articles=load(private/'approved-articles.json')
    metadata=load(private/'article-metadata.json')
    approval=load(private/'approval.json')
    if approval.get('schema')!='LOG.NL62.OWNER_APPROVAL.v1' or approval.get('release_authorized') is not False:
        raise ValueError('Invalid or already-authorized approval record')
    if approval.get('editorial_mix')!=[75,15,10] or approval.get('owner_approval_signed') is not False:
        raise ValueError('Unexpected bootstrap approval policy')
    if approval.get('cold_start_exception') is not None:raise ValueError('NL62 preview is not a history override')
    if len(approval.get('issues',[]))!=2:raise ValueError('Approval record missing one issue')
    # Pin NL61 payload to its approved canonical JSON; no repo secret needed.
    expected_payload_sha=sha(canonical_json(articles))
    if approval.get('payload_sha256')!=expected_payload_sha:
        raise ValueError('Private editorial JSON differs from approved manifest')
    if approval.get('metadata_sha256')!=sha(canonical_json(metadata)):
        raise ValueError('Private metadata differs from approved manifest')
    verified=verify(articles,ledger,expected_payload_sha)
    if verified.get('private_articles_verified')!=12:raise RuntimeError('All 12 articles must be approved')
    by_kind={x['edition']:x for x in articles['issues']}
    data=validate_data(data_root,war_week,str(nl44_id),str(nl45_id))
    if data['through']!=9:raise RuntimeError('Wrong completed NFL week')
    results=[]
    with tempfile.TemporaryDirectory(prefix='nl62-private-') as td:
        tmp=Path(td)
        for kind,(filename,week) in FILES.items():
            ref=private/filename
            if not ref.is_file():raise FileNotFoundError('Owner-approved private PDF missing: '+filename)
            expected=next(x for x in ledger['editions'] if x['edition']==kind and x['week']==week)
            if sha(ref.read_bytes())!=expected['pdf_sha256']:raise ValueError('Private PDF changed from NL59 hash ledger')
            if next(x for x in approval['issues'] if x['edition']==kind)['pdf_sha256']!=expected['pdf_sha256']:
                raise ValueError('PDF approval manifest identity differs')
            m=current_edition_metadata(metadata,kind,week)
            reference_team_source_check(ref,m,kind)
            for mode in ('approved_pages','json_reflow'):
                output=tmp/(kind.replace(' ','')+'-'+mode+'.pdf')
                if mode=='approved_pages':approved_pages(ref,output)
                else:json_reflow(by_kind[kind],m,ref,output)
                actual=issue_fingerprint(output.read_bytes(),kind,week,'WEEK '+str(week))
                if actual['articles']!=expected['articles']:
                    raise RuntimeError(f'Post-render fingerprint identity FAILURE: {kind}, {mode}')
                verify_pdf_pages(output,ref,range(11) if mode=='approved_pages' else range(7,11))
                results.append({'edition':kind,'week':week,'mode':mode,'pages':11,
                                'approved_articles_verified':6,'appendix_verified':4,
                                'full_visual_parity':mode=='approved_pages',
                                'render_sha256':sha(output.read_bytes())})
        # Enforce post-render adversarial control: modified editorial must fail.
        tampered=copy.deepcopy(by_kind['War Room'])
        tampered['articles'][0]['verdict']+=' FORGED'
        target=next(e for e in ledger['editions'] if e['edition']=='War Room' and e['week']==10)
        if article_fingerprint(tampered['articles'][0])==target['articles'][0]:
            raise RuntimeError('Tampered article was accepted')
    missing=ledger['known_history_gaps']
    if missing.get('Aftermath')!=[5,6,7] or missing.get('War Room')!=[6,7,8]:
        raise RuntimeError('Unexpected four-edition history coverage; re-audit')
    report={'schema':'LOG.NL62.PROTECTED_INTEGRATION_PREVIEW.v1',
            'status':'INTEGRATION_VERIFIED_RELEASE_BLOCKED','editors_approved_existing_pdfs':True,
            'approved_articles_verified':12,'rendered_issues':results,
            'source_data':{'war_week':10,'scored_through_week':9,'V7_weights':'35/20/10/25/10',
                            'NL44_run_id':str(nl44_id),'NL45_run_id':str(nl45_id),
                            'source_pdf_sha256':data['nl44_pdf_sha']},
            'history_gaps':missing,'originality_gate':'BLOCKED_MISSING_HISTORY',
            'requires_owner_signed_cold_start_exception':True,
            'requires_environment_approval':True,
            'production_modified':False,'private_article_text_exported':False,
            'raw_pdf_uploaded':False,'release_authorized':False}
    out.mkdir(parents=True,exist_ok=True)
    (out/'NL62R1-PROTECTED-INTEGRATION.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# NL62R1 - Protected editorial integration proof','',
           '**PASS**: 12/12 approved article fingerprints survived PDF generation in both adapters.',
           '**PASS**: Four approved V7/Offense/IDP appendix pages remained visually/text identical for each edition.',
           '**PASS**: NL44 and NL45 validated against the frozen Week 9 evidence.',
           '**BLOCKED**: Earlier history incomplete, no signed exception or automatic publication.',
           '', '| Edition | Adapter | Articles | Appendix |', '|---|---|---:|---:|']
    for r in results:lines.append(f"| {r['edition']} W{r['week']} | {r['mode']} | 6/6 | 4/4 |")
    lines.extend(['','No PDFs or editorial prose are uploaded as artifacts.','Production NL47 was not modified.'])
    (out/'NL62R1-PROTECTED-INTEGRATION.md').write_text('\n'.join(lines)+'\n')
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--private',type=Path,required=True)
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--war-week',type=int,default=10)
    p.add_argument('--nl44-run-id',default='42837956712')
    p.add_argument('--nl45-run-id',default='42838026515')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(a.private,a.ledger,a.data_root,a.war_week,a.nl44_run_id,a.nl45_run_id,a.out)
    print('PASS NL62 protected preview: 12/12 approved articles survived both adapters; publication BLOCKED')
    print('Frozen data validated and audited; raw editorial content is not printed.')
if __name__=='__main__':main()
