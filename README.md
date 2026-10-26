# Binzmühle Quartier-Atlas

An open 3D neighbourhood model of **Affoltern and Oerlikon (Zürich, Kreis 11)** around the new GISA estate
**Siedlung Binzmühle** (Zelghalde / Kügeliloostrasse). A plaster-white city on a model board with the new rows set in
as birch wood: explore places, take guided walks, see what's on, and add what is missing.

*Ein offenes 3D-Quartiermodell von Affoltern und Oerlikon rund um die neue GISA-Siedlung Binzmühle. Orte entdecken,
Rundgänge machen, Anlässe finden und Fehlendes ergänzen.*

**Live:** https://phideltaee.github.io/binzmuehle-atlas/

**Author:** Fidel Esquivel ([@phideltaee](https://github.com/phideltaee))

> **Unofficial.** An independent neighbourhood project, not affiliated with Baugenossenschaft GISA. The official site
> is [binzmuehle.ch](https://www.binzmuehle.ch). *Inoffiziell: ein unabhängiges Nachbarschaftsprojekt, nicht mit der
> GISA verbunden.*

## What's in it

| | |
|---|---|
| 3D model | OpenStreetMap buildings (heights from OSM levels or type defaults), land use, streets, rail, tram and street trees within 1.8 km |
| The estate | Five rows after GISA's site plan, fitted to the federal building register: 19 houses (4 storeys + set-back attic), open walkways ("Viadukte"), balcony towers, two lanes and two garden courts. Rows 1–3 (stage 1, autumn 2027) in birch, rows 4–5 (stage 2, 2029) as a translucent sketch |
| Places | 159 in 10 groups (33 Kitas, kindergartens and schools, playgrounds, parks, sport, culture, food and shops, community, health, mobility), each with a walking time from the estate, German and English text and a source |
| Walking routes | 144 pre-routed footpaths (OSRM) from the estate to every place on the board |
| Walks | 4 guided routes: Kita morning & commute, Saturday in Oerlikon, green loop with a pram (Hürstwald), old Affoltern |
| Events | 35, November 2026 – October 2027, with a month strip and regular events |
| Layers | trees, place names, walking-time rings, stops, bus lines 80 and 64, drinking fountains, recycling points, bike and car sharing |
| Contribute | ideas for the estate plus "Fehlt ein Ort?": drop a pin and get a record to copy |
| Terrain | swissALTI3D heights (© swisstopo) on a 15 m grid, shown 1.5× exaggerated; "Relief" switch in the layers menu |
| Modes | German/English, light and dark UI, day and night model, phone layout |

## How it's built

One static HTML page, no server and no build tools beyond Python 3 (standard library; PIL only for `build_site.py`).
three.js 0.170 loads from jsDelivr. The GitHub Pages workflow runs `assemble.py --public` on every push to `main`.

```
src/app.html          UI + three.js engine (template with __SCENE__/__CONTENT__/__ROUTES__/__OVERLAY__ placeholders)
src/assemble.py       injects the data into the template -> one HTML file (--public: GitHub Pages build)
src/build_site.py     GISA site plan + federal building register points -> data/site.json (the new rows)
src/build_geo.py      Overpass JSON + site.json -> data/scene.json
src/build_content.py  research JSON -> data/content.json (places, events, routed walks, lines)
src/build_routes.py   OSRM walking routes from the estate -> data/routes.json (cached)
src/build_terrain.py  swisstopo profile service (swissALTI3D) -> data/terrain.json (height grid in model metres)
src/queries/*.txt     the Overpass queries (buildings in 4×4 tiles, land, points, bus routes)
data/research/*.json  researched places, events and walk suggestions, each with a source
```

```bash
python3 -I src/assemble.py src/app.html data/scene.json data/content.json data/routes.json index.html --public
```

Rebuilding the 3D city needs the raw OpenStreetMap downloads (about 15 MB, not in the repo): fetch them with the queries
in `src/queries` from overpass-api.de, one tile at a time, then run `build_geo.py <raw dir> data/site.json data/scene.json`.
New or corrected places go into `data/research/*.json`, then `build_content.py`, `build_routes.py` and `assemble.py`.

## How the estate was placed

GISA publishes no site coordinates, only the schematic site plan behind its unit list. The federal building register
(GWR, `api3.geo.admin.ch`, layer `ch.bfs.gebaeude_wohnungs_register`) lists the five new rows as buildings under
construction (EGID 302067231 Kügeliloostrasse 63–69, 302067232 Zelghalde 30–36, 302067233 Zelghalde 31–37,
302067234 Binderweg 2–10, 302067235 Binderweg 1–9). `build_site.py` fits the drawing to those five points (scale
0.344 m per pixel, rotation −11°, residuals 0.4–1.2 m). Heights are schematic: 3.05 m per storey, four storeys plus an
attic set back 2 m. Walkways, balcony towers, lanes and courts follow the drawing; their details are not published.

## Credits and data

- Map data © OpenStreetMap contributors, ODbL. Routing: OSRM (routing.openstreetmap.de). Building points: GWR / swisstopo.
- Terrain: swissALTI3D, © swisstopo (geo.admin.ch profile service).
- Estate: Baugenossenschaft GISA, binzmuehle.ch (project and site plan, October 2026).
- Places and events: City of Zürich open data, GISA, community centres and associations (each record has a `source`).
  Opening hours and dates change; check the source before you go.
- Code: MIT (see `LICENSE`), adapted from the [Koch-Quartier Atlas](https://github.com/phideltaee/koch-atlas).

Missing or wrong? Open an [issue](https://github.com/phideltaee/binzmuehle-atlas/issues) or use "Fehlt ein Ort?" in the map.
