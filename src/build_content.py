"""Merge researched places/events into the explorer's content file and route the guided walks.

Usage: python3 -I build_content.py <research_dir> <raw_dir> <out_json> [<units_json>]

research_dir: pois-family.json, pois-quartier.json, events.json, tours-suggestions.json
units_json:   the GISA unit list (../research/units-*.json) -> free 3.5/4.5 flats per row, house and floor
"""
import json, math, sys, os, time, urllib.request

LAT0, LON0 = 47.41381, 8.52935
KX = 111320.0 * math.cos(math.radians(LAT0)); KY = 110574.0
BC, R = (-60.0, 80.0), 1800.0
HOME = (47.41381, 8.52935)     # Zelghalde 34, 8046 Zürich (Nominatim), centre of Bauetappe 1


def proj(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


GROUP = {'kita': 'kita', 'kindergarten': 'school', 'school': 'school', 'playground': 'play', 'park': 'green',
         'nature': 'green', 'pool': 'sport', 'sport': 'sport', 'library': 'culture', 'culture': 'culture',
         'history': 'culture', 'landmark': 'culture', 'food': 'food', 'market': 'food', 'shop': 'food',
         'community': 'community', 'health': 'health', 'transport': 'mobility', 'sharing': 'mobility'}

# places that get a permanent label on the model, and the ones highlighted on it (set after the research landed)
FEATURED = {'kita-globegarden-huerststrasse', 'schule-kuegeliloo', 'kindergarten-kuegeliloo', 'spielplatz-louis-haefliger-park',
            'gustav-ammann-park', 'oerliker-park', 'mfo-park', 'huerstwald', 'bauspielplatz-affoltern', 'bahnhof-oerlikon',
            'market-wochenmarkt-oerlikon', 'gz-oerlikon', 'pbz-oerlikon', 'shop-center-eleven', 'elch-regensbergstrasse',
            'freibad-allenmoos', 'bahnhof-affoltern', 'zehntenhaus-quartiertreff', 'familiengaerten-nordheim',
            'spielplatz-althoos', 'quartiergarten-aphaltra', 'sport-velotrial-fronwald', 'bus-chaletweg', 'wahlenpark'}
HIGHLIGHT = {'spielplatz-louis-haefliger-park', 'bauspielplatz-affoltern'}
LINES = ('80', '64')                      # drawn on the map: the buses at Chaletweg


def merge_pois(research):
    fam = json.load(open(os.path.join(research, 'pois-family.json')))
    qua = json.load(open(os.path.join(research, 'pois-quartier.json')))
    by = {}
    for src in (fam, qua):
        for p in src:
            if p['id'] in by:
                o = by[p['id']]
                if len(str(p.get('desc_de') or '')) > len(str(o.get('desc_de') or '')):
                    o['desc_de'], o['desc_en'] = p.get('desc_de'), p.get('desc_en')   # DE and EN from the same record
                for k in ('address', 'url'):
                    if len(str(p.get(k) or '')) > len(str(o.get(k) or '')):
                        o[k] = p[k]
                o['tags'] = sorted(set(o.get('tags', [])) | set(p.get('tags', [])))
                o['details'] = {**(p.get('details') or {}), **(o.get('details') or {})}
            else:
                by[p['id']] = dict(p)
    out = []
    for p in by.values():
        if p['id'] == 'binzmuehle-siedlung':
            continue                              # the model itself shows the estate
        x, y = proj(p['lat'], p['lon'])
        g = GROUP.get(p['cat'], 'community')
        det = p.get('details') or {}
        keep = {}
        for k in ('ages', 'hours', 'opening_hours', 'price_day', 'price', 'subsidised', 'subsidized', 'labels', 'languages',
                  'operator', 'phone', 'status', 'lines', 'waitlist', 'places', 'note', 'when'):
            v = det.get(k)
            if v not in (None, '', [], {}):
                keep[k] = v if not isinstance(v, list) else ', '.join(map(str, v))
        rec = {'id': p['id'], 'n': p['name'], 'g': g, 'c': p['cat'], 'x': round(x, 1), 'y': round(y, 1),
               'w': p.get('walk_min'), 'a': p.get('address') or '', 'dd': p.get('desc_de') or '', 'de': p.get('desc_en') or '',
               'u': p.get('url') or '', 's': p.get('source') or '', 't': [t for t in (p.get('tags') or [])][:8]}
        if keep:
            rec['d'] = keep
        if p.get('approx'):
            rec['ap'] = 1
        if p['id'] in FEATURED:
            rec['f'] = 1
        if p['id'] in HIGHLIGHT:
            rec['hl'] = 1
        if math.hypot(x - BC[0], y - BC[1]) > R - 25:
            rec['out'] = 1
        out.append(rec)
    out.sort(key=lambda r: (r['w'] if r['w'] is not None else 999))
    return out


def events(research):
    ev = json.load(open(os.path.join(research, 'events.json')))
    out = []
    for e in ev:
        rec = {'id': e['id'], 'n': e['name'], 'r': e['recurrence'], 'wd': e.get('when_de') or '', 'we': e.get('when_en') or '',
               'ds': e.get('date_start'), 'dz': e.get('date_end'), 'm': e.get('month'), 'v': e.get('venue') or '',
               'dd': e.get('desc_de') or '', 'de': e.get('desc_en') or '', 'fam': bool(e.get('family_friendly')),
               'u': e.get('url') or ''}
        if e.get('lat') and e.get('lon'):
            x, y = proj(e['lat'], e['lon']); rec['x'] = round(x, 1); rec['y'] = round(y, 1)
        out.append(rec)
    return out


def osrm(a, b, prof='foot'):
    url = (f"https://routing.openstreetmap.de/routed-{prof}/route/v1/{prof}/{a[1]},{a[0]};{b[1]},{b[0]}"
           f"?overview=full&geometries=geojson")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'binzmuehle-atlas/1.0'})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.load(r)
            rt = d['routes'][0]
            return rt['geometry']['coordinates'], rt['distance'], rt['duration']
        except Exception as ex:
            print('osrm retry', attempt, ex); time.sleep(2 + attempt * 2)
    raise RuntimeError('osrm failed')


