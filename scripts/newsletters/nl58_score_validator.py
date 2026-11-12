#!/usr/bin/env python3
"""NL47: production-ready, owner-approved weekly newsletter PDF artifact builder.

Verifies exact source NL44 V7 rankings, NL45 lineups and NL39 Aftermath editorial.
Maintains six unchanged matchup articles per edition and approved two unit leaderboards.
Removes NL39 Aftermath shadow-only labelling without altering underlying sports copy.
Read-only: no repository changes, email sends, free agents or trade calculator updates.
"""
from __future__ import annotations

def _nl57_equal_source_articles(original, revised):
    """Allow only recognized publisher footer differences AFTER complete source credit.

    Reject edits in a six-matchup article including headline, picks, numeric evidence,
    week, SOURCE/credit, and any unexpected post-footer content. Never compares cover.
    """
    import re as _nl57_re
    if not isinstance(original, str) or not isinstance(revised, str):
        return False

    def _core(text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines or not _nl57_re.fullmatch(r'MATCHUP 0[1-6] / 06', lines[0]):
            return None
        if not any(_nl57_re.fullmatch(r'(WAR ROOM|AFTERMATH) · WEEK [0-9]{1,2}', line) for line in lines[:4]):
            return None
        def _footer(line):
            return bool(
                _nl57_re.fullmatch(r'LOG\s*/\s*\d+', line) or
                _nl57_re.fullmatch(r'LOG\s*/\s*V7 POWER INDEX\s*/\s*W\d+ REISSUE', line) or
                _nl57_re.fullmatch(r'LOG\s*/\s*V7 POWER INDEX\s*/\s*WEEK [0-9]{1,2} EDITION', line) or
                _nl57_re.fullmatch(r'LOG\s*/\s*AFTERMATH W\d+\s*/\s*FINAL', line) or
                _nl57_re.fullmatch(r'LOG\s*/\s*WEEK \d+\s*/\s*[A-Z -]+', line) or
                line.startswith('LOG EDITORIAL SHADOW')
            )
        footer_index = next((j for j, line in enumerate(lines) if _footer(line)), None)
        if footer_index is None or footer_index < 5:
            return None
        core, footer = lines[:footer_index], lines[footer_index:]
        if not any(line.startswith('SOURCE Sleeper') for line in core):
            return None
        if not all(_footer(line) for line in footer):
            return None
        # Source credit must terminate editorial text; no pre-credit footer.
        if next(j for j, line in enumerate(core) if line.startswith('SOURCE Sleeper')) < len(core)-3:
            return None
        return core

    old, new = _core(original), _core(revised)
    return old is not None and new is not None and old == new

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from collections import defaultdict
import math
import fitz

LEAGUE_ID='1326679131051532288'
KEYS=('QB','RB','WR','TE','DL','LB','DB','K','P','DST')
O_KEYS=('QB','RB','WR','TE')
D_KEYS=('DL','LB','DB')
BACKGROUND='#FCFAF5'; NAVY='#112E46'; INK='#19374C'; STEEL='#617989'
ACCENT='#B96D60'; PALE='#E9EEF0'; LINE='#C7D2D9'; GOLD='#AC7C43'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def read_csv(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def dec(v):
    try:return Decimal(str(v).replace(',','').strip())
    except (InvalidOperation,TypeError,AttributeError):raise ValueError(f'Invalid number {v!r}')

def fmt(v):return f'{dec(v):,.2f}'

def hex_rgb(s):
    s=s.lstrip('#');return tuple(int(s[i:i+2],16)/255 for i in (0,2,4))

def sha(b):return hashlib.sha256(b).hexdigest()

def check_sum(label,a,b,tolerance=Decimal('0.015')):
    if abs(a-b)>tolerance: raise ValueError(f'{label}: {a} != {b}')


def validate_data(input_dir, war_week, run_44=None, run_45=None):
    w=war_week-1
    pdfpath=input_dir/'nl44'/f'LOG-W{war_week:02d}-War-Room-V7-Final.pdf'
    epath=input_dir/'nl44'/f'LOG-W{war_week:02d}-V7-Evidence.json'
    formula=input_dir/'nl44'/'V7-PRODUCTION-FORMULA.json'
    if not pdfpath.is_file() or not epath.is_file() or not formula.is_file():raise ValueError('NL44 approved production source incomplete')
    evidence=load_json(epath);cfg=load_json(formula)
    if evidence.get('edition')!='WarRoom' or evidence.get('model')!='V7' or evidence.get('war_week')!=war_week or evidence.get('rank_through')!=w:
        raise ValueError('NL44 source week/edition/V7 mismatch')
    if cfg.get('league_id')!=LEAGUE_ID or cfg.get('production_power_formula')!='V7' or cfg.get('policy')!='OWNER_APPROVED_PRODUCTION':
        raise ValueError('Expected owner-approved, pinned V7 production policy')
    expected={'season_scoring':.35,'all_play':.2,'recent_scoring':.1,'scoring_floor':.25,'h2h':.1}
    for k,v in expected.items():
        if abs(float(evidence['weights'].get(k,-1))-v)>1e-9 or abs(float(cfg['weights'].get(k,-1))-v)>1e-9:
            raise ValueError(f'Frozen V7 weights drifted: {k}')
    ranks=evidence['rankings']
    if len(ranks)!=12 or sorted(x['rank'] for x in ranks)!=list(range(1,13)) or len({x['roster_id'] for x in ranks})!=12:
        raise ValueError('V7 evidence does not cover 12 unique ranked teams')
    ledger=input_dir/'nl45'
    manifest=load_json(ledger/'run-manifest.json')
    if str(manifest.get('league_id'))!=LEAGUE_ID or int(manifest.get('season',-1))!=2026 or manifest.get('through_week')!=w or int(manifest.get('total_team_weeks',-1))!=12*w:
        raise ValueError('NL45 season/week/12-team coverage mismatch')
    season=read_csv(ledger/'season-all-teams.csv')
    weekly=read_csv(ledger/'weekly-offense-idp-splits.csv')
    starters=read_csv(ledger/'every-scoring-starter.csv')
    if len(season)!=12 or len(weekly)!=12*w or not starters or len(starters)!=int(manifest['total_starters']):
        raise ValueError('NL45 row-count integrity mismatch')
    by_id={int(x['roster_id']):x for x in season}
    if len(by_id)!=12 or set(by_id)!=set(int(x['roster_id']) for x in ranks):raise ValueError('NL45/NL44 roster coverage mismatch')
    names={int(x['roster_id']):x['team'] for x in ranks}
    by_wid={(int(x['week']),int(x['roster_id'])):x for x in weekly}
    if len(by_wid)!=12*w or any((week,rid) not in by_wid for rid in names for week in range(1,w+1)):
        raise ValueError('Missing weekly score rows')
    for rid,row in by_id.items():
        if row['team']!=names[rid] or int(row['weeks'])!=w:raise ValueError(f'Name or week mismatch on roster {rid}')
        a=sum((dec(row[k]) for k in O_KEYS),Decimal(0))
        b=sum((dec(row[k]) for k in D_KEYS),Decimal(0))
        check_sum(f'{rid} offense',a,dec(row['offense']))
        check_sum(f'{rid} IDP',b,dec(row['idp_defense']))
        check_sum(f'{rid} full score',a+b+dec(row['kickers'])+dec(row['other']),dec(row['sleeper_points']))
        if abs(dec(row['reconciliation_delta']))>Decimal('.11'):raise ValueError('NL45 reported nonzero reconciliation')
        for k in ('offense','idp_defense','kickers','other','sleeper_points',*KEYS):
            check_sum(f'{rid} season aggregate {k}',sum((dec(by_wid[(week,rid)][k]) for week in range(1,w+1)),Decimal(0)),dec(row[k]),Decimal('.12'))
        check_sum(f'{rid} V7 PF',dec(row['sleeper_points']),dec(next(x['pf'] for x in ranks if int(x['roster_id'])==rid)),Decimal('.015'))
    for wk in range(1,w+1):
        for rid in names:
            r=by_wid[(wk,rid)]
            check_sum(f'W{wk}/R{rid} reconciliation',dec(r['offense'])+dec(r['idp_defense'])+dec(r['kickers'])+dec(r['other']),dec(r['sleeper_points']),Decimal('.12'))
            if abs(dec(r['reconciliation_delta']))>Decimal('.11'):raise ValueError('Weekly starter mismatch')
    for r in starters:
        if (int(r['week']),int(r['roster_id'])) not in by_wid:raise ValueError('Unexpected starter week/roster')
        if r['category'] not in KEYS:raise ValueError('Unexpected starter category')
    if sum(dec(x['reconciliation_delta']) for x in season)!=dec(manifest['total_reconciliation_delta']):
        raise ValueError('Manifest reconciliation mismatch')
    # Ranking position checks with deterministic rank and stable ID tie-break.
    for cat,field in [('offense','offense_rank'),('idp_defense','defense_rank')]:
        order=sorted(season,key=lambda x:(-dec(x[cat]),int(x['roster_id'])))
        for n,x in enumerate(order,1):
            if int(x[field])!=n:raise ValueError(f'Incorrect NL45 {cat} rank for {x["team"]}')
    if not pdfpath.is_file():raise ValueError('Source newsletter missing')
    with fitz.open(pdfpath) as d:
        if len(d)!=9:raise ValueError('NL44 War Room must have nine fully verified pages')
        if 'POWER RANKINGS / V7' not in d[7].get_text() or 'POWER RANKINGS / V7' not in d[8].get_text():
            raise ValueError('Source is not the production V7 newsletter')
        if 'NOT PUBLISHED' in ' '.join(p.get_text() for p in d):
            raise ValueError('Expected share-ready NL44 War Room without shadow watermarks')
    return {'war_pdf':pdfpath,'rankings':ranks,'season':season,'weekly':weekly,'by_wid':by_wid,'names':names,
            'through':w,'war_week':war_week,'nl45_manifest':manifest,'nl44_evidence':evidence,
            'nl44_pdf_sha':sha(pdfpath.read_bytes()),'source_nl44_run':run_44,'source_nl45_run':run_45}

class Pen:
    def __init__(self,page):
        self.page=page
        self.name='LOG-DejaVu';self.boldname='LOG-DejaVuBold'
        self.page.insert_font(fontname=self.name,fontfile=FONT)
        self.page.insert_font(fontname=self.boldname,fontfile=FONT_BOLD)
        self.font=fitz.Font(fontfile=FONT)
        self.bold=fitz.Font(fontfile=FONT_BOLD)
    def text(self,x,y,label,size=9,color=INK,bold=False,maxw=None,minsize=7.25):
        label=str(label)
        # Standard PDF font lacks this emoji; keep team name legible without a missing-glyph box.
        label=label.replace('🐴','').strip()
        font=self.bold if bold else self.font
        if maxw:
            while size>minsize and font.text_length(label,fontsize=size)>maxw:size-=.15
            if font.text_length(label,fontsize=size)>maxw:raise ValueError(f'Text overflow: {label} at {size} into {maxw}')
        self.page.insert_text((x,y),label,fontsize=size,fontname=self.boldname if bold else self.name,color=hex_rgb(color),overlay=True)
    def rect(self,x0,y0,x1,y1,fill):self.page.draw_rect(fitz.Rect(x0,y0,x1,y1),color=None,fill=hex_rgb(fill))
    def line(self,x0,y0,x1,y1,stroke=LINE,width=.5):self.page.draw_line((x0,y0),(x1,y1),color=hex_rgb(stroke),width=width)


def page_frame(doc,title,sub,section,edition,week,page_in_section):
    W,H=doc[0].rect.width,doc[0].rect.height
    page=doc.new_page(width=W,height=H);p=Pen(page)
    p.rect(0,0,W,H,BACKGROUND)
    p.rect(0,0,W,107,NAVY);p.rect(0,104,W,108,ACCENT)
    p.text(15,20,'LEAGUE OF ORDINARY GENTLEMEN',7.4,'#E8CFBC',True,maxw=W-30)
    p.text(15,47,title,18.3,'#FFF8EB',True,maxw=W-30,minsize=15.0)
    p.text(15,68,sub,9.0,'#F5E2D5',False,maxw=W-30)
    p.text(15,87,f'{edition.upper()}  /  WEEK {week}  /  {page_in_section} OF 2',8.0,'#E5CCC1',True,maxw=W-30)
    p.text(15,123,section,8.3,ACCENT,True,maxw=W-30)
    return p,W,H


def ranking_movement(data,category):
    current=sorted(data['season'],key=lambda x:(-dec(x[category]),int(x['roster_id'])))
    prior={}
    if data['through']>=2:
        val=[]
        for x in data['season']:
            rid=int(x['roster_id'])
            total=sum((dec(data['by_wid'][(i,rid)][category]) for i in range(1,data['through'])),Decimal(0))
            val.append((rid,total))
        val.sort(key=lambda x:(-x[1],x[0]));prior={rid:i for i,(rid,_) in enumerate(val,1)}
    out=[]
    for i,x in enumerate(current,1):
        rid=int(x['roster_id']);change=prior.get(rid,i)-i if prior else None
        out.append({'rank':i,'team':x['team'],'roster_id':rid,'points':dec(x[category]),'movement':change})
    return out


def movement_label(m):
    if m is None:return 'NEW'
    if m>0:return f'UP {m}'
    if m<0:return f'DN {-m}'
    return 'EVEN'


def top_week(data,category):
    candidates=sorted(data['weekly'],key=lambda x:(-dec(x[category]),int(x['week']),int(x['roster_id'])))
    x=candidates[0]
    return {'week':int(x['week']),'team':x['team'],'points':dec(x[category])}


def draw_leaderboard(doc,data,edition,category,edition_week,preview):
    offense=category=='offense'
    ranks=ranking_movement(data,category)
    name='OFFENSE' if offense else 'IDP DEFENSE'
    title='OFFENSIVE POWERHOUSES' if offense else 'DEFENSIVE POWERHOUSES'
    p,W,H=page_frame(doc,title, f'ACTUAL STARTER POINTS  /  WEEKS 1-{data["through"]}',
                     f'ALL 12 TEAMS  /  {name} SCORING',edition,edition_week,1 if offense else 2)
    p.text(15,140, 'RANK   TEAM',7.5,STEEL,True)
    p.text(W-91,140,'POINTS',7.5,STEEL,True)
    p.text(W-50,140,'MOVE',7.5,STEEL,True)
    p.line(15,145,W-15,145)
    start_y=151;rh=32.0
    for i,row in enumerate(ranks):
        y=start_y+i*rh
        if i%2==0:p.rect(13,y,W-13,y+rh-1,PALE)
        if i==0:p.rect(13,y,16,y+rh-1,GOLD)
        p.text(18,y+19,f'{row["rank"]:02d}',10,ACCENT if i<3 else STEEL,True)
        p.text(40,y+18,row['team'],9.6,INK,i<3,maxw=W-148,minsize=7.6)
        p.text(W-102,y+18,fmt(row['points']),9.4,INK,True,maxw=67,minsize=8.0)
        mov=movement_label(row['movement'])
        p.text(W-47,y+18,mov,7.1,ACCENT if row['movement'] and row['movement']>0 else STEEL,True,maxw=33,minsize=6.6)
    after=start_y+12*rh+15
    p.line(15,after,W-15,after)
    # Keep the concise unit-wide highlights; do not feature individual position leaders.
    if offense:
        peak=top_week(data,category)
        p.text(16,after+22, f'BEST SINGLE WEEK: {peak["team"]}  |  W{peak["week"]}  |  {fmt(peak["points"])}',
               7.4,STEEL,maxw=W-32,minsize=6.4)
    else:
        spread=max(data['season'],key=lambda x:(abs(int(x['offense_rank'])-int(x['defense_rank'])),-int(x['roster_id'])))
        p.text(16,after+21,f'WIDEST UNIT SPLIT: {spread["team"]}  |  OFF #{spread["offense_rank"]}  /  IDP #{spread["defense_rank"]}',
               7.35,STEEL,maxw=W-32,minsize=6.2)
        peak=top_week(data,category)
        p.text(16,after+41, f'BEST IDP WEEK: {peak["team"]}  |  W{peak["week"]}  |  {fmt(peak["points"])}',
               7.4,STEEL,maxw=W-32,minsize=6.4)
    p.line(15,H-36,W-15,H-36)
    p.text(15,H-24,'SOURCE: SLEEPER STARTER SCORES. KICKERS EXCLUDED.',6.5,STEEL,maxw=W-30,minsize=6.0)
    p.text(15,H-13,'WEEK-TO-WEEK RANK MOVEMENT VS PREVIOUS COMPLETED WEEK.',6.2,STEEL,maxw=W-30,minsize=5.8)
    return ranks


def power_rank_appendix(doc,data,week):
    ranks=data['rankings'];W,H=doc[0].rect.width,doc[0].rect.height
    for part in range(2):
        p,_,_=page_frame(doc,'POWER RANKINGS / V7',f'AFTERMATH WEEK {week}   /   THROUGH WEEK {data["through"]}',
                           'FROZEN V7  /  ORIGINAL H2H + MEDIAN SPLITS','Aftermath',week,part+1)
        p.text(15,144,'35% SCORING  /  20% ALL-PLAY  /  10% RECENT',7.3,INK,maxw=W-30)
        p.text(15,157,'25% SCORING FLOOR  /  10% HEAD-TO-HEAD',7.3,INK,maxw=W-30)
        y0=169;rowh=72
        for i,x in enumerate(ranks[part*6:(part+1)*6]):
            y=y0+rowh*i
            if i%2==0:p.rect(13,y,W-13,y+rowh-4,PALE)
            p.text(18,y+18,f'{x["rank"]:02d}',11,ACCENT,True)
            p.text(44,y+18,x['team'],9.2,INK,True,maxw=W-117,minsize=7.2)
            p.text(W-65,y+18,f'{float(x["power_score"]):.1f}',11,INK,True,maxw=49)
            h=x['h2h'];m=x['median'];c=x['combined'];
            label=f'H2H {h["w"]}-{h["l"]}    MED {m["w"]}-{m["l"]}    TOTAL {c["w"]}-{c["l"]}'
            p.text(44,y+36,label,7.7,STEEL,False,maxw=W-54,minsize=6.8)
            p.text(44,y+51,f'PF {fmt(x["pf"])}     Q1 FLOOR {fmt(x["floor"])}',8.0,INK,False,maxw=W-54,minsize=7.2)
        p.line(15,H-40,W-15,H-40)
        p.text(15,H-26,'EDITORIAL V7 INDEX - NOT OFFICIAL SLEEPER STANDINGS',7.0,STEEL,maxw=W-30,minsize=6.3)
        p.text(15,H-13,'SOURCE: VERIFIED COMPLETED 2026 SLEEPER MATCHUPS.',6.4,STEEL,maxw=W-30)



def release_aftermath_source(doc, week):
    """Conservatively remove only NL39 preview-specific labels from original 7 pages.

    Strict paragraph audit below guarantees the six editorial matchup articles remain
    byte-for-byte identical in extracted text, apart from the original page footer.
    """
    if len(doc)!=7: raise ValueError('Expected seven-page NL39 Aftermath source')
    original_text=[page.get_text() for page in doc]
    assert 'AFTERMATH' in original_text[0].upper()
    if f'WEEK {week}' not in original_text[0].upper():
        raise ValueError('Aftermath cover is for the wrong completed week')
    for i,page in enumerate(doc):
        blocks=page.get_text('blocks')
        footers=[b for b in blocks if 'LOG EDITORIAL SHADOW' in b[4] and 'NOT PUBLISHED' in b[4]]
        if len(footers)!=1:raise ValueError(f'Aftermath page {i+1}: unknown or missing preview footer')
        f=footers[0];W,H=page.rect.width,page.rect.height
        if f[1]<H-42:raise ValueError(f'Aftermath page {i+1}: footer unexpectedly overlaps story')
        page.add_redact_annot(fitz.Rect(max(10,f[0]-3),f[1]-2,min(W-7,f[2]+3),min(H-4,f[3]+3)),
                              fill=(1,1,1),cross_out=False)
        if i==0:
            decks=[b for b in blocks if 'The NL36 writing you approved' in b[4]]
            notes=[b for b in blocks if 'DESIGN SHADOW' in b[4] and 'NOT PUBLISHED' in b[4]]
            if len(decks)!=1 or len(notes)!=1:
                raise ValueError('Unknown NL39 Aftermath cover layout: refused to remove editorial text')
            deck=fitz.Rect(decks[0][:4]);note=fitz.Rect(notes[0][:4])
            coverdeck=fitz.Rect(max(15,deck.x0-3),deck.y0-3,min(W-15,deck.x1+20),deck.y1+6)
            covernote=fitz.Rect(max(15,note.x0-10),note.y0-9,min(W-15,note.x1+58),note.y1+9)
            page.add_redact_annot(coverdeck,fill=hex_rgb(BACKGROUND),cross_out=False)
            page.add_redact_annot(covernote,fill=hex_rgb(BACKGROUND),cross_out=False)
        page.apply_redactions(images=0,graphics=0,text=0)
        p=Pen(page)
        p.text(20,H-12,f'LOG  /  THE AFTERMATH  /  WEEK {week}  /  PAGE {i+1}',7.2,STEEL,maxw=W-36,minsize=7.0)
        if i==0:
            p.text(coverdeck.x0+2,coverdeck.y0+16,'Six matchups. Real numbers. Sharp opinions.',10.0,INK,maxw=coverdeck.width-3)
            p.text(coverdeck.x0+2,coverdeck.y0+32,'Weekly results, receipts and final verdicts.',10.0,INK,maxw=coverdeck.width-3)
            p.rect(covernote.x0,covernote.y0,covernote.x1,covernote.y1,'#EEEAE5')
            p.rect(covernote.x0,covernote.y0,covernote.x0+2.2,covernote.y1,ACCENT)
            p.text(covernote.x0+9,covernote.y0+14,f'WEEK {week}  /  THE AFTERMATH',8,INK,True,maxw=covernote.width-14)
            p.text(covernote.x0+9,covernote.y0+24,'Approved editorial and V7 power rankings.',7.5,STEEL,maxw=covernote.width-14)
    for i,page in enumerate(doc):
        text=page.get_text()
        if 'NOT PUBLISHED' in text or 'SHADOW' in text:
            raise ValueError(f'Aftermath page {i+1}: preview labels remain')
        if i>0:
            # Source matchup article must remain text-identical, including scores and jokes.
            before=original_text[i].split('LOG EDITORIAL SHADOW')[0].strip()
            after=text.split('LOG  /  THE AFTERMATH')[0].strip()
            if before!=after:
                raise ValueError(f'Aftermath page {i+1}: editorial text changed during release')
    return hashlib.sha256(''.join(original_text).encode()).hexdigest()


def strip_war_room_reissue_label(doc,war_week):
    """For new weekly issues, replace archival-reissue metadata only, not prose."""
    if war_week<=9:return
    for i in range(7):
        page=doc[i]
        marks=[b for b in page.get_text('blocks') if 'REISSUE' in b[4] and 'V7 POWER INDEX' in b[4]]
        if len(marks)!=1:raise ValueError('Unknown NL44 edition footer')
        b=marks[0]; W,H=page.rect.width,page.rect.height
        if b[1]<H-35:raise ValueError('War Room edition footer overlaps editorial page')
        page.add_redact_annot(fitz.Rect(max(10,b[0]-1),b[1]-2,min(W-10,b[2]+1),min(H-3,b[3]+2)),
                              fill=(1,1,1),cross_out=False)
        if i==0:
            notes=[b for b in page.get_text('blocks') if 'Archival reissue; original matchup analysis retained.' in b[4]]
            if len(notes)!=1:raise ValueError('Expected NL44 Week 10+ reissue cover note')
            n=notes[0]
            note=fitz.Rect(max(15,n[0]-3),n[1]-2,min(W-12,n[2]+4),n[3]+2)
            page.add_redact_annot(note,fill=hex_rgb('#EEEAE5'),cross_out=False)
        page.apply_redactions(images=0,graphics=0,text=0)
        pen=Pen(page)
        pen.text(20,H-12,f'LOG  /  V7 POWER INDEX  /  WEEK {war_week} EDITION',7.2,STEEL,maxw=W-35)
        if i==0:
            pen.text(note.x0+3,n[3]-1,'Approved weekly matchup analysis retained.',7.3,STEEL,maxw=note.width-6)
    if any('REISSUE' in doc[i].get_text() for i in range(7)):
        raise ValueError('Reissue labels remained in new Week 10+ issue')


def build(data, input_dir, output_dir, include_aftermath=True,mode='Preview'):
    output_dir.mkdir(parents=True,exist_ok=True)
    win=data['war_week'];prev=data['through']
    warpdf=output_dir/f'LOG-W{win:02d}-War-Room-V7-Offense-IDP-Final.pdf'
    with fitz.open(data['war_pdf']) as original:
        with fitz.open() as d:
            d.insert_pdf(original)
            strip_war_room_reissue_label(d,win)
            offense=draw_leaderboard(d,data,'War Room','offense',win,mode=='Preview')
            defense=draw_leaderboard(d,data,'War Room','idp_defense',win,mode=='Preview')
            d.save(warpdf,garbage=4,deflate=True)
            if len(d)!=11:raise ValueError('WarRoom expected 11 pages (9 original + 2 new)')
    with fitz.open(data['war_pdf']) as a,fitz.open(warpdf) as b:
        if len(b)!=len(a)+2 or (win<=9 and any(b[i].get_text()!=a[i].get_text() for i in range(len(a)))):
            raise ValueError('Original approved NL44 WarRoom pages were modified')
        if win>9:
            for i in range(7):
                original=a[i].get_text()
                revised=b[i].get_text()
                if i>0 and original!=revised and not _nl57_equal_source_articles(original, revised):
                    raise ValueError('New War Room match analysis changed')
        if any('POSITIONAL SCORING LEADERS' in p.get_text() for p in list(b)[9:]):
            raise ValueError('Removed positional scoring leaders section resurfaced')
        for title in ('OFFENSIVE POWERHOUSES','DEFENSIVE POWERHOUSES'):
            if title not in ' '.join(p.get_text() for p in list(b)[9:]):
                raise ValueError('New WarRoom appendices missing')
    outputs={'WarRoom':str(warpdf)}
    if include_aftermath:
        path=input_dir/'nl39'/f'LOG-NL39R1-Aftermath-W{prev:02d}-Weekly-Integration-Shadow.pdf'
        wsource=input_dir/'nl39'/f'LOG-NL39R1-WarRoom-W{win:02d}-Weekly-Integration-Shadow.pdf'
        if not path.is_file() or not wsource.is_file():raise ValueError('NL39 Aftermath requires exact earlier NL39 companion PDFs')
        if sha(wsource.read_bytes())!=data['nl44_evidence']['original_pdf_sha256']:
            raise ValueError('Aftermath source must match the exact NL39 War Room used by production NL44')
        out=output_dir/f'LOG-W{prev:02d}-Aftermath-V7-Offense-IDP-Final.pdf'
        with fitz.open(path) as src:
            if len(src)!=7:raise ValueError('NL39 Aftermath must have seven original pages')
            with fitz.open() as d:
                d.insert_pdf(src)
                release_aftermath_source(d,prev)
                power_rank_appendix(d,data,prev)
                draw_leaderboard(d,data,'Aftermath','offense',prev,True)
                draw_leaderboard(d,data,'Aftermath','idp_defense',prev,True)
                d.save(out,garbage=4,deflate=True)
        with fitz.open(path) as a,fitz.open(out) as b:
            if len(b)!=11:raise ValueError('Aftermath expected eleven pages')
            if any('NOT PUBLISHED' in b[i].get_text() or 'SHADOW' in b[i].get_text() for i in range(7)):
                raise ValueError('Aftermath must be share-ready without shadow marks')
            for i in range(1,7):
                old=a[i].get_text().split('LOG EDITORIAL SHADOW')[0].strip()
                new=b[i].get_text().split('LOG  /  THE AFTERMATH')[0].strip()
                if old!=new:raise ValueError('Aftermath editorial article altered during release')
            if any('POSITIONAL SCORING LEADERS' in p.get_text() for p in list(b)[9:]):
                raise ValueError('Removed positional scoring leaders section resurfaced in Aftermath')
            if 'POWER RANKINGS / V7' not in b[7].get_text() or 'OFFENSIVE POWERHOUSES' not in b[9].get_text() or 'DEFENSIVE POWERHOUSES' not in b[10].get_text():
                raise ValueError('Aftermath V7 + unit appendices missing')
        outputs['Aftermath']=str(out)
    result={'model':'V7','league_id':LEAGUE_ID,'season':2026,'war_week':win,'scored_through_week':prev,
            'offense_leader':{'team':offense[0]['team'],'points':fmt(offense[0]['points'])},
            'defense_leader':{'team':defense[0]['team'],'points':fmt(defense[0]['points'])},
            'page_policy':'NL44 WarRoom 9 approved pages plus 2 scoring pages; Aftermath 7 original editorial pages with preview metadata cleaned, plus 2 V7 pages and 2 scoring pages.',
            'source_warroom_pdf_sha256':data['nl44_pdf_sha'],
            'source_nl44_run_id':data['source_nl44_run'],'source_nl45_run_id':data['source_nl45_run'],
            'scoring_source_manifest':data['nl45_manifest'],
            'privacy_policy':'No private FA board, calculator data, or roster-scouting leaks',
            'provenance':'Exact-week NL44 and NL45 GitHub artifacts, plus exact NL39 Aftermath source; only shadow metadata cleaned',
            'outputs':{k:{'file':Path(v).name,'sha256':sha(Path(v).read_bytes())} for k,v in outputs.items()}}
    (output_dir/'NL46-VERIFIED-SOURCE-MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return outputs,result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--war-week',type=int,required=True)
    ap.add_argument('--mode',choices=('Release',),default='Release')
    ap.add_argument('--no-aftermath',action='store_true')
    ap.add_argument('--nl44-run-id',default=None)
    ap.add_argument('--nl45-run-id',default=None)
    args=ap.parse_args()
    if args.war_week not in range(2,19):raise SystemExit('War Room week must be 2-18')
    data=validate_data(args.input,args.war_week,args.nl44_run_id,args.nl45_run_id)
    outputs,manifest=build(data,args.input,args.output,not args.no_aftermath,args.mode)
    print('PASS: verified 12-team x completed week offense/IDP and exact original league scores')
    print('PASS: frozen V7 power index, original editorial paragraphs and streamlined leaderboards')
    for k,v in outputs.items():
        with fitz.open(v) as d:
            print(f'PASS: {k} {len(d)} pages, output {v}, {Path(v).stat().st_size} bytes')
    print(json.dumps({'offense_leader':manifest['offense_leader'],'defense_leader':manifest['defense_leader']},indent=2))

if __name__=='__main__':main()
