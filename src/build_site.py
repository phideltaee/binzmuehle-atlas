"""Place the new Binzmühle rows on the model: measure GISA's site-plan schematic and fit it to the GWR building points.

Usage: python3 -I build_site.py <defaultetage.png> <out site.json>

Input: https://www.binzmuehle.ch/files/apartments/defaults/defaultetage.png (the Lageplan behind the unit list).
Anchor: the federal building register (GWR, api3.geo.admin.ch, layer ch.bfs.gebaeude_wohnungs_register) has one
point per row, status 1003 "im Bau" (checked 24 Oct 2026). A similarity fit (scale, rotation, shift) maps the five
row centroids of the drawing onto those points; residuals are 0.2 to 1.7 m.
Output: metres from the origin (Zelghalde 34, x = east, y = north). Pieces: 'h' = house, 'v' = open walkway
("Viadukt") between houses, 'b' = balcony towers on the garden side; plus the gaps between rows ('gasse', 'hof').
"""
import json, math, sys
from PIL import Image

LAT0, LON0 = 47.41381, 8.52935
GWR = {1: (8.530237, 47.414046), 2: (8.5297, 47.414044), 3: (8.529206, 47.41411), 4: (8.528627, 47.414187), 5: (8.528132, 47.414252)}
GWR_EGID = {1: 302067231, 2: 302067232, 3: 302067233, 4: 302067234, 5: 302067235}
KX = 111320.0 * math.cos(math.radians(LAT0)); KY = 110574.0
ROW_X = {5: (120, 230), 4: (240, 345), 3: (360, 465), 2: (480, 590), 1: (600, 690)}   # pixel columns of each row
STAGE = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2}
GAPS = [(5, 4, 'gasse', 'Binderweg'), (4, 3, 'hof', ''), (3, 2, 'gasse', 'Zelghalde'), (2, 1, 'hof', '')]


def regions(path):
    """Connected light-grey areas between the black outlines, with their most common grey."""
    im = Image.open(path).convert('RGB'); W, H = im.size; px = im.load()
    seen = [[False] * H for _ in range(W)]
    isfill = lambda c: c != (255, 255, 255) and sum(c) > 500
    out = []
    for x in range(W):
        for y in range(H):
            if seen[x][y] or not isfill(px[x, y]): continue
            st = [(x, y)]; seen[x][y] = True; pts = []
            while st:
                a, b = st.pop(); pts.append((a, b))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    u, v = a + dx, b + dy
                    if 0 <= u < W and 0 <= v < H and not seen[u][v] and isfill(px[u, v]): seen[u][v] = True; st.append((u, v))
            if len(pts) < 100: continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            cols = {}
            for p in pts: cols[px[p][0]] = cols.get(px[p][0], 0) + 1
            out.append({'x0': min(xs) - 1, 'y0': min(ys) - 1, 'x1': max(xs) + 2, 'y1': max(ys) + 2, 'n': len(pts), 'c': max(cols, key=cols.get)})
    return out


