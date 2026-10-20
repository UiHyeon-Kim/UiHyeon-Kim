"""Anonymous public calendar collection and MIT-derived calendar-only renderer.

Normal-mode geometry ported from yoshi389111/github-profile-3d-contrib
e235d118909be71eb7edb05482a3de4e76156df3, src/create-3d-contrib.ts.
Copyright (c) 2021 SATO, Yoshiyuki. MIT license retained in ../third_party/github-profile-3d-contrib-LICENSE.
Changes: stdlib Python, anonymous HTML input, calendar-only blue-gray frame,
explicit UTC snapshot date, per-day provenance, vertical projection scaling.
No environment, credential, GitHub GraphQL, package install or subprocess access.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UPSTREAM = 'e235d118909be71eb7edb05482a3de4e76156df3'
PALETTE = ['#E3EBF1', '#B8CEDB', '#8DAFC2', '#628DA5', '#385F79']


class DataError(ValueError):
    pass


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = {}
        self.tooltips = {}
        self.active = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and attrs.get('data-date') and attrs.get('id'):
            if attrs['id'] in self.cells:
                raise DataError('Duplicate calendar cell')
            self.cells[attrs['id']] = (attrs['data-date'], int(attrs['data-level']))
        if tag == 'tool-tip':
            self.active = attrs.get('for')
            self.parts = []

    def handle_data(self, text):
        if self.active:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.active:
            self.tooltips[self.active] = ' '.join(''.join(self.parts).split())
            self.active = None

    def days(self):
        result = {}
        for key, (day, level) in self.cells.items():
            text = self.tooltips.get(key, '')
            if re.match(r'^No contributions\b', text):
                count = 0
            else:
                m = re.match(r'^([\d,]+) contributions?\b', text)
                if not m:
                    raise DataError('Calendar count tooltip missing or unsupported')
                count = int(m.group(1).replace(',', ''))
            if day in result:
                raise DataError('Duplicate calendar date')
            result[day] = {'date': day, 'count': count, 'level': level}
        return result


def validate_days(days, end):
    start = end - timedelta(days=364)
    expected = [(start + timedelta(days=i)).isoformat() for i in range(365)]
    if len(days) != 365 or [d.get('date') for d in days] != expected:
        raise DataError('Need exactly 365 unique consecutive observed dates')
    for d in days:
        if type(d.get('count')) is not int or d['count'] < 0:
            raise DataError('Invalid count')
        if type(d.get('level')) is not int or not 0 <= d['level'] <= 4:
            raise DataError('Invalid level')
        if (d['count'] == 0) != (d['level'] == 0):
            raise DataError('Count and contribution level disagree')
    return days


def collect(user, end, proof_dir=None):
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', user):
        raise DataError('Invalid username')
    start = end - timedelta(days=364)
    merged, sources = {}, []
    for year in range(start.year, end.year + 1):
        url = 'https://github.com/users/%s/contributions?%s' % (user, urlencode({
            'from': '%s-01-01' % year, 'to': '%s-12-31' % year}))
        # Deliberately anonymous: no token, environment, cookie jar or browser session.
        with urlopen(Request(url, headers={'User-Agent': 'UiHyeon-contribution-widget/1.0',
                                         'Accept-Language': 'en-US'}), timeout=30) as resp:
            if resp.status != 200:
                raise DataError('Calendar HTTP response is not 200')
            body = resp.read()
            sources.append({'url': url, 'http_status': resp.status,
                            'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
                            'sha256': hashlib.sha256(body).hexdigest()})
        if proof_dir:
            proof_dir.mkdir(parents=True, exist_ok=True)
            (proof_dir / ('calendar-%d.html' % year)).write_bytes(body)
        parser = CalendarParser()
        parser.feed(body.decode('utf-8'))
        year_days = parser.days()
        if not year_days:
            raise DataError('No observed calendar cells')
        merged.update(year_days)
    # Never invent missing days or coerce missing data to zero.
    wanted = [(start + timedelta(days=i)).isoformat() for i in range(365)]
    if any(k not in merged for k in wanted):
        raise DataError('Incomplete public calendar; outputs not replaced')
    days = validate_days([merged[k] for k in wanted], end)
    return {'username': user, 'from': start.isoformat(), 'to': end.isoformat(),
            'fetched_at_utc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
            'scope': 'Counts visible on the anonymous public GitHub profile calendar; anonymous private aggregates may be included',
            'upstream_commit': UPSTREAM, 'days': days}


def geometry(days, width=900, height=600):
    # The upstream normal-mode 30-degree grid and logarithmic bar height.
    first = date.fromisoformat(days[0]['date'])
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = math.ceil((len(days) + (first.weekday() + 1) % 7) / 7)
    dx = width / 64
    dy = dx * math.tan(math.pi / 6)
    dxx, dyy = dx * .9, dy * .9
    out = []
    for d in days:
        when = date.fromisoformat(d['date'])
        week = (when - sunday).days // 7
        dow = (when.weekday() + 1) % 7
        x = dx * 7 + (week - dow) * dx
        base_y = height - (weeks + 7) * dy + (week + dow) * dy
        bar_h = math.log10(d['count'] / 20 + 1) * 144 + 3
        out.append((d, x, base_y - bar_h, dxx, dyy, bar_h))
    return out


def darker(color, exponent):
    rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
    # d3-color's darker(k) multiplies RGB channels by 0.7**k.
    return '#'+''.join('%02x' % math.floor(c * .7**exponent + .5) for c in rgb)


def render(data):
    validate_days(data['days'], date.fromisoformat(data['to']))
    bars = geometry(data['days'])
    projection_y = .62  # Display-only flattening for a wide calendar; counts unchanged.
    points = []
    for _, x, y, a, b, h in bars:
        points += [(x, y * projection_y), (x+a, (y-b)*projection_y),
                   (x+2*a, y*projection_y), (x+a, (y+b+h)*projection_y)]
    min_x, max_x = min(x for x,y in points), max(x for x,y in points)
    min_y, max_y = min(y for x,y in points), max(y for x,y in points)
    scale = min(828/(max_x-min_x), 280/(max_y-min_y))
    tx = (900 - (max_x-min_x)*scale)/2 - min_x*scale
    ty = 82 + (280-(max_y-min_y)*scale)/2 - min_y*scale
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="414" viewBox="0 0 900 414" role="img" aria-labelledby="title desc">',
             '<title id="title">%s public contribution calendar</title>' % escape(data['username']),
             '<desc id="desc">365 observed daily cells, %s to %s. Automatically refreshed from the public profile calendar at %s. MIT-derived calendar-only geometry, no language, radar or total panel.</desc>' % (data['from'],data['to'],escape(data['fetched_at_utc'])),
             '<rect x=".5" y=".5" width="899" height="413" rx="12" fill="#F5F8FB" stroke="#D9E3EC"/>',
             '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">',
             '<text x="28" y="35" fill="#38576D" font-size="19" font-weight="600">Contribution skyline</text>',
             '<text x="28" y="58" fill="#748796" font-size="12">%s · %s - %s</text>' % (escape(data['username']),data['from'],data['to']),
             '<g id="calendar" transform="translate(%.4f %.4f) scale(%.6f %.6f)">' % (tx,ty,scale,scale*projection_y)]
    for d, x, y, a, b, h in bars:
        color = PALETTE[d['level']]
        parts.append('<g data-date="%s" data-count="%d" data-level="%d" transform="translate(%.4f %.4f)"><title>%s: %d contributions</title>' % (d['date'],d['count'],d['level'],x,y,d['date'],d['count']))
        faces = [([(0,0),(a,b),(a,b+h),(0,h)],darker(color,.5)),
                 ([(a,b),(2*a,0),(2*a,h),(a,b+h)],darker(color,1)),
                 ([(0,0),(a,-b),(2*a,0),(a,b)],color)]
        for poly, fill in faces:
            parts.append('<polygon points="%s" fill="%s"/>' % (' '.join('%.4f,%.4f'%q for q in poly),fill))
        parts.append('</g>')
    parts.append('</g><text x="28" y="387" fill="#748796" font-size="11">Less</text>')
    for i,c in enumerate(PALETTE):
        parts.append('<rect x="%d" y="377" width="11" height="11" rx="2" fill="%s"/>'%(60+i*16,c))
    parts.append('<text x="145" y="387" fill="#748796" font-size="11">More</text><text x="872" y="387" text-anchor="end" fill="#748796" font-size="11">Updated %s UTC</text></g></svg>' % escape(data['fetched_at_utc'][:16].replace('T',' ')))
    return '\n'.join(parts)+'\n'


def atomic_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        f.write(body)
        temp = Path(f.name)
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default='UiHyeon-Kim')
    parser.add_argument('--today', type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data-output', type=Path, required=True)
    parser.add_argument('--proof-dir', type=Path)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text()) if args.snapshot else collect(args.username,args.today,args.proof_dir)
    if data['username'] != args.username:
        raise DataError('Snapshot belongs to a different user')
    svg = render(data)
    # All collection and validation must pass before replacing either output.
    atomic_write(args.output, svg)
    atomic_write(args.data_output, json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'username':data['username'],'days':len(data['days']),'from':data['from'],'to':data['to'],'fetched_at_utc':data['fetched_at_utc'],'total_for_verification_only':sum(d['count'] for d in data['days']),'max_daily_count':max(d['count'] for d in data['days'])}))


if __name__ == '__main__':
    main()
