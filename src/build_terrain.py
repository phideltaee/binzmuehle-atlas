"""Fetch a terrain height grid for the model board from swisstopo and write a compact terrain file for the 3D atlas.

Usage: python3 -I build_terrain.py <scene_json> <out_json> [--cache <dir>] [--step <metres>]

Source: swissALTI3D, the swisstopo terrain model (bare ground: no buildings, no trees), read through the free
profile service api3.geo.admin.ch/rest/services/profile.json: one call per grid row with a short pause, every
row cached in <cache> (default ~/Library/Caches/binzmuehle-atlas/terrain), so a rerun is offline. © swisstopo.

The grid is laid out in the scene's own metres (build_geo.py: equirectangular around the scene origin, x = east,
y = north), so it lines up with the buildings and streets: each row is a line of constant y in model metres, its
two ends are converted to LV95 with the swisstopo approximate formulas, and the service samples the line evenly.
The returned points are converted back and checked against the grid (the report prints the largest offset).

Output: {"src", "x0", "y0", "d", "nx", "ny", "u", "z0", "date", "rows"} (date: when the rows were fetched). Heights are relative to the ground at the scene
origin (Zelghalde 34, z0 metres above sea level) in units of u metres. Only the part of each row over the board
(plus one cell) is stored: rows[j] = [i0, first value, delta, delta, ...] for grid points i0, i0 + 1, ...
"""
import json, math, os, sys, time, urllib.request, urllib.parse

STEP = 15.0                      # grid spacing, metres
UNIT = 0.1                       # height unit in the file, metres
API = 'https://api3.geo.admin.ch/rest/services/'
UA = {'User-Agent': 'binzmuehle-quartier-atlas/1.0 (terrain grid for a neighbourhood model; one call per row)'}


def wgs_to_lv95(lat, lon):
    """swisstopo approximate formulas (accuracy about 1 m)."""
    p = (lat * 3600 - 169028.66) / 10000
    l = (lon * 3600 - 26782.5) / 10000
    e = 2600072.37 + 211455.93 * l - 10938.51 * l * p - 0.36 * l * p * p - 44.54 * l ** 3
    n = 1200147.07 + 308807.95 * p + 3745.25 * l * l + 76.63 * p * p - 194.56 * l * l * p + 119.79 * p ** 3
    return e, n


def lv95_to_wgs(e, n):
    y = (e - 2600000) / 1e6
    x = (n - 1200000) / 1e6
    lam = 2.6779094 + 4.728982 * y + 0.791484 * y * x + 0.1306 * y * x * x - 0.0436 * y ** 3
    phi = 16.9023892 + 3.238272 * x - 0.270978 * y * y - 0.002528 * x * x - 0.0447 * y * y * x - 0.0140 * x ** 3
    return phi * 100 / 36, lam * 100 / 36


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as ex:   # network hiccup or rate limit: wait and retry
            if k == tries - 1:
                raise
            print('  retry after', ex)
            time.sleep(3 * (k + 1))


def main():
    args = sys.argv[1:]
    scene_path, out_path = args[0], args[1]
    cache = os.path.expanduser(args[args.index('--cache') + 1]) if '--cache' in args else os.path.expanduser('~/Library/Caches/binzmuehle-atlas/terrain')
    step = float(args[args.index('--step') + 1]) if '--step' in args else STEP
    os.makedirs(cache, exist_ok=True)

    sc = json.load(open(scene_path))
    lat0, lon0 = sc['origin']
    R, (bx, by) = sc['R'], sc['bc']
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110574.0       # as in build_geo.py
    to_lv95 = lambda x, y: wgs_to_lv95(lat0 + y / ky, lon0 + x / kx)

    def to_local(e, n):
        lat, lon = lv95_to_wgs(e, n)
        return (lon - lon0) * kx, (lat - lat0) * ky

    half = R + step
    n = int(math.ceil(2 * half / step)) + 1
    x0, y0 = math.floor((bx - half) / step) * step, math.floor((by - half) / step) * step

    # reference: the ground at the scene origin (single-point height service)
    e0, n0 = to_lv95(0.0, 0.0)
    ref_file = os.path.join(cache, 'origin.json')
    if not os.path.exists(ref_file):
        json.dump(get(API + f'height?easting={e0:.1f}&northing={n0:.1f}&sr=2056'), open(ref_file, 'w'))
    z0 = float(json.load(open(ref_file))['height'])
    print(f'origin LV95 {e0:.1f} {n0:.1f}, ground {z0} m; grid {n}x{n} at {step:g} m from ({x0:g}, {y0:g})')

    rows, calls, worst, lo, hi, newest = [], 0, 0.0, 1e9, -1e9, 0.0
    for j in range(n):
        y = y0 + j * step
        dy = y - by
        if abs(dy) > half:
            rows.append(None); continue
        w = math.sqrt(max(0.0, half * half - dy * dy))                # the board's chord on this row, plus a cell
        i0 = max(0, int(math.floor((bx - w - x0) / step)))
        i1 = min(n - 1, int(math.ceil((bx + w - x0) / step)))
        cnt = i1 - i0 + 1
        f = os.path.join(cache, f'row_{step:g}_{j:03d}_{i0}_{cnt}.json')
        if not os.path.exists(f):
            a, b = to_lv95(x0 + i0 * step, y), to_lv95(x0 + i1 * step, y)
            geom = json.dumps({'type': 'LineString', 'coordinates': [[round(a[0], 2), round(a[1], 2)], [round(b[0], 2), round(b[1], 2)]]})
            url = API + 'profile.json?' + urllib.parse.urlencode({'geom': geom, 'sr': 2056, 'nb_points': cnt})
            res = get(url); calls += 1
            json.dump([[p['easting'], p['northing'], p['alts'].get('COMB', p['alts'].get('DTM2'))] for p in res], open(f, 'w'))
            time.sleep(0.4)                                               # be polite to the free service
            if calls % 20 == 0:
                print(f'  {calls} rows fetched (row {j}/{n})')
        pts = json.load(open(f))
        newest = max(newest, os.path.getmtime(f))
        if len(pts) != cnt:
            sys.exit(f'row {j}: expected {cnt} points, got {len(pts)}; delete {f} and retry')
        vals = []
        for k, (e, nn, h) in enumerate(pts):
            lx, ly = to_local(e, nn)
            worst = max(worst, math.hypot(lx - (x0 + (i0 + k) * step), ly - y))
            vals.append(int(round((h - z0) / UNIT)))
            lo, hi = min(lo, h), max(hi, h)
        rows.append([i0] + vals[:1] + [vals[k] - vals[k - 1] for k in range(1, len(vals))])

    print(f'fetched {calls} rows ({sum(r is not None for r in rows)} rows in total); heights {lo:.1f} to {hi:.1f} m '
          f'({lo - z0:+.1f} to {hi - z0:+.1f} relative); largest grid offset {worst:.2f} m')
    out = {'src': 'swissALTI3D © swisstopo, via the api3.geo.admin.ch profile service', 'x0': x0, 'y0': y0, 'd': step,
           'nx': n, 'ny': n, 'u': UNIT, 'z0': z0,
           'date': time.strftime('%Y-%m-%d', time.localtime(newest)), 'rows': [r or [] for r in rows]}
    s = json.dumps(out, separators=(',', ':'), ensure_ascii=False)
    open(out_path, 'w').write(s)
    print('wrote', out_path, round(len(s) / 1024), 'KB')


if __name__ == '__main__':
    main()