def main():
    regs = regions(sys.argv[1])
    rows = {}
    for z, (a, b) in ROW_X.items():
        rs = [r for r in regs if a <= (r['x0'] + r['x1']) / 2 < b and r['y1'] < 300]
        pieces = []
        for r in rs:
            w, h = r['x1'] - r['x0'], r['y1'] - r['y0']
            if h < 12 and w > 40: k = 'v'                            # walkway bars
            elif r['n'] < 400 and w >= 20: k = 'g'                   # garden side, drawn as an outline next to a house
            elif r['n'] > 900: k = 'h'                               # houses
            else: continue                                           # thin shading slivers
            pieces.append(dict(r, k=k))
        rows[z] = sorted(pieces, key=lambda r: r['y0'])
    def cen(z):
        hs = [r for r in rows[z] if r['k'] == 'h']
        A = sum((r['x1'] - r['x0']) * (r['y1'] - r['y0']) for r in hs)
        return complex(sum((r['x0'] + r['x1']) / 2 * (r['x1'] - r['x0']) * (r['y1'] - r['y0']) for r in hs) / A,
                       -sum((r['y0'] + r['y1']) / 2 * (r['x1'] - r['x0']) * (r['y1'] - r['y0']) for r in hs) / A)
    zs = sorted(rows)
    u = [cen(z) for z in zs]
    g = [complex((GWR[z][0] - LON0) * KX, (GWR[z][1] - LAT0) * KY) for z in zs]
    mu, mg = sum(u) / len(u), sum(g) / len(g)
    a = sum((gi - mg) * (ui - mu).conjugate() for ui, gi in zip(u, g)) / sum(abs(ui - mu) ** 2 for ui in u)
    t = mg - a * mu
    P = lambda x, y: (lambda p: [round(p.real, 2), round(p.imag, 2)])(a * complex(x, -y) + t)
    box = lambda x0, y0, x1, y1: [P(x0, y1), P(x1, y1), P(x1, y0), P(x0, y0)]   # CCW in metres
    print('scale %.4f m/px, rotation %.2f deg' % (abs(a), math.degrees(math.atan2(a.imag, a.real))))
    for z, ui, gi in zip(zs, u, g):
        print('  row', z, 'residual %.1f m' % abs(a * ui + t - gi))
    pieces = []
    for z in zs:
        hs = [r for r in rows[z] if r['k'] == 'h']
        # balcony towers ("vorgelagerte Balkontürme") on the garden side: 4.5 m wide, 4.3 m deep, about every 10 m
        bw, bd, step = 4.5 / abs(a), 4.3 / abs(a), 10.0 / abs(a)
        for g in [r for r in rows[z] if r['k'] == 'g']:
            for h in hs:
                ov = min(g['y1'], h['y1']) - max(g['y0'], h['y0'])
                if ov < 20 or not (abs(g['x0'] - h['x1']) < 4 or abs(g['x1'] - h['x0']) < 4): continue
                east = abs(g['x0'] - h['x1']) < 4
                y0, y1 = max(g['y0'], h['y0']), min(g['y1'], h['y1'])
                n = max(1, int((y1 - y0) // step))
                for k in range(n):
                    cy = y0 + (y1 - y0) * (k + 0.5) / n
                    x0, x1 = (h['x1'], h['x1'] + bd) if east else (h['x0'] - bd, h['x0'])
                    rows[z].append({'k': 'b', 'x0': x0, 'x1': x1, 'y0': cy - bw / 2, 'y1': cy + bw / 2})
        rows[z] = [r for r in rows[z] if r['k'] != 'g']
        for i, r in enumerate(rows[z]):
            rec = {'z': z, 'e': STAGE[z], 'k': r['k'], 'ring': box(r['x0'], r['y0'], r['x1'], r['y1'])}
            if r['k'] == 'h':
                # attic: set back 2 m from the long facades (the drawing's x sides), flush at the ends
                inset = 2.0 / abs(a)
                rec['attic'] = box(r['x0'] + inset, r['y0'] + inset * 0.5, r['x1'] - inset, r['y1'] - inset * 0.5)
                rec['i'] = hs.index(r)
            pieces.append(rec)
    gaps = []
    for zw, ze, kind, name in GAPS:
        xw = max(r['x1'] for r in rows[zw]); xe = min(r['x0'] for r in rows[ze])
        y0 = min(r['y0'] for r in rows[zw] + rows[ze]); y1 = max(r['y1'] for r in rows[zw] + rows[ze])
        gaps.append({'k': kind, 'name': name, 'between': [zw, ze], 'ring': box(xw + 1.5, y0, xe - 1.5, y1)})
    allp = [p for r in pieces for p in r['ring']]
    xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
    out = {'source': 'binzmuehle.ch Lageplan (defaultetage.png) fitted to GWR points ' + ', '.join(map(str, GWR_EGID.values())),
           'scale_m_per_px': round(abs(a), 4), 'rotation_deg': round(math.degrees(math.atan2(a.imag, a.real)), 2),
           'pieces': pieces, 'gaps': gaps,
           'footprint': box(min(r['x0'] for z in zs for r in rows[z]) - 6, 38, max(r['x1'] for z in zs for r in rows[z]) + 4, 300)}
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
    print('pieces', {k: sum(1 for p in pieces if p['k'] == k) for k in 'hvb'}, 'gaps', len(gaps), 'bbox x %.0f..%.0f y %.0f..%.0f' % (min(xs), max(xs), min(ys), max(ys)))


if __name__ == '__main__':
    main()
