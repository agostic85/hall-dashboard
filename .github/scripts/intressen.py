"""Hämtar RSS-flöden och behåller nyheter som rör Cristophers fritidsintressen.
Resultatet skrivs till intressen.json som porträtt-dashboarden läser."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

# (namn, adress, kategori som alltid gäller eller None = måste matcha nyckelord)
SOURCES = [
    ('Bambu Lab', 'https://blog.bambulab.com/rss/', '3D'),
    ('Home Assistant', 'https://www.home-assistant.io/atom.xml', 'Hem'),
    ('Elbilen', 'https://elbilen.se/feed/', 'Elbil'),
    ('SweClockers', 'https://www.sweclockers.com/feeds/nyheter', None),
    ('Feber', 'https://feber.se/rss/', None),
    ('M3', 'https://www.m3.se/rss', None),
    ('Hackaday', 'https://hackaday.com/blog/feed/', None),
    ('The Verge', 'https://www.theverge.com/rss/index.xml', None),
    ('Electrek', 'https://electrek.co/feed/', None),
    ("Tom's Hardware", 'https://www.tomshardware.com/feeds/all', None),
]

TOPICS = [
    ('3D', r'bambu|makerworld|3d[- ]?print|3d[- ]?skrivar|3d[- ]?utskrift|snapmaker|klipper|orcaslicer|filament'),
    ('Elbil', r'\bkia\b|\bev6\b|\bev3\b|\bev9\b|ioniq|\belbil|laddbox|zaptec|\btibber'),
    ('Hem', r'home assistant|homey|smarta? hem|smart home|zigbee|\bmatter\b|philips hue|\bhue\b|aqara|sonos|dirigera|switchbot|roborock'),
    ('Dator', r'rtx ?50[6-9]0|geforce|\bnvidia\b|9800x3d|\bx3d\b|ryzen 7|librehardwaremonitor'),
    ('Ljud', r'sennheiser|hörlur|headphone|\biems?\b|\bfiio\b|truthear|airpods'),
    ('iPhone', r'iphone 17|\bios 2[6-9]\b'),
]
SKIP = re.compile(r'\b(deal|deals|discount|sale|save \$|rea|rabatt|black friday|cyber monday)\b', re.I)
MAX_AGE = timedelta(days=5)
NOW = datetime.now(timezone.utc)


def text(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or '').strip():
            return x.text.strip()
    return ''


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fetch(name, url, fixed):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (hall-dashboard intressen)'})
    with urlopen(req, timeout=25) as r:
        root = ET.fromstring(r.read())
    for el in root.iter():
        el.tag = el.tag.split('}')[-1]   # ta bort namnrymder (Atom)
    out = []
    for it in list(root.iter('item')) + list(root.iter('entry')):
        title = re.sub(r'\s+', ' ', text(it, 'title'))
        link = text(it, 'link')
        if not link:
            le = it.find('link')
            link = le.get('href', '') if le is not None else ''
        when = parse_date(text(it, 'pubDate', 'published', 'updated', 'date'))
        if not title or not link.startswith('https://') or not when or NOW - when > MAX_AGE:
            continue
        if SKIP.search(title):
            continue
        cat = fixed
        if not cat:
            hay = (title + ' ' + re.sub(r'<[^>]+>', ' ', text(it, 'description', 'summary'))[:400]).lower()
            cat = next((c for c, rx in TOPICS if re.search(rx, title.lower())), None) \
                or next((c for c, rx in TOPICS if re.search(rx, hay)), None)
        if cat:
            out.append({'t': title[:160], 'l': link, 's': name, 'c': cat, 'ts': int(when.timestamp() * 1000)})
    return out


items, errors = [], []
for name, url, fixed in SOURCES:
    try:
        items += fetch(name, url, fixed)
    except Exception as e:  # en trasig källa ska inte stoppa resten
        errors.append(f'{name}: {e.__class__.__name__}')

seen, uniq = set(), []
for x in sorted(items, key=lambda x: -x['ts']):
    k = re.sub(r'[^a-z0-9åäö]', '', x['t'].lower())[:60]
    if k not in seen:
        seen.add(k)
        uniq.append(x)

path = Path('intressen.json')
new = {'items': uniq[:30], 'errors': errors}
old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
if {k: old.get(k) for k in new} != new:
    new['updated'] = int(NOW.timestamp() * 1000)
    path.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{len(uniq)} träffar, fel: {errors}')