def bus_line(raw, ref, start, end):
    """Slice a bus route (OSM route relation with this ref, the longest variant) between two points."""
    d = json.load(open(os.path.join(raw, 'routes_geom.json')))
    rels = [e for e in d['elements'] if e.get('tags', {}).get('ref') == ref and e.get('members')]
    rel = max(rels, key=lambda e: sum(len(m.get('geometry') or []) for m in e['members']))
    ways = [[(p['lat'], p['lon']) for p in m['geometry']] for m in rel['members'] if m['type'] == 'way' and m.get('geometry') and m.get('role', '') in ('', 'forward', 'backward')]
    line = list(ways[0])
    for w in ways[1:]:
        if line[-1] == w[0]: line += w[1:]
        elif line[-1] == w[-1]: line += w[::-1][1:]
        elif line[0] == w[-1] and len(line) == len(ways[0]): line = w[:-1] + line
        elif line[0] == w[0] and len(line) == len(ways[0]): line = w[::-1][:-1] + line
        else:
            da = (line[-1][0] - w[0][0]) ** 2 + (line[-1][1] - w[0][1]) ** 2
            db = (line[-1][0] - w[-1][0]) ** 2 + (line[-1][1] - w[-1][1]) ** 2
            line += w if da <= db else w[::-1]
    def near(pt):
        return min(range(len(line)), key=lambda i: (line[i][0] - pt[0]) ** 2 + ((line[i][1] - pt[1]) * 0.68) ** 2)
    i, j = near(start), near(end)
    seg = line[i:j + 1] if i <= j else line[j:i + 1][::-1]
    return [[lon, lat] for lat, lon in seg]


def to_xy(coords):
    pts = []
    for lon, lat in coords:
        x, y = proj(lat, lon)
        if not pts or math.hypot(x - pts[-1][0], y - pts[-1][1]) > 1.5:
            pts.append([round(x, 1), round(y, 1)])
    return pts


def load_tours(research):
    """Guided walks from tours-suggestions.json. A bus leg may name its line ("line": "80"; default 80) and minutes."""
    return json.load(open(os.path.join(research, 'tours-suggestions.json')))


