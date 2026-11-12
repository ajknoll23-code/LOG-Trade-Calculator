#!/usr/bin/env python3
"""LOG NL62: render verified approval payload into 11-page PDFs.

Modes:
  approved_pages: copy user-approved seven editorial and four appendix pages;
                  no text is regenerated (current-week exact release adapter).
  json_reflow:   draw new cover and six matchup pages solely from approved
                  headline/story/verdict JSON, plus verified appendix pages.

This module does not authorize, email, or publish a release.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import fitz

BASE=Path('/usr/share/fonts/truetype/dejavu')
FONT=str(BASE/'DejaVuSans.ttf')
BOLD=str(BASE/'DejaVuSans-Bold.ttf')
W,H=306.142,691.654
INK=(.095,.21,.29); NAVY=(.06,.18,.28); ACCENT=(.69,.37,.31)
PAPER=(.989,.98,.963); LIGHT=(.94,.95,.95); MUTED=(.35,.44,.49)

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def verify_pdf_pages(actual:Path,approved:Path,indices=range(11)):
    """Raster and text parity (for trusted approved-page adapters)."""
    with fitz.open(actual) as a, fitz.open(approved) as b:
        if len(a)!=11 or len(b)!=11:raise RuntimeError('Expected 11 pages for parity')
        for idx in indices:
            if a[idx].get_text()!=b[idx].get_text():raise RuntimeError(f'Approved page {idx+1} text changed')
            if a[idx].rect!=b[idx].rect:raise RuntimeError(f'Approved page {idx+1} geometry changed')
            p=a[idx].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
            q=b[idx].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
            if (p.width,p.height,p.samples)!=(q.width,q.height,q.samples):
                raise RuntimeError(f'Approved page {idx+1} visual changed')
    return True

def approved_pages(approved:Path,out:Path):
    with fitz.open(approved) as source,fitz.open() as d:
        if len(source)!=11:raise ValueError('Approved PDF must have 11 pages')
        d.insert_pdf(source)
        d.save(out,garbage=4,deflate=True)
    verify_pdf_pages(out,approved)

def font(doc:fitz.Document,p:fitz.Page):
    p.insert_font(fontname='logbody',fontfile=FONT)
    p.insert_font(fontname='logbold',fontfile=BOLD)

def width(text,size,bold=False):
    f=fitz.Font(fontfile=BOLD if bold else FONT)
    return f.text_length(text,fontsize=size)

def wrap(s,size,maxwidth,bold=False):
    """Lossless word reflow with no hyphenation."""
    lines=[]
    for par in re.split(r'\n+',s.strip()):
        words=par.split();cur=''
        for word in words:
            if width(word,size,bold)>maxwidth+0.001:
                raise ValueError('Unbreakable overwide word: '+word[:35])
            nxt=(cur+' '+word).strip()
            if cur and width(nxt,size,bold)>maxwidth:
                lines.append(cur);cur=word
            else:cur=nxt
        if cur:lines.append(cur)
    return lines

def drawlines(page,lines,x,y,size,leading,bold=False,color=INK):
    for line in lines:
        page.insert_text((x,y),line,fontname='logbold' if bold else 'logbody',fontsize=size,color=color)
        y+=leading
    return y

def pagebase(d,edition,week,n):
    page=d.new_page(width=W,height=H);font(d,page)
    page.draw_rect(fitz.Rect(0,0,W,H),fill=PAPER,color=None)
    page.draw_rect(fitz.Rect(0,0,W,52),fill=NAVY,color=None)
    page.draw_rect(fitz.Rect(0,51,W,54),fill=ACCENT,color=None)
    page.insert_text((17,21),'LEAGUE OF ORDINARY GENTLEMEN',fontname='logbold',fontsize=7.3,color=(.95,.90,.84))
    marker='WAR ROOM' if edition=='War Room' else 'AFTERMATH'
    page.insert_text((17,39),f'THE {marker} / W{week}',fontname='logbold',fontsize=9.1,color=(1,1,1))
    page.insert_text((17,H-15),f'LOG / {marker} / WEEK {week} / PAGE {n}',fontname='logbody',fontsize=7.2,color=MUTED)
    return page

def render_cover(d,issue,metadata):
    edition=issue['edition'];week=issue['week'];page=pagebase(d,edition,week,1)
    title='THE WEEKLY WAR ROOM' if edition=='War Room' else 'THE AFTERMATH'
    page.insert_text((18,92),title,fontname='logbold',fontsize=17.5,color=INK)
    page.insert_text((18,111),'SIX MATCHUPS / SIX ORIGINAL EDITORIAL CALLS',fontname='logbody',fontsize=8.3,color=ACCENT)
    page.insert_text((18,140),'THE MATCHUP INDEX',fontname='logbold',fontsize=10,color=INK)
    y=169
    for i,article in enumerate(issue['articles']):
        heading=wrap(article['headline'],10.8,W-57,True)
        teams=wrap(metadata[i]['teams'],8.5,W-64)
        height=19+len(heading)*13+len(teams)*11+7
        if y+height>H-65:raise ValueError('Cover index overflow')
        page.draw_line((18,y-8),(W-18,y-8),color=(.79,.82,.82),width=.55)
        page.insert_text((19,y+2),f'{i+1:02d}',fontname='logbold',fontsize=10,color=ACCENT)
        yy=drawlines(page,heading,44,y+2,10.8,13,True,INK)
        drawlines(page,teams,44,yy+1,8.5,11,False,MUTED)
        y+=height
    if y>H-65:raise ValueError('Cover overflows')
    page.insert_text((18,H-37),'Verified source data. Original writing. No private FA board.',fontname='logbody',fontsize=7.1,color=MUTED)

def render_article(d,issue,article,meta):
    num=article['number'];kind=issue['edition'];week=issue['week']
    p=pagebase(d,kind,week,num+1)
    p.insert_text((18,70),f'MATCHUP {num:02d} / 06',fontname='logbold',fontsize=8.1,color=ACCENT)
    p.insert_text((18,82),f'{"WAR ROOM" if kind=="War Room" else "AFTERMATH"} / WEEK {week}',fontname='logbold',fontsize=7.4,color=MUTED)
    headline=article['headline'];story=article['story'];verdict=article['verdict'];teams=meta['teams']
    if not re.search(r'\bvs\.?\b',teams,re.I):raise ValueError('Team names must have vs. separator')
    # Choose largest safe headline/body sizes while keeping verdict, source and footer clear.
    layout=None
    for hsz in (17.1,16.2,15.3):
        for bsz in (10.5,10.2,9.8,9.5):
            hs=wrap(headline,hsz,W-36,True)
            ts=wrap(teams,10.4,W-36,True)
            st=wrap(story,bsz,W-38)
            vsz=11.0
            vs=wrap(verdict,vsz,W-49,True)
            ss=wrap(meta['source'],7.0,W-36)
            # Every text line is inserted in reading order for NL59 extraction.
            y=105+len(hs)*21+7+len(ts)*14+27
            end=y+len(st)*(bsz*1.41)+27+len(vs)*15+25+len(ss)*9.3
            if end<H-30:layout=(hsz,bsz,hs,ts,st,vs,ss);break
        if layout:break
    if layout is None:raise ValueError(f'Matchup {num}: article does not fit one page at readable sizes')
    hsz,bsz,hs,ts,st,vs,ss=layout
    y=drawlines(p,hs,18,105,hsz,21,True,INK)+7
    y=drawlines(p,ts,18,y,10.4,14,True,INK)+7
    p.draw_line((18,y),(W-18,y),color=ACCENT,width=1.5)
    y+=18
    section='THE STAKES' if kind=='War Room' else 'WHAT HAPPENED'
    p.insert_text((18,y),section,fontname='logbold',fontsize=8.0,color=ACCENT)
    y+=19
    y=drawlines(p,st,19,y,bsz,bsz*1.41,False,INK)+11
    p.draw_line((18,y-8),(W-18,y-8),color=(.80,.84,.85),width=.55)
    sec2='MY PICK & FINAL WORD' if kind=='War Room' else 'THE FINAL VERDICT'
    p.insert_text((18,y+6),sec2,fontname='logbold',fontsize=8.0,color=ACCENT)
    y+=27
    y=drawlines(p,vs,22,y,11,15,True,INK)+8
    p.draw_line((18,y),(W-18,y),color=(.82,.84,.84),width=.55)
    y+=12
    # Starts with SOURCE to meet the canonical NL59 source integrity check.
    drawlines(p,ss,18,y,7.0,9.3,False,MUTED)
    if y+len(ss)*9.3>H-30:raise ValueError('Source overlaps footer')

def json_reflow(issue,meta,approved:Path,out:Path):
    with fitz.open(approved) as source,fitz.open() as d:
        if len(source)!=11:raise ValueError('Approved appendix source must be 11 pages')
        render_cover(d,issue,meta)
        for a,m in zip(issue['articles'],meta):render_article(d,issue,a,m)
        d.insert_pdf(source,from_page=7,to_page=10)
        if len(d)!=11:raise RuntimeError('Rendered edition does not have 11 pages')
        d.save(out,garbage=4,deflate=True)
    verify_pdf_pages(out,approved,range(7,11))
