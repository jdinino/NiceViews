# Nice Views

Interactive map of scenic viewpoints, hidden gems, waterfalls, beaches, mountain vistas, motorcycle routes, and public restrooms across all of New England.

**[View the live map →](https://jdinino.github.io/NiceViews/)**

## What's on the Map

| Layer | Count | Source |
| --- | --- | --- |
| Scenic spots & landmarks | 438 | Hand-curated + [NER B-O-N-E](https://www.newenglandriders.org/b-o-n-e/) + top state parks |
| Reference photos | 367 / 438 (84%) | Wikipedia/Commons + Flickr CC + originals — every remote photo visually verified |
| Motorcycle-friendly road segments | 226 — every road draws its path, incl. the 1,079-mile Iron Butt Ride Around Maine loop | NER B-O-N-E + [OpenStreetMap](https://www.openstreetmap.org) via Overpass |
| Public restrooms | 2,287 | [Boston Public Amenities Map](https://www.google.com/maps/d/viewer?mid=1yciPnqgJqtqKFcZI4NAvRm6ey9A_wT0) + [bathroomaccess.com](https://bathroomaccess.com) + [OSM amenity=toilets](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dtoilets) |
| **Total spots** | **2,951** | |

### Coverage
- **Massachusetts** ~1,790 spots
- **New Hampshire / Maine** ~445
- **Vermont** ~285
- **Rhode Island** ~292
- **Connecticut** ~226

## Filters

**Radio (one at a time):**
- **All Spots** — every spot on the map
- **Within 30 mi** — within 30 miles of your GPS location (or Chelmsford default)
- **Local Loop** — within 10 miles of your GPS location (or Chelmsford default)
- **Ponds, Falls & Mountains** — Wachusett, Walden Pond, Trap Falls, and more
- **Ocean & Beaches** — Singing Beach, Crane Beach, Cape Cod lighthouses, Hampton Beach, Rockport, and Boston-area picks
- **State Parks** — 76 top parks across all six states (Baxter, Smugglers' Notch, Purgatory Chasm, Camden Hills…), selected by Wikipedia popularity
- **Going North / South / East / West** — directional tours from Chelmsford

**Toggle layers (overlay on top of any radio filter):**
- 🚻 **Restrooms** — 2,287 public restrooms
- 🏍️ **Riders' Roads** — motorcycle routes with road geometry highlighted

## Spot Details

Each marker opens a sheet with:
- GPS coordinates and a Google Maps link
- Street View link
- What3Words address (where available)
- Wikipedia / Wikimedia Commons reference photo (where matched and content-verified)

## Features

- Leaflet map with category-specific icons (mountain, waterfall, beach, lookout, historic, park, canal, road, restroom)
- Live GPS location: auto-locate on load, pulsing blue dot, recenter button, auto-expands filter if no spots near you, and distance filters re-center as you ride
- Fullscreen map toggle (top-right) for mobile real-estate
- All Spots toggles scenic markers off while a Restrooms/Riders' Roads overlay is on (overlay-only browsing)
- Route Planner with nearest-neighbor stop ordering from GPS (or Chelmsford default), 15-stop cap with "+N more" expand
- Mobile-first responsive layout with horizontal pill-bar filters and auto-scrolling card sets

## Perfect For

- October foliage drives
- Weekend day trips
- Motorcycle touring
- Photography outings
- Long drives with kids who need a bathroom every hour
- Any time you need a view that'll make you stop and breathe

## Data Quality

Every remote photo has been geo-anchored to a Wikipedia article at the spot's coordinates and then **visually inspected** against the spot's name and category — wrong-subject, junk, and out-of-region images are removed (a blank spot beats a wrong photo). Spots are de-duplicated by proximity + name-token overlap on import. Road polylines are sourced from OSM with connectivity filtering, simplified to 5 m tolerance, and every path is verified longer than 500 m with its marker on the road.