def build_tours(pois, raw, tours):
    byid = {p['id']: p for p in pois}
    def latlon(pid):
        if pid == '@home':
            return HOME
        p = byid[pid]
        return (LAT0 + p['y'] / KY, LON0 + p['x'] / KX)
    out = []
    for t in tours:
        cur = HOME; legs = []; total_d = total_t = 0
        for leg in t['legs']:
            nxt = latlon(leg['to'])
            if leg['mode'] == 'bus':
                # the line and ride time come from the leg ("line", "min") or its text ("Bus 61 …", "3 Min.")
                import re
                txt = leg.get('de', '') + ' ' + leg.get('en', '')
                line = str(leg.get('line') or (re.findall(r'Bus (\w+)', txt) or ['80'])[0])
                mins = int(leg.get('min') or (re.findall(r'(\d+) Min\.', txt) or [5])[-1])
                coords = bus_line(raw, line, cur, nxt); d = 0; dur = mins * 60
                for a, b in zip(coords, coords[1:]):
                    d += math.hypot((b[0] - a[0]) * KX, (b[1] - a[1]) * KY)
            else:
                coords, d, dur = osrm(cur, nxt); time.sleep(1.1)
            pts = to_xy(coords)
            legs.append({'mode': leg['mode'], 'to': leg['to'], 'de': leg.get('de', ''), 'en': leg.get('en', ''), 'p': pts,
                         'dist': round(d), 'min': round(dur / 60) if leg['mode'] == 'bus' else max(1, round(d / 75))})
            total_d += d; total_t += legs[-1]['min']
            cur = nxt
        rec = {k: v for k, v in t.items() if k != 'legs'}
        rec['legs'] = legs; rec['dist'] = round(total_d); rec['min'] = total_t
        out.append(rec)
        print(t['id'], round(total_d), 'm', total_t, 'min', [l['min'] for l in legs])
    return out


def transit_lines(raw):
    d = json.load(open(os.path.join(raw, 'routes_geom.json')))
    lines, done = [], set()
    for e in sorted(d['elements'], key=lambda e: -sum(len(m.get('geometry') or []) for m in e.get('members', []))):
        if not e.get('members'):
            continue                              # tag-only answer of the "which lines stop here" query
        ref = e['tags'].get('ref'); kind = e['tags'].get('route')
        if ref in done or ref not in LINES:
            continue                              # one direction per line is enough on the map
        done.add(ref)
        segs = []
        for m in e['members']:
            if m['type'] == 'way' and m.get('geometry') and m.get('role', '') in ('', 'forward', 'backward'):
                pts = to_xy([[p['lon'], p['lat']] for p in m['geometry']])
                pts = [p for p in pts if math.hypot(p[0] - BC[0], p[1] - BC[1]) < R - 5]
                if len(pts) >= 2:
                    segs.append(pts)
        lines.append({'ref': ref, 'kind': kind, 'segs': segs})
        print('line', kind, ref, len(segs))
    return lines


LEVEL = {'EG': [0], 'EG/1.OG': [0, 1], '1.OG': [1], '2.OG': [2], '3.OG': [3], 'DG': [4]}


def units(path):
    """Free 3.5 and 4.5 flats per row: by house (free/total, cheapest gross rent) and by floor level."""
    us = json.load(open(path))['units']
    out = {}
    for z in (1, 2, 3):
        row = [u for u in us if u['zeile'] == f'Zeile {z}' and u['type'] == 'Wohnung']
        houses = []
        for a in sorted({u['address'] for u in row}, key=lambda a: int(a.split()[-1])):
            hs = [u for u in row if u['address'] == a]
            rec = {'a': a}
            for r, k in (('3.5', '35'), ('4.5', '45')):
                rec['t' + k] = sum(1 for u in hs if u['rooms'] == r)
                rec['f' + k] = sum(1 for u in hs if u['rooms'] == r and u['status'] == 'Frei')
            free = [u['gross'] for u in hs if u['rooms'] in ('3.5', '4.5') and u['status'] == 'Frei']
            rec['min'] = min(free) if free else None
            houses.append(rec)
        levels = [[0, 0] for _ in range(5)]
        for u in row:
            if u['status'] != 'Frei' or u['rooms'] not in ('3.5', '4.5'):
                continue
            for lv in LEVEL.get(u['floor'], []):
                levels[lv][0 if u['rooms'] == '3.5' else 1] += 1
        out['z%d' % z] = {'houses': houses, 'levels': levels}
    return out


def main():
    research, raw, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pois = merge_pois(research)
    ev = events(research)
    tours = build_tours(pois, raw, load_tours(research))
    lines = transit_lines(raw)
    home = proj(*HOME)
    data = {'home': [round(home[0], 1), round(home[1], 1)], 'pois': pois, 'events': ev, 'tours': tours, 'lines': lines}
    if len(sys.argv) > 4:
        data['units'] = units(sys.argv[4])
    s = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    open(out, 'w').write(s)
    from collections import Counter
    print('pois', len(pois), Counter(p['g'] for p in pois), 'outside board', sum(1 for p in pois if p.get('out')))
    print('events', len(ev), 'wrote', out, round(len(s) / 1024), 'KB')


if __name__ == '__main__':
    main()
