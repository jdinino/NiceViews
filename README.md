# Nice Views

Interactive map of scenic viewpoints, hidden gems, waterfalls, beaches, mountain vistas, motorcycle routes, and public restrooms across all of New England.

**[View the live map →](https://jdinino.github.io/NiceViews/)**

## What's on the Map

| Layer | Count | Source |
| --- | --- | --- |
| Scenic spots & landmarks | 385 | Hand-curated + [NER B-O-N-E](https://www.newenglandriders.org/b-o-n-e/) |
| Reference photos | 243 / 385 (63%) | Wikipedia/Commons + originals |
| Motorcycle-friendly road segments | 322 | NER B-O-N-E + [OpenStreetMap](https://www.openstreetmap.org) via Overpass |
| Public restrooms | 2,306 | [Boston Public Amenities Map](https://www.google.com/maps/d/viewer?mid=1yciPnqgJqtqKFcZI4NAvRm6ey9A_wT0) + [bathroomaccess.com](https://bathroomaccess.com) + [OSM amenity=toilets](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dtoilets) |
| **Total spots** | **3,013** | |

### Coverage
- **Massachusetts** ~1,765 spots
- **New Hampshire / Maine** ~459
- **Vermont** ~283
- **Rhode Island** ~282
- **Connecticut** ~223

## Filters

**Radio (one at a time):**
- **All Spots** — every spot on the map
- **Within 30 mi** — within 30 miles of your GPS location (or Chelmsford default)
- **Local Loop** — within 10 miles of your GPS location (or Chelmsford default)
- **Ponds, Falls & Mountains** — Wachusett, Walden Pond, Trap Falls, and more
- **Ocean & Beaches** — Singing Beach, Crane Beach, Cape Cod lighthouses, Hampton Beach, Rockport, and Boston-area picks
- **Going North / South / East / West** — directional tours from Chelmsford

**Toggle layers (overlay on top of any radio filter):**
- 🚻 **Restrooms** — 2,306 public restrooms
- 🏍️ **Riders' Roads** — motorcycle routes with road geometry highlighted

## Spot Details

Each marker opens a sheet with:
- GPS coordinates and a Google Maps link
- Street View link
- What3Words address (where available)
- Wikipedia / Wikimedia Commons reference photo (where matched and content-verified)

## Features

- Leaflet map with category-specific icons (mountain, waterfall, beach, lookout, historic, park, canal, road, restroom)
- Live GPS location: auto-locate on load, pulsing blue dot, recenter button, auto-expands filter if no spots near you
- Fullscreen map toggle (top-right) for mobile real-estate
- Route Planner with nearest-neighbor stop ordering from GPS (or Chelmsford default), 15-stop cap with "+N more" expand
- Sortable spot table with clickable GPS and What3Words links
- Mobile-first responsive layout with horizontal pill-bar filters and auto-scrolling card sets

## Perfect For

- October foliage drives
- Weekend day trips
- Motorcycle touring
- Photography outings
- Long drives with kids who need a bathroom every hour
- Any time you need a view that'll make you stop and breathe

## Data Quality

Photos are verified by name-token overlap and Wikipedia globalusage cross-check. Spots are de-duplicated by proximity + name-token overlap on import. Road polylines are sourced from OSM with connectivity filtering to keep only contiguous ways.
