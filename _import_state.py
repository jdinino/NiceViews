"""
Consolidated NER BONE import pipeline.

Usage: python _import_state.py <state_code>
  where <state_code> is one of: me, ri, vt

Encodes every learned-the-hard-way fix from the MA + NH import so
ME / RI / VT land cleanly without manual cleanup:

  1. Fetch the 3 GPX files (roads / scenicviews / attractions)
  2. Drop non-Flag-Blue waypoints from roads (POIs that NER bundles in)
  3. Normalize names (strip trailing digits, leading state prefix,
     slash composites, double spaces)
  4. Recategorize scenic + attraction by keyword
     (Mt X -> mountain, Falls -> waterfall, Lighthouse -> historic, etc.)
  5. Dedupe within new + vs existing spots (50m + name-token overlap)
  6. Assign routes (directional from Chelmsford + thematic ponds/ocean)
  7. Fetch OSM road polylines:
     - try ref (US + state + bare number variants)
     - try name with state-prefix strip + abbreviation expansion
     - connectivity filter (BFS from seed, drop unrelated same-name segs)
     - reject if seed > 3km from anchor
  8. Merge directional pairs (X East + X West -> X with combined polyline)
  9. Generate second-endpoint markers for state routes with > 5km polylines
 10. Snap marker to polyline if anchor > 500m from any polyline point
 11. Strip directional suffixes from state route names
 12. Append OSM 'name' alias to route number (NH 112 -> Kancamagus Highway)
 13. Fetch photos with strict GPS + name verification
     (Wikipedia geo + Wikidata + Commons geo, all with location checks)
 14. Drop weak notes (NER BONE pick boilerplate, address-only, town-only)

Roads, restrooms, and the toggle behavior are not touched on existing
data — only new spots are added.
"""
import sys, re, math, json, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
import concurrent.futures, time
from collections import Counter, defaultdict

if len(sys.argv) != 2 or sys.argv[1] not in ('me','ri','vt'):
    print('Usage: python _import_state.py <me|ri|vt>')
    sys.exit(2)
STATE = sys.argv[1]
STATE_NAME = {'me':'Maine','ri':'Rhode Island','vt':'Vermont'}[STATE]
STATE_PREFIX = STATE.upper()  # 'ME', 'RI', 'VT'

UA = 'NiceViews/1.0 (https://github.com/jdinino/NiceViews; via Claude Code)'
SPOTS_PATH = 'A:/NiceViews/spots.json'

CHELMSFORD = (42.6, -71.35)

