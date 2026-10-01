import json
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse

MONTHS = {
    "january":1, "february":2, "march":3, "april":4, "may":5, "june":6,
    "july":7, "august":8, "september":9, "october":10, "november":11, "december":12,
    "jan":1, "feb":2, "mar":3, "apr":4, "jun":6, "jul":7, "aug":8,
    "sep":9, "sept":9, "oct":10, "nov":11, "dec":12,
}
WALL_MARKERS = (
    "subscribe to continue",
    "subscription required",
    "sign in to continue",
    "login to continue",
    "join premium now",
    "this content is for subscribers",
)
DERIVATIVE_MARKERS = (
    "derived from another mock",
    "derived from consensus",
    "consensus mock product",
    "syndicated from",
    "reposted from",
)

class Probe(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts=[]
        self.text_parts=[]
        self.meta=[]
        self.canonical=None
        self.jsonld_parts=[]
        self.in_title=False
        self.in_jsonld=False
        self.time_values=[]
        self.slot_numbers=set()
        self.in_td=False
        self.td_parts=[]

    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        d={str(k).lower(): ("" if v is None else str(v)) for k,v in attrs}
        if tag=="title":
            self.in_title=True
        if tag=="script" and d.get("type","").lower()=="application/ld+json":
            self.in_jsonld=True
        if tag=="meta":
            self.meta.append(d)
        if tag=="link" and "canonical" in d.get("rel","").lower():
            self.canonical=d.get("href") or self.canonical
        if tag=="time" and d.get("datetime"):
            self.time_values.append(d["datetime"])
        if tag=="li" and d.get("value","").isdigit():
            n=int(d["value"])
            if 1 <= n <= 99:
                self.slot_numbers.add(n)
        if tag=="td":
            self.in_td=True
            self.td_parts=[]

    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag=="title":
            self.in_title=False
        if tag=="script" and self.in_jsonld:
            self.in_jsonld=False
        if tag=="td" and self.in_td:
            t=re.sub(r"\s+"," ","".join(self.td_parts)).strip()
            if re.fullmatch(r"\d{1,2}",t):
                n=int(t)
                if 1 <= n <= 99:
                    self.slot_numbers.add(n)
            self.in_td=False
            self.td_parts=[]

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)
            return
        if self.in_td:
            self.td_parts.append(data)
        s=re.sub(r"\s+"," ",data).strip()
        if s:
            self.text_parts.append(s)

def _walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)

def _iso_date(value):
    if not value:
        return None
    m=re.match(r"^(\d{4})-(\d{2})-(\d{2})",str(value))
    if not m:
        return None
    try:
        return date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:
        return None

def analyze_html(raw, k, allowed_domains):
    p=Probe()
    p.feed(raw)
    title=re.sub(r"\s+"," ","".join(p.title_parts)).strip()
    text="\n".join(p.text_parts)
    low=text.lower()
    author=None
    found_date=None

    for d in p.meta:
        key=(d.get("name") or d.get("property") or "").lower()
        value=d.get("content","").strip()
        if key=="author" and value and author is None:
            author=value
        if key in {"article:published_time","article:modified_time","date","datepublished"} and found_date is None:
            found_date=_iso_date(value) or found_date

    for raw_json in p.jsonld_parts:
        try:
            obj=json.loads(raw_json)
        except Exception:
            continue
        for node in _walk_json(obj):
            a=node.get("author")
            if author is None:
                if isinstance(a,dict) and isinstance(a.get("name"),str) and a["name"].strip():
                    author=a["name"].strip()
                elif isinstance(a,str) and a.strip():
                    author=a.strip()
            if found_date is None:
                found_date=_iso_date(node.get("datePublished")) or _iso_date(node.get("dateModified"))

    if author is None:
        m=re.search(r"(?:^|\n)By\s+([A-Z][A-Za-z .'-]{1,80})(?:$|\n)",text,re.I)
        if m:
            author=m.group(1).strip()

    if found_date is None:
        for v in p.time_values:
            found_date=_iso_date(v)
            if found_date:
                break

    if found_date is None:
        m=re.search(
            r"\b(?:Updated|Last update:?)\s+"
            r"(January|February|March|April|May|June|July|August|September|October|November|December|"
            r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+"
            r"(\d{1,2}),?\s+(\d{4})\b", text, re.I
        )
        if m:
            mm=MONTHS[m.group(1).lower()]
            try:
                found_date=date(int(m.group(3)),mm,int(m.group(2))).isoformat()
            except ValueError:
                pass

    domain=None
    if p.canonical:
        domain=(urlparse(p.canonical).hostname or "").lower()
        if domain.startswith("www."):
            domain=domain[4:]
    allowed={x.lower() for x in allowed_domains}
    domain_allowed=bool(domain and any(domain==d or domain.endswith("."+d) for d in allowed))

    title_low=title.lower()
    mock_type=("nfl mock draft" in title_low and "big board" not in title_low and "prospect rankings" not in title_low)
    wall=any(x in low for x in WALL_MARKERS)
    derivative=any(x in low for x in DERIVATIVE_MARKERS)

    slots=set(p.slot_numbers)
    for line in text.splitlines():
        t=line.strip()
        for pat in (
            r"^(?:No\.?\s*)?(\d{1,2})\s*[\.\):\-]\s*",
            r"^Pick\s*#?\s*(\d{1,2})\b",
        ):
            m=re.search(pat,t,re.I)
            if m:
                n=int(m.group(1))
                if 1 <= n <= 99:
                    slots.add(n)

    coverage=set(range(1,int(k)+1)).issubset(slots)
    checks={
        "author_present":bool(author),
        "date_present":bool(found_date),
        "domain_allowed":domain_allowed,
        "mock_type":mock_type,
        "no_access_wall":not wall,
        "non_derivative":not derivative,
        "slot_coverage":coverage,
    }
    return {
        "passed":all(checks.values()),
        "checks":checks,
        "author":author,
        "publication_date":found_date,
        "canonical_domain":domain,
        "slot_count_through_k":sum(1 for n in slots if 1 <= n <= int(k)),
        "max_slot_detected":max(slots) if slots else None,
    }

def independent_pair(a,b):
    return (
        str(a.get("publisher_domain","")).strip().lower()
        != str(b.get("publisher_domain","")).strip().lower()
        and str(a.get("author","")).strip().casefold()
        != str(b.get("author","")).strip().casefold()
    )

def in_anchor_window(publication_iso, anchor_iso, days=8):
    p=date.fromisoformat(publication_iso)
    a=date.fromisoformat(anchor_iso)
    return abs((p-a).days) <= int(days)