def fetch(url, timeout=30, data=None):
    req = urllib.request.Request(url, headers={'User-Agent': UA}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_json(url, timeout=15):
    return json.loads(fetch(url, timeout).decode('utf-8'))

def dm(a, b):
    dlat = (a[0]-b[0])*111000
    dlng = (a[1]-b[1])*111000*math.cos(math.radians(a[0]))
    return (dlat*dlat + dlng*dlng) ** .5

# =======================================================================
# 1. FETCH + PARSE GPX
# =======================================================================
def fetch_gpx(category):
    """Fetch NER GPX, return list of waypoint dicts."""
    url = f'https://www.newenglandriders.org/download/{STATE}-{category}/'
    print(f'  fetching {url}')
    try:
        gpx = fetch(url, timeout=30).decode('utf-8', errors='replace')
    except Exception as e:
        print(f'    error: {e}')
        return []
    root = ET.fromstring(gpx)
    ns_uri = root.tag.split('}')[0][1:] if '}' in root.tag else ''
    ns = {'g': ns_uri} if ns_uri else {}
    wpts = []
    for w in root.findall('.//g:wpt' if ns_uri else 'wpt', ns):
        lat = float(w.attrib['lat']); lng = float(w.attrib['lon'])
        def gettxt(tag):
            el = w.find(f'g:{tag}' if ns_uri else tag, ns)
            return (el.text or '').strip() if el is not None and el.text else ''
        wpts.append({
            'name': gettxt('name'),
            'lat': lat, 'lng': lng,
            'cmt': gettxt('cmt'),
            'desc': gettxt('desc'),
            'sym': gettxt('sym'),
        })
    return wpts

# =======================================================================
# 2-3. POI FILTER + NAME NORMALIZATION
# =======================================================================
ROAD_POI_PATTERNS = [
    r'\brestaurant\b', r'\bmcdonald', r'^DD\s', r'^DDStart\b', r'\bcumby',
    r"\bfamily's gas\b", r'\bvillage mart\b', r'\brestrooms?\b', r'\bmonument\b',
    r"\bisaac'?s\b", r'\blighthouse\b',
]
def is_road_poi(w):
    name = w['name']
    if w['sym'] not in ('', 'Flag, Blue'):
        return True
    return any(re.search(p, name, re.I) for p in ROAD_POI_PATTERNS)

DIR_SFX_FULL = re.compile(r'\s+(N|S|E|W|North|South|East|West)$', re.I)

def normalize_name(name):
    n = re.sub(r'([a-zA-Z])\d+$', r'\1', name)               # 'Drift Road1' -> 'Drift Road'
    n = re.sub(r'^(NH|MA|RI|VT|ME|CT)\s+(?![0-9])', '', n, flags=re.I)  # 'NH Bear Notch' -> 'Bear Notch'
    if '/' in n:
        parts = [p.strip() for p in n.split('/')]
        n = max(parts, key=len)                              # composite: keep longer side
    n = re.sub(r'\s{2,}', ' ', n).strip()
    return n

# =======================================================================
# 4. KEYWORD RECATEGORIZATION
# =======================================================================
RECAT_RULES = [
    (r'\bcanal\b|\breservoir\b|\bdam\b', 'canal'),
    (r'\blight\b(?!\s+lookout)|\blighthouse\b|\bbridge\b|\btunnel\b|\bportal\b'
     r'|\binn\b|\bhomestead\b|\bvisitor.s?\s+center\b|\bmonument\b|\bmemorial\b'
     r'|\bbattleship\b|\bcastle\b|\bcathedral\b|\bfort\b|\bobservatory\b',
     'historic'),
    (r'\bfalls?\b|\bflume\b|\bgorge\b|\bcascade\b', 'waterfall'),
    (r'\bbeach\b|\bdunes?\b', 'beach'),
    (r'^Mount\s+\w+|^Mt\s+\w+|\bmountain\b|\bpeak\b|\bsummit\b|\bquabbin tower\b'
     r'|\bobservation tower\b|\bsugar hill\b|\bhigh point\b|\bnotch\b', 'mountain'),
    (r'\bpark\b|\bgarden\b|\barboretum\b|\bforest\b|\bpreserve\b|\breservation\b', 'park'),
]
def recategorize(name, fallback):
    n = name.lower()
    for pattern, cat in RECAT_RULES:
        if re.search(pattern, n):
            return cat
    return fallback

# =======================================================================
# 5. ROUTE ASSIGNMENT
# =======================================================================
def direction_from_chelmsford(lat, lng):
    dlat = lat - CHELMSFORD[0]
    dlng = lng - CHELMSFORD[1]
    return ('north' if dlat > 0 else 'south') if abs(dlat) >= abs(dlng) else ('east' if dlng > 0 else 'west')

PONDS_CATS = {'mountain', 'waterfall', 'canal'}
OCEAN_CATS = {'beach'}
def assign_routes(spot):
    if 'road' in spot['cats']:
        return ['roads']
    routes = [direction_from_chelmsford(spot['lat'], spot['lng'])]
    cat = spot['cats'][0]
    if cat in PONDS_CATS: routes.append('ponds')
    if cat in OCEAN_CATS: routes.append('boston')  # internal key for Ocean & Beaches
    return routes

# =======================================================================
# 6. DEDUPE
# =======================================================================
SKIP_TOKENS = {'the','a','an','of','at','in','on','to','view','vista','overlook',
               'lookout','scenic','area','road','rd','st','street','beach','pond',
               'lake','mountain','mt','park','bridge','historic','memorial',
               'national','state','site'}
def name_tokens(s):
    n = re.sub(r'[^a-z0-9 ]', ' ', s.lower())
    return {t for t in n.split() if t and t not in SKIP_TOKENS and len(t) >= 3}

def dedupe_new_vs_existing(new_spots, existing_spots, prox_m=200):
    """Drop new spots within `prox_m` of an existing spot when their distinctive
    name tokens overlap. Also dedupes within new (commutative loop)."""
    ex_pts_toks = [((s['lat'], s['lng']), name_tokens(s['name']), s) for s in existing_spots]
    kept = []
    for n in new_spots:
        n_toks = name_tokens(n['name'])
        n_pt = (n['lat'], n['lng'])
        dup = False
        for ep, et, es in ex_pts_toks:
            if dm(n_pt, ep) > prox_m: continue
            if n_toks and et and (n_toks & et): dup = True; break
            # Or exact name match
            if n['name'].lower() == es['name'].lower(): dup = True; break
        if dup: continue
        # Dedupe within new
        for k in kept:
            if dm(n_pt, (k['lat'],k['lng'])) > prox_m: continue
            kt = name_tokens(k['name'])
            if (n_toks and kt and (n_toks & kt)) or n['name'].lower() == k['name'].lower():
                dup = True; break
        if not dup: kept.append(n)
    return kept

# =======================================================================
# 7. ROAD POLYLINE LOOKUP
# =======================================================================
ABBREV = {'Rd':'Road','St':'Street','Ave':'Avenue','Blvd':'Boulevard','Dr':'Drive',
          'Ln':'Lane','Tpke':'Turnpike','Hwy':'Highway','Pkwy':'Parkway','Ct':'Court'}

def parse_route_query(name):
    """Return a list of (kind, value/values) tuples to try in order against OSM."""
    s = name
    s = re.sub(r'\s+(Canada Border|Border|Vista|View|Bottom|Top)$', '', s, flags=re.I)
    s = DIR_SFX_FULL.sub('', s).strip()

    queries = []
    m = re.match(r'^(NH|MA|RI|VT|ME|CT|US|I)\s+Route\s+(\d+[A-Z]?)$', s, re.I)
    if m:
        prefix, num = m.group(1).upper(), m.group(2)
        queries.append(('ref', [f'US {num}', f'{prefix} {num}', num]))
        return queries
    m = re.match(r'^Route\s+(\d+[A-Z]?)$', s, re.I)
    if m:
        num = m.group(1)
        queries.append(('ref', [f'US {num}', f'{STATE_PREFIX} {num}', f'NH {num}', f'MA {num}', num]))
        return queries
    m = re.match(r'^(NH|MA|RI|VT|ME|CT|US|I)\s+(\d+[A-Z]?)$', s, re.I)
    if m:
        prefix, num = m.group(1).upper(), m.group(2)
        queries.append(('ref', [f'{prefix} {num}', f'US {num}', num]))
        return queries
    if re.match(r'^\d+[A-Z]?$', s):
        num = s
        queries.append(('ref', [f'US {num}', f'{STATE_PREFIX} {num}', f'NH {num}', f'MA {num}', num]))
        return queries

    # Named road — try as-is and with abbreviation expansion
    parts = s.split()
    parts_expanded = [ABBREV.get(p, p) for p in parts]
    candidates = [' '.join(parts_expanded)]
    if candidates[0] != s: candidates.append(s)
    # Also try without leading state prefix
    s_stripped = re.sub(r'^(NH|MA|RI|VT|ME|CT)\s+', '', s, flags=re.I).strip()
    if s_stripped and s_stripped != s and s_stripped not in candidates:
        candidates.append(s_stripped)
    queries.append(('name', candidates))
    return queries

def overpass_ways(query, timeout=45):
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    for attempt in range(3):
        try:
            req = urllib.request.Request('https://overpass-api.de/api/interpreter',
                                         data=data, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout+5) as r:
                return [e for e in json.loads(r.read().decode('utf-8')).get('elements',[])
                        if e['type']=='way' and e.get('geometry')]
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(5*(attempt+1)); continue
            return []
        except Exception:
            return []
    return []

def connectivity_filter(ways, anchor, conn_m=200, max_seed_m=3000):
    if not ways: return []
    def md(w): return min(dm(p, anchor) for p in w)
    distances = [md(w) for w in ways]
    seed = min(range(len(ways)), key=lambda i: distances[i])
    if distances[seed] > max_seed_m: return []
    kept = {seed}; front=[seed]
    while front:
        nf=[]
        for i in front:
            wi=ways[i]; ei=[wi[0],wi[-1]]
            for j in range(len(ways)):
                if j in kept: continue
                wj=ways[j]; ej=[wj[0],wj[-1]]
                if any(dm(a,b)<conn_m for a in ei for b in ej):
                    kept.add(j); nf.append(j)
        front=nf
    return [ways[i] for i in sorted(kept)]

def fetch_road_polyline(spot):
    """Try every parse_route_query strategy, return geoms or []."""
    anchor = (spot['lat'], spot['lng'])
    bbox = (anchor[0]-0.3, anchor[1]-0.3, anchor[0]+0.3, anchor[1]+0.3)
    for kind, values in parse_route_query(spot['name']):
        if kind == 'ref':
            ref_re = '|'.join(re.escape(v) for v in values)
            q = (f'[out:json][timeout:45];'
                 f'way["ref"~"(^|;)({ref_re})($|;)"]'
                 f'({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});out geom;')
        else:
            patterns = '|'.join(re.escape(v) for v in values)
            q = (f'[out:json][timeout:45];'
                 f'way["name"~"^({patterns})$",i]'
                 f'({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});out geom;')
        ways = overpass_ways(q)
        scored = []
        for w in ways:
            geom = [[round(g['lat'],5), round(g['lon'],5)] for g in w['geometry']]
            min_d = min(dm(p, anchor) for p in geom)
            scored.append((min_d, geom))
        scored.sort(key=lambda x: x[0])
        candidates = [g for d, g in scored[:25] if d < 8000]
        geoms = connectivity_filter(candidates, anchor)
        if geoms: return geoms
        time.sleep(0.5)
    return []

def snap_marker_to_polyline(spot):
    if not spot.get('way'): return
    anchor = (spot['lat'], spot['lng'])
    endpoints = []
    for seg in spot['way']: endpoints.extend([seg[0], seg[-1]])
    endpoints.sort(key=lambda p: dm(anchor, p))
    if endpoints and dm(anchor, endpoints[0]) > 500:
        spot['lat'] = round(endpoints[0][0], 4)
        spot['lng'] = round(endpoints[0][1], 4)

# =======================================================================
# 8. MERGE DIRECTIONAL PAIRS
# =======================================================================
def merge_directional_pairs(spots):
    """If 'X East' and 'X West' both exist as separate entries, combine polylines."""
    by_base = defaultdict(list)
    for s in spots:
        if 'road' not in s['cats']: continue
        base = DIR_SFX_FULL.sub('', s['name']).strip()
        by_base[base].append(s)
    for base, members in by_base.items():
        if len(members) < 2: continue
        # Combine polylines
        combined = []
        seen_keys = set()
        for m in members:
            for seg in m.get('way') or []:
                key = (seg[0][0], seg[0][1], seg[-1][0], seg[-1][1])
                if key not in seen_keys:
                    seen_keys.add(key); combined.append(seg)
        # All members get full polyline; names drop direction
        for i, m in enumerate(members):
            m['way'] = combined
            m['name'] = base if i == 0 else f'{base} (other end)'

# =======================================================================
# 9. SECOND ENDPOINTS (for state routes with long polylines)
# =======================================================================
STATE_ROUTE_RE = re.compile(
    r'^((NH|MA|RI|VT|ME|CT|US|I)\s+)?(Route\s+)?\d+[A-Z]?$', re.I)
def generate_endpoints(spots, next_id):
    new_endpoints = []
    for s in spots:
        if 'road' not in s['cats']: continue
        if not s.get('way'): continue
        if not STATE_ROUTE_RE.match(s['name'].split(' (other end)')[0]): continue
        # Skip if already has '(other end)' partner in new_spots
        partner_name = s['name'] + ' (other end)'
        if any(x['name'] == partner_name for x in spots): continue
        anchor = (s['lat'], s['lng'])
        all_pts = [p for seg in s['way'] for p in seg]
        if not all_pts: continue
        far_pt = max(all_pts, key=lambda p: dm(p, anchor))
        if dm(far_pt, anchor) < 5000: continue
        new_endpoints.append({
            'id': next_id,
            'name': s['name'] + ' (other end)',
            'lat': round(far_pt[0], 4), 'lng': round(far_pt[1], 4),
            'w3w': '', 'routes': ['roads'],
            'note': f'Far endpoint of {s["name"]}', 'images': [],
            'icon': s['icon'], 'cats': ['road'],
            'way': s['way'],
        })
        next_id += 1
    return new_endpoints

# =======================================================================
# 10. ROUTE NAME ALIASES (Kancamagus etc.)
# =======================================================================
GENERIC_ROAD_NAMES = {
    'main street','main st','high street','union street','broadway','elm street',
    'park street','mill street','church street','school street','south street',
    'north street','east street','west street','depot street','water street',
    'state street','bridge street',
}
def append_route_aliases(spots):
    for s in spots:
        if 'road' not in s['cats']: continue
        if not s.get('way'): continue
        if not STATE_ROUTE_RE.match(s['name'].split(' (other end)')[0]): continue
        queries = parse_route_query(s['name'].split(' (other end)')[0])
        if not queries or queries[0][0] != 'ref': continue
        refs = queries[0][1]
        # Use polyline bbox
        pts = [p for seg in s['way'] for p in seg]
        lats = [p[0] for p in pts]; lngs = [p[1] for p in pts]
        pad = 0.02
        bbox = (min(lats)-pad, min(lngs)-pad, max(lats)+pad, max(lngs)+pad)
        ref_re = '|'.join(re.escape(r) for r in refs)
        q = (f'[out:json][timeout:30];'
             f'way["ref"~"(^|;)({ref_re})($|;)"]'
             f'({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});out tags;')
        try:
            data = urllib.parse.urlencode({'data': q}).encode('utf-8')
            req = urllib.request.Request('https://overpass-api.de/api/interpreter',
                                         data=data, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=35) as r:
                els = json.loads(r.read().decode('utf-8')).get('elements',[])
        except Exception:
            continue
        names = Counter()
        for el in els:
            if el['type'] != 'way': continue
            nm = el.get('tags', {}).get('name')
            if nm and nm.lower() not in GENERIC_ROAD_NAMES and not any(r.lower() in nm.lower() for r in refs):
                names[nm] += 1
        if not names: continue
        top, count = names.most_common(1)[0]
        if count < 2: continue
        m = re.match(r'^(.*?)(\s+\(other end\))?$', s['name'])
        base, tail = m.group(1), (m.group(2) or '')
        s['name'] = f'{base} — {top}{tail}'
        time.sleep(0.8)

# =======================================================================
# 11. PHOTO LOOKUP (geo + name verified)
# =======================================================================
PLACE_NAMES_PHOTOS = {
    'massachusetts','hampshire','vermont','rhode','maine','connecticut',
    'new','england','boston','cambridge','somerville','brookline','salem',
    'manchester','portsmouth','nashua','keene','providence','newport',
    'burlington','montpelier','portland','bangor','augusta',
}
def photo_tokens(s):
    n = re.sub(r'[^a-z0-9 ]', ' ', s.lower())
    skip = {'view','vista','overlook','lookout','scenic','area','road','rd','st',
            'street','national','state','file','jpg','png','jpeg','webp','beach',
            'pond','lake','mountain','mount','mt','park','bridge','site',
            'historic','memorial'} | PLACE_NAMES_PHOTOS
    return {t for t in n.split() if t and t not in skip and len(t) >= 3}

BAD_PHOTO_PAT = re.compile(
    r'\.(svg|pdf)$|map_of|locator|coat_of_arms|_seal|_logo|_sign\.|_signs|_emblem'
    r'|_crest|_flag|diagram|plan_of|unsplash|stock_photo|geograph\.org\.uk'
    r'|peking|beijing|rio_de_janeiro|brazil|isle_of_man|tokyo|london|paris',
    re.I
)

def fetch_photos(spot, max_results=3):
    spot_toks = photo_tokens(spot['name'])
    if not spot_toks: return []
    out = []

    # 1) Wikipedia geosearch within 250m + name token overlap
    try:
        d = fetch_json(f'https://en.wikipedia.org/w/api.php?action=query&list=geosearch'
                       f'&gscoord={spot["lat"]}%7C{spot["lng"]}&gsradius=250&gslimit=8&format=json')
        for r in d.get('query',{}).get('geosearch',[]):
            title = r.get('title','')
            if not (photo_tokens(title) & spot_toks): continue
            try:
                sm = fetch_json(f'https://en.wikipedia.org/api/rest_v1/page/summary/'
                                f'{urllib.parse.quote(title.replace(" ","_"))}')
                desc = (sm.get('description') or '').lower()
                if re.search(r'^(city|town|village|state|country|region|county)\s', desc): continue
                if sm.get('type') == 'disambiguation': continue
                thumb = sm.get('thumbnail',{}).get('source')
                if thumb and not BAD_PHOTO_PAT.search(thumb):
                    out.append(thumb); break
            except Exception: continue
    except Exception: pass
    if len(out) >= max_results: return out

    # 2) Commons geosearch within 500m + name token overlap
    try:
        d = fetch_json(f'https://commons.wikimedia.org/w/api.php?action=query&list=geosearch'
                       f'&gscoord={spot["lat"]}%7C{spot["lng"]}&gsradius=500&gsnamespace=6&gslimit=12&format=json')
        for r in d.get('query',{}).get('geosearch',[]):
            title = r.get('title','')
            if not title.startswith('File:'): continue
            if BAD_PHOTO_PAT.search(title): continue
            if not (photo_tokens(title[5:]) & spot_toks): continue
            try:
                info = fetch_json(f'https://commons.wikimedia.org/w/api.php?action=query&titles='
                                  f'{urllib.parse.quote(title)}&prop=imageinfo&iiprop=url%7Cmime'
                                  f'&iiurlwidth=500&format=json')
                for _, p in info.get('query',{}).get('pages',{}).items():
                    ii = p.get('imageinfo',[])
                    if ii:
                        u = ii[0].get('thumburl') or ii[0].get('url')
                        m = ii[0].get('mime','')
                        if u and m.startswith('image/') and 'svg' not in m and u not in out:
                            out.append(u)
                            break
            except Exception: continue
            if len(out) >= max_results: break
    except Exception: pass
    return out

# =======================================================================
# 12. NOTE CLEANUP
# =======================================================================
def clean_note(spot):
    n = (spot.get('note') or '').strip()
    if not n: return ''
    if re.search(r'NER\s+(NH|MA|RI|VT|ME)\s+BONE\s+pick', n, re.I): return ''
    if re.fullmatch(r'\w+(\s+\w+){0,2}\s+(Twn|County)', n): return ''
    if re.fullmatch(r'N\d+\.\d+.*W\d+\.\d+.*', n): return ''
    if 'road' in spot['cats'] and re.match(r'^\s*\d+\s+\w', n): return ''  # address-only for roads
    return n

# =======================================================================
# MAIN
# =======================================================================
def main():
    print(f'=== Importing {STATE_NAME} BONE data ===\n')
    with open(SPOTS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    next_id = max(s['id'] for s in data['spots']) + 1
    existing = data['spots']

    # 1. Fetch + parse
    print('Step 1: fetch GPX')
    roads_w = [w for w in fetch_gpx('roads') if not is_road_poi(w)]
    scenic_w = fetch_gpx('scenicviews')
    attr_w = fetch_gpx('attractions')
    print(f'  roads(clean): {len(roads_w)}  scenic: {len(scenic_w)}  attractions: {len(attr_w)}')

    # 2-3. Normalize names + build initial spot records
    print('\nStep 2: build spot records')
    cats_dict = data['cats']
    def make(w, fallback_cat):
        cat = recategorize(w['name'], fallback_cat) if fallback_cat != 'road' else 'road'
        icon = cats_dict[cat].get('icon')
        note_parts = []
        if w.get('cmt'): note_parts.append(w['cmt'].split('\n')[0].strip())
        return {
            'id': 0, 'name': normalize_name(w['name']),
            'lat': round(w['lat'], 4), 'lng': round(w['lng'], 4),
            'w3w': '', 'routes': [], 'note': ' / '.join(note_parts),
            'images': [], 'icon': icon, 'cats': [cat],
        }
    spots = [make(w, 'lookout') for w in scenic_w] \
          + [make(w, 'historic') for w in attr_w] \
          + [make(w, 'road') for w in roads_w]

    # 5. Dedupe within new + vs existing
    print('\nStep 3: dedupe')
    before = len(spots)
    spots = dedupe_new_vs_existing(spots, existing, prox_m=200)
    print(f'  {before} -> {len(spots)}')

    # 6. Routes
    for s in spots:
        s['routes'] = assign_routes(s)

    # 7. Road polylines (concurrent)
    print('\nStep 4: fetch road polylines via OSM')
    road_spots = [s for s in spots if 'road' in s['cats']]
    print(f'  {len(road_spots)} roads to look up')
    def lookup_one(s):
        s['way'] = fetch_road_polyline(s) or []
        if s['way']: snap_marker_to_polyline(s)
        return s
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for i, _ in enumerate(ex.map(lookup_one, road_spots)):
            if (i+1) % 20 == 0: print(f'    {i+1}/{len(road_spots)} done')
    hits = sum(1 for s in road_spots if s.get('way'))
    print(f'  polylines: {hits}/{len(road_spots)}')

    # 8. Merge directional pairs
    print('\nStep 5: merge directional pairs')
    merge_directional_pairs(spots)

    # 11. Strip direction suffix from state route names (now that pairs are merged)
    for s in spots:
        if 'road' not in s['cats']: continue
        s['name'] = DIR_SFX_FULL.sub('', s['name']).strip()

    # 10. Route aliases
    print('\nStep 6: append OSM road name aliases')
    append_route_aliases(road_spots)

    # 9. Second endpoints (after pairs merged and aliases set)
    print('\nStep 7: generate second endpoints for long state routes')
    # assign IDs first
    for s in spots:
        if s['id'] == 0: s['id'] = next_id; next_id += 1
    endpoints = generate_endpoints(spots, next_id)
    for e in endpoints: next_id = max(next_id, e['id']+1)
    print(f'  generated {len(endpoints)} second endpoints')
    spots.extend(endpoints)

    # 12. Note cleanup
    for s in spots: s['note'] = clean_note(s)

    # 13. Photos (concurrent, non-road only)
    print('\nStep 8: fetch photos with location + name verification')
    photo_targets = [s for s in spots if 'road' not in s['cats']]
    def photo_one(s):
        s['images'] = fetch_photos(s)
        return s
    hits = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for i, s in enumerate(ex.map(photo_one, photo_targets)):
            if s['images']: hits += 1
            if (i+1) % 30 == 0: print(f'    {i+1}/{len(photo_targets)} done  hits={hits}')
    print(f'  photos: {hits}/{len(photo_targets)}')

    # Merge into spots.json
    data['spots'].extend(spots)
    with open(SPOTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f'\nDone. Added {len(spots)} {STATE_NAME} entries:')
    by_cat = Counter(s['cats'][0] for s in spots)
    for cat, n in by_cat.most_common():
        print(f'  {n:>4}  {cat}')

if __name__ == '__main__':
    main()
