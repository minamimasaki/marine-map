"""Reconstruct fishing-ground polygons from the PDF's base-point / bearing descriptions.

usage: python -I build.py <scratch dir> <out geojson>
"""
import json, sys, re, math, collections
import shapely
from shapely.geometry import shape, Point, Polygon, LineString, MultiPoint, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

S = sys.argv[1]
OUT = sys.argv[2]
recs = json.load(open(f'{S}/recs2.json'))
geo3 = json.load(open(f'{S}/geo3.json'))

Z2H = str.maketrans('０１２３４５６７８９．，－', '0123456789.,-')
CODE = {'四国中央市': '38213', '新居浜市': '38205', '西条市': '38206', '今治市': '38202', '越智郡上島町': '38356',
        '松山市': '38201', '西宇和郡伊方町': '38442', '八幡浜市': '38204', '西予市': '38214', '宇和島市': '38203',
        '南宇和郡愛南町': '38506'}
ALLCODES = ['38201', '38202', '38203', '38204', '38205', '38206', '38207', '38210', '38213', '38214', '38215', '38356',
            '38386', '38401', '38402', '38422', '38442', '38484', '38488', '38506']
muni = {}
for c, code in CODE.items():
    fc = json.load(open(f'{S}/dl/muni/{code}.json'))
    muni[c] = unary_union([shapely.make_valid(shape(f['geometry'])) for f in fc['features']]).buffer(0)
land = unary_union([shapely.make_valid(shape(f['geometry'])) for code in ALLCODES
                    for f in json.load(open(f'{S}/dl/muni/{code}.json'))['features']]).buffer(0)
land_parts = list(land.geoms) if land.geom_type == 'MultiPolygon' else [land]
land_tree = STRtree(land_parts)
coast = land.boundary


def nz(s):
    return (s.replace('ヶ', 'ケ').replace('ヵ', 'ケ').replace('ｹ', 'ケ').replace('之', 'の').replace('ノ', 'の')
            .replace('が', 'ケ').replace('ガ', 'ケ').replace('　', '').replace(' ', ''))


gaz = []
for g in json.load(open(f'{S}/gaz2.json')):
    g['geom'] = shapely.from_wkt(g['wkt'])
    g['pt'] = g['geom'] if g['geom'].geom_type == 'Point' else g['geom'].representative_point()
    gaz.append(g)
name_idx = collections.defaultdict(list)
for g in gaz:
    for n in g['n']:
        name_idx[nz(n)].append(g)
NAMES = sorted(name_idx, key=len, reverse=True)

PRECISE = {'cape', 'islet', 'island', 'rock', 'reef', 'stone', 'river', 'stream', 'cliff', 'beach', 'peak'}

# ---------------------------------------------------------------- geodesy
def offset(p, bearing_deg, dist_m):
    lon, lat = p
    b = math.radians(bearing_deg)
    dx, dy = dist_m * math.sin(b), dist_m * math.cos(b)
    return (lon + dx / (111320 * math.cos(math.radians(lat))), lat + dy / 110574)


def bearing(p, q):
    dx = (q[0] - p[0]) * 111320 * math.cos(math.radians(p[1]))
    dy = (q[1] - p[1]) * 110574
    return math.degrees(math.atan2(dx, dy)) % 360


def dist_m(p, q):
    dx = (q[0] - p[0]) * 111320 * math.cos(math.radians(p[1]))
    dy = (q[1] - p[1]) * 110574
    return math.hypot(dx, dy)


def intersect_rays(p, b1, q, b2):
    # solve p + t*u = q + s*v in local metres
    u = (math.sin(math.radians(b1)), math.cos(math.radians(b1)))
    v = (math.sin(math.radians(b2)), math.cos(math.radians(b2)))
    kx = 111320 * math.cos(math.radians(p[1])); ky = 110574
    qx, qy = (q[0] - p[0]) * kx, (q[1] - p[1]) * ky
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    if abs(det) < 1e-9:
        return None
    t = (qx * (-v[1]) - qy * (-v[0])) / det
    return (p[0] + t * u[0] / kx, p[1] + t * u[1] / ky)


DIRS = {'北': 0, '北北東': 22.5, '北東': 45, '東北東': 67.5, '東': 90, '東南東': 112.5, '南東': 135, '南南東': 157.5,
        '南': 180, '南南西': 202.5, '南西': 225, '西南西': 247.5, '西': 270, '西北西': 292.5, '北西': 315, '北北西': 337.5,
        '東南': 135, '西南': 225, '東北': 45, '西北': 315}


def num(s):
    return float(s.translate(Z2H).replace(',', ''))


def parse_bearing(s):
    s = s.translate(Z2H)
    m = re.match(r'(\d+)度(?:(\d+)分)?(?:(\d+)秒)?', s)
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2) or 0) / 60 + int(m.group(3) or 0) / 3600


# ---------------------------------------------------------------- place resolution
def extreme_point(geom, word):
    """Point of geom at the extremity indicated by e.g. 北端 / 南東端."""
    m = re.search(r'(北北東|北東|東北東|東南東|南東|南南東|南南西|南西|西南西|西北西|北西|北北西|東南|西南|東北|西北|北|東|南|西)(端|角|側|部|突端|先端)', word)
    if not m or geom.geom_type == 'Point':
        return None
    b = math.radians(DIRS[m.group(1)])
    ux, uy = math.sin(b), math.cos(b)
    if geom.geom_type in ('Polygon', 'MultiPolygon'):
        coords = [c for poly in getattr(geom, 'geoms', [geom]) for c in poly.exterior.coords]
    else:
        coords = [c for g in getattr(geom, 'geoms', [geom]) for c in g.coords]
    lat0 = geom.centroid.y
    k = math.cos(math.radians(lat0))
    best = max(coords, key=lambda c: c[0] * k * ux + c[1] * uy)
    return (best[0], best[1])


def river_mouth(geom):
    coords = [c for g in getattr(geom, 'geoms', [geom]) for c in g.coords]
    best = min(coords, key=lambda c: Point(c).distance(coast) if land.contains(Point(c)) else -1)
    return best


def strip_admin(desc):
    d = re.sub(r'^(愛媛県|香川県|広島県|山口県|大分県|高知県)', '', desc)
    for c in list(CODE) + ['今治市', '宇和島市', '松山市', '伊予市', '大洲市']:
        d = d.replace(c, '')
    return d.replace('同市', '').replace('同町', '')


def find_named(desc, anchor, radius_km, city=None):
    """Find the most specific precise feature named inside desc."""
    d = nz(strip_admin(desc))
    best = None
    for n in NAMES:
        if len(n) < 2 or n not in d:
            continue
        if best and len(n) < len(best[0]):
            break
        for g in name_idx[n]:
            kind = g['c'] if g['t'] != 'div' else g['s']
            if g['t'] == 'div' and kind not in ('hamlet', 'village'):
                continue
            if kind not in PRECISE and kind not in ('hamlet', 'village', 'bay', 'strait'):
                continue
            if kind in ('river', 'stream') and not re.search(nz(n) + r'(河口|左岸|右岸)', d):
                continue
            pt = g['pt']
            if anchor is not None:
                dk = dist_m(anchor, (pt.x, pt.y)) / 1000
                if dk > radius_km:
                    continue
            elif city is not None and muni[city].distance(pt) > 0.03:
                continue
            else:
                dk = 0
            cand = (n, g, kind, dk)
            if best is None or len(n) > len(best[0]) or (len(n) == len(best[0]) and dk < best[3]):
                best = cand
    if not best:
        return None
    n, g, kind, _ = best
    after = d[d.index(n) + len(n):]
    # 一致した地名の後ろに別の小地名が続く場合（例: 「日振島コオラ鼻北端」）は、包含する島や地区に
    # 一致しただけなので基点の位置としては使わない
    if after and not re.match(r'(北北東|北東|東北東|東南東|南東|南南東|南南西|南西|西南西|西北西|北西|北北西|東南|西南|東北|西北|北|東|南|西)?'
                              r'(端|角|突端|先端|中央|頂|山頂|島頂|の標識|標識|灯台|河口|左岸|右岸|から|より|側|部|の点|$)', after):
        return None
    if kind in ('river', 'stream'):
        p = river_mouth(g['geom'])
    else:
        p = extreme_point(g['geom'], after[:6]) or (g['pt'].x, g['pt'].y)
    conf = 'hamlet' if kind in ('hamlet', 'village', 'bay', 'strait') else 'feature'
    return {'p': p, 'name': n, 'kind': kind, 'conf': conf}


def latlon_in(desc):
    t = desc.translate(Z2H)
    m = re.search(r'北緯(\d+)度(\d+)分(\d+(?:\.\d+)?)秒、?東経(\d+)度(\d+)分(\d+(?:\.\d+)?)秒', t)
    if m:
        a = [float(x) for x in m.groups()]
        return (a[3] + a[4] / 60 + a[5] / 3600, a[0] + a[1] / 60 + a[2] / 3600)
    m = re.search(r'北緯(\d+\.\d+)、?東経(\d+\.\d+)', t)
    if m:
        return (float(m.group(2)), float(m.group(1)))
    return None


OFFSET_RE = re.compile(r'^(.*?)から(?:海岸線|護岸|海岸|堤防|岸壁)?(?:沿い)?(?:に)?(北北東|北東|東北東|東南東|南東|南南東|南南西|南西|西南西|西北西|北西|北北西|東南|西南|東北|西北|北|東|南|西|南北)(?:へ|に)(?:直線距離)?([\d,，０-９]+)(?:メートル|ｍ|m)')


class Ctx:
    def __init__(self, rec, anchor, city):
        self.rec = rec; self.anchor = anchor; self.city = city
        self.bases = {}; self.verts = {}; self.notes = []; self.min_conf = 'exact'

    def degrade(self, c):
        order = ['exact', 'feature', 'offset', 'hamlet']
        if order.index(c) > order.index(self.min_conf):
            self.min_conf = c


def resolve_desc(desc, ctx, radius_km=6, depth=0):
    """Resolve a free-text location (base point or sighting target) to (lon,lat)."""
    ll = latlon_in(desc)
    if ll:
        return ll
    m = re.fullmatch(r'([Ａ-Ｚ])', desc.strip())
    if m:
        return get_point(m.group(1), ctx)
    m = OFFSET_RE.match(desc.translate(Z2H))
    if m and depth < 3:
        src, d, L = m.group(1), m.group(2), num(m.group(3))
        p = resolve_desc(src, ctx, radius_km, depth + 1)
        if p is None:
            return None
        if d == '南北':
            return p
        if L > 150:
            ctx.degrade('offset')
        return offset(p, DIRS[d], L)
    r = find_named(desc, ctx.anchor, radius_km, ctx.city)
    if r is None and radius_km < 30:
        # sighting targets can be far away (another island etc.)
        r = None
    if r is None:
        return None
    if r['conf'] == 'hamlet':
        ctx.degrade('hamlet')
    else:
        ctx.degrade('feature')
    return r['p']


def get_point(k, ctx, depth=0):
    if k in ctx.bases:
        return ctx.bases[k]
    if k in ctx.verts:
        return ctx.verts[k]
    rec = ctx.rec
    if depth > 6:
        return None
    if k in rec['bases']:
        p = resolve_desc(rec['bases'][k], ctx)
        ctx.bases[k] = p
        return p
    if k in rec['verts']:
        ctx.verts[k] = None  # recursion guard
        p = resolve_vertex(rec['verts'][k], ctx, depth + 1)
        ctx.verts[k] = p
        return p
    return None


def target_bearing(src, tgt_desc, ctx, depth):
    p = get_point(src, ctx, depth) if len(src) == 1 else resolve_desc(src, ctx)
    if p is None:
        return None, None
    t = tgt_desc.strip()
    if len(t) == 1 and (t in ctx.rec['bases'] or t in ctx.rec['verts']):
        q = get_point(t, ctx, depth)
    else:
        q = resolve_desc(t, ctx, radius_km=40)
    if q is None or dist_m(p, q) < 1:
        return p, None
    return p, bearing(p, q)


def resolve_vertex(d, ctx, depth):
    d = d.translate(Z2H).replace(',', '').replace(' ', '')
    ll = latlon_in(d)
    if ll:
        return ll
    # X から N度M分S秒 L メートルの点
    m = re.fullmatch(r'(.)から(\d+度(?:\d+分)?(?:\d+秒)?)(\d+(?:\.\d+)?)メートルの点', d)
    if m:
        p = get_point(m.group(1), ctx, depth)
        return offset(p, parse_bearing(m.group(2)), float(m.group(3))) if p else None
    # X から T 見通し(線)? L メートルの点
    m = re.fullmatch(r'(.+?)から(.+?)見通し線?(?:上)?(\d+(?:\.\d+)?)メートル(?:の点)?', d)
    if m:
        p, b = target_bearing(m.group(1), m.group(2), ctx, depth)
        return offset(p, b, float(m.group(3))) if b is not None else None
    # intersections
    m = re.fullmatch(r'(.)から(\d+度(?:\d+分)?)の線と(.)から(\d+度(?:\d+分)?)の線との交点', d)
    if m:
        p = get_point(m.group(1), ctx, depth); q = get_point(m.group(3), ctx, depth)
        if p and q:
            return intersect_rays(p, parse_bearing(m.group(2)), q, parse_bearing(m.group(4)))
        return None
    m = re.fullmatch(r'(.+?)から(.+?)見通し線と(.+?)から(.+?)見通し線との交点', d)
    if m:
        p, b1 = target_bearing(m.group(1), m.group(2), ctx, depth)
        q, b2 = target_bearing(m.group(3), m.group(4), ctx, depth)
        if b1 is not None and b2 is not None:
            return intersect_rays(p, b1, q, b2)
        return None
    m = re.fullmatch(r'(.)から(\d+度(?:\d+分)?)の線と(.+?)から(.+?)見通し線との交点', d)
    if m:
        p = get_point(m.group(1), ctx, depth)
        q, b2 = target_bearing(m.group(3), m.group(4), ctx, depth)
        if p and b2 is not None:
            return intersect_rays(p, parse_bearing(m.group(2)), q, b2)
        return None
    m = re.fullmatch(r'(.+?)から(.+?)見通し線と(.)から(\d+度(?:\d+分)?)の線との交点', d)
    if m:
        p, b1 = target_bearing(m.group(1), m.group(2), ctx, depth)
        q = get_point(m.group(3), ctx, depth)
        if q and b1 is not None:
            return intersect_rays(p, b1, q, parse_bearing(m.group(4)))
        return None
    # 「アエ間のアから150メートルの点」
    m = re.fullmatch(r'(.)(.)間の(.)から(\d+(?:\.\d+)?)メートルの点', d)
    if m:
        a, b, s = m.group(1), m.group(2), m.group(3)
        other = b if s == a else a
        p = get_point(s, ctx, depth); q = get_point(other, ctx, depth)
        return offset(p, bearing(p, q), float(m.group(4))) if p and q else None
    ctx.notes.append('未対応の記述: ' + d)
    return None


# ---------------------------------------------------------------- ring assembly
PAIR = r'[ア-ンＡ-ＺA-Z]{2}'


def norm_pair(s):
    return ''.join(chr(ord(c) - ord('A') + ord('Ａ')) if 'A' <= c <= 'Z' else c for c in s)


def segments(clause):
    """Return list of (a, b, kind) where kind is 'line' or 'coast'."""
    segs = []
    clause = re.sub(r'メ[ーｰ－\-]トル', 'm', clause)
    # coast segments: "ＡＢ間", "ＡＢ及びＤＥ間", "ＡＢ間、ＣＤ間"
    coast_pairs = set()
    for m in re.finditer(r'((?:' + PAIR + r'(?:間)?(?:、|及び|､)?)+)の?(?:最大|地先最大|護岸)', clause):
        for p in re.findall(PAIR, m.group(1)):
            coast_pairs.add(norm_pair(p))
    for p in re.findall(PAIR + r'(?=間)', clause):
        coast_pairs.add(norm_pair(p))
    for p in re.findall(PAIR, clause):
        p = norm_pair(p)
        kind = 'coast' if p in coast_pairs else 'line'
        if (p[0], p[1], kind) not in segs:
            segs.append((p[0], p[1], kind))
    return segs


def chain(segs):
    """Order segments into a closed ring of point labels."""
    if not segs:
        return None
    segs = list(segs)
    a, b, k = segs.pop(0)
    ring = [a, b]; kinds = [k]
    while segs:
        last = ring[-1]
        for i, (x, y, kk) in enumerate(segs):
            if x == last:
                ring.append(y); kinds.append(kk); segs.pop(i); break
            if y == last:
                ring.append(x); kinds.append(kk); segs.pop(i); break
        else:
            return None
    if ring[0] != ring[-1]:
        # implicit closing along the coast
        kinds.append('coast'); ring.append(ring[0])
    return ring, kinds


def ring_polygon(ring, ctx):
    pts = []
    for k in ring:
        p = get_point(k, ctx)
        if p is None:
            return None, k
        pts.append(p)
    if len(set(pts)) < 3:
        return None, '点不足'
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly, None


def build(rec, anchor, city):
    ctx = Ctx(rec, anchor, city)
    head = rec['head']
    main, _, excl = head.partition('ただし')
    segs = segments(main)
    ch = chain([s for s in segs])
    if ch:
        ring, kinds = ch
        poly, missing = ring_polygon(ring, ctx)
    else:
        labels = []
        for a, b, _ in segs:
            labels += [a, b]
        labels = list(dict.fromkeys(labels))
        if len(labels) < 3:
            return None, ctx, '区域の構成を解釈できません'
        pts = []
        missing = None
        for k in labels:
            p = get_point(k, ctx)
            if p is None:
                missing = k; break
            pts.append(p)
        poly = None if missing else MultiPoint(pts).convex_hull
        if poly is not None:
            ctx.notes.append('区域の境界線の構成が複雑なため、関係する点を包む概形で表示')
    if poly is None:
        return None, ctx, f'基点・点 {missing} の位置を特定できません'
    # exclusions that are themselves closed rings of labelled points
    if excl:
        for part in re.split(r'並びに|の[0-9０-９]+直線(?:、|及び|と)|と(?=' + PAIR + ')', excl):
            es = segments(part)
            if len(es) >= 3:
                ech = chain(es)
                if ech:
                    ep, _ = ring_polygon(ech[0], ctx)
                    if ep is not None and ep.area > 0:
                        poly = poly.difference(ep)
        if '除く' in excl and not re.search(PAIR, excl):
            ctx.notes.append('除外区域は地図上で表現していません')
    return poly, ctx, None


# ---------------------------------------------------------------- anchors (地先)
BAD_ANCHOR = {'今治市吉海町沖浦地先', '宇和島市九島荒網代地先', '宇和島市吉田町野島地先'}


TOWNS = {c: json.load(open(f'{S}/dl/towns/{c}.json')) for c in CODE}


def town_mean(city, prefix):
    ts = [t for t in TOWNS[city] if t['town'].startswith(prefix)]
    return (sum(t['lng'] for t in ts) / len(ts), sum(t['lat'] for t in ts) / len(ts))


# 地先名が地名データに無い場所: 基点の記述に出てくる地名や上位の地区名で代替する
MANUAL = {
    '今治市吉海町沖浦地先': ((133.061283, 34.13631), 'point'),          # 基点「志津見漁港」→ 志津見
    '今治市吉海町鴨磯地先': (lambda: town_mean('今治市', '吉海町'), 'district'),
    '松山市浅海地先': ((132.795325, 34.001847), 'point'),               # 浅海原
    '松山市堀江地先': ((132.759138, 33.908885), 'point'),               # 堀江町
    '西宇和郡伊方町平磯及び釜木地先': ((132.142687, 33.410795), 'point'),  # 平礒
    '南宇和郡愛南町左右水地先': ((132.494889, 32.9712), 'district'),     # 中浦
    '南宇和郡愛南町塩子島地先': ((132.4531, 33.050302), 'district'),     # 基点「油袋」
    '南宇和郡愛南町水谷地先': ((132.600509, 32.921292), 'district'),     # 基点「大浜」
    '西予市三瓶町伊崎地先': ((132.387128, 33.376026), 'point'),          # 基点「周木南海岸」
    '西予市三瓶町須崎地先': ((132.392926, 33.368954), 'point'),          # 基点「長早」
    '西予市三瓶町辰ヶ崎地先': (lambda: town_mean('西予市', '三瓶町蔵貫浦'), 'point'),
    '西予市三瓶町枯井地先': (lambda: town_mean('西予市', '三瓶町皆江'), 'point'),
    '宇和島市吉田町野島地先': ((132.495363, 33.272762), 'district'),     # 基点「南君野島山」
    '宇和島市小高島地先': ((132.519, 33.2225), 'district'),             # 基点「本九島箱崎」→ 本九島
    '西条市市塚地先': ((133.195547, 33.94149), 'district'),             # 基点「西ひうち」
    '西条市干拓地先': ((133.143844, 33.915518), 'district'),            # 禎瑞（西条干拓）
}
for _k in ['宇和島市三浦大内、安米地先', '宇和島市三浦大内地先', '宇和島市三浦安米地先', '宇和島市三浦尾崎地先',
           '宇和島市三浦無月地先', '宇和島市三浦豊浦地先']:
    MANUAL[_k] = (lambda: town_mean('宇和島市', '三浦'), 'district')


def loc_anchor(loc):
    if loc in MANUAL:
        p, lvl = MANUAL[loc]
        return p() if callable(p) else p
    g = geo3.get(loc)
    if not g or loc in BAD_ANCHOR or not g['hit']:
        return None
    cs = g['hit'][1]
    pri = {'cape': 0, 'islet': 0, 'island': 1, 'hamlet': 2, 'microhood': 3, 'neighborhood': 4}
    cs = sorted(cs, key=lambda c: pri.get(c.get('c') or c.get('s'), 5))
    return (cs[0]['x'], cs[0]['y'])


def city_of(loc):
    for c in CODE:
        if loc.startswith(c):
            return c
    return '宇和島市'


def sea_point(p, max_m=400):
    """Move p (possibly on land) to the nearest sea location just off the coast."""
    P = Point(p)
    if not land.contains(P) and land.distance(P) > 0.0003:
        return p
    q = shapely.ops.nearest_points(coast, P)[0]
    b = bearing(p, (q.x, q.y)) if dist_m(p, (q.x, q.y)) > 1 else 0
    for d in (60, 120, 200, 300):
        for db in (0, 30, -30, 60, -60, 90, -90, 135, -135, 180):
            c = offset((q.x, q.y), b + db, d)
            if not land.contains(Point(c)):
                return c
    return (q.x, q.y)


def region_of(no):
    if no.startswith('燧'): return '燧灘'
    if no.startswith('伊'): return '伊予灘'
    return '宇和海'


def category(name):
    if '真珠' in name: return '真珠・真珠貝'
    if 'まぐろ' in name and '除く' not in name: return 'くろまぐろ'
    if '魚類' in name or name.startswith('式魚'): return '魚類養殖'
    if 'のり' in name and 'とさか' not in name: return 'のり'
    if 'かき' in name: return 'かき'
    if 'ひおうぎ' in name or 'あわび' in name: return '貝類（ひおうぎ・あわび）'
    return '海藻類（わかめ・ひじき等）'


FIX_NAME = {'式魚養類殖小業割式養殖業（くろまぐろ小割式養殖業を除く）': '魚類小割式養殖業（くろまぐろ小割式養殖業を除く）',
            '魚類小割式養殖業（くろまぐろ小割式養殖業': '魚類小割式養殖業（くろまぐろ小割式養殖業を除く）',
            '魚類小割式養殖業（くろまぐろ小割': '魚類小割式養殖業（くろまぐろ小割式養殖業を除く）'}

features = []
stats = collections.Counter()
fail = collections.Counter()
unres = []
unplaced = []
for rec in recs:
    loc = rec['location']; city = city_of(loc)
    anchor = loc_anchor(loc)
    poly, ctx, err = build(rec, anchor, city)
    if anchor is None:
        # derive the anchor from resolvable base points within the municipality
        for k in rec['bases']:
            p = ctx.bases.get(k)
            if p:
                anchor = p; break
    geom = None; acc = None
    if poly is not None and not poly.is_empty:
        sea = poly.difference(land)
        on_land = 1 - (sea.area / poly.area if poly.area else 0)
        span = max(dist_m(a, b) for a in poly.exterior.coords for b in poly.exterior.coords) if poly.geom_type == 'Polygon' else 0
        stated = [num(x) for x in re.findall(r'([\d,，０-９]+)メートル', rec['area'])]
        far = anchor is not None and dist_m(anchor, (poly.centroid.x, poly.centroid.y)) > 8000
        distinct = len({ctx.bases[k] for k in ctx.bases if ctx.bases[k]}) == len([k for k in ctx.bases if ctx.bases[k]])
        # 基点は海岸にある目標物なので、海岸線から離れた位置に解決された場合は誤りとみなす
        coast_gap = max([coast.distance(Point(p)) * 100000 for k, p in ctx.bases.items()
                         if p and not latlon_in(rec['bases'][k])] or [0])
        if coast_gap > 200:
            distinct = False
            ctx.notes.append(f'基点が海岸線から約{coast_gap:.0f}m離れている')
        if not distinct:
            ctx.notes.append('複数の基点が同一地点に解決された')
        if sea.is_empty or sea.area < 1e-9 or not distinct or on_land > 0.6 or far or (stated and span > 4 * max(stated) + 3000):
            fail['検証で除外'] += 1
            err = '推定した区域が陸上に重なる・離れすぎる等のため不採用'
        else:
            geom = sea
            acc = 'exact' if ctx.min_conf == 'exact' else ('approx' if ctx.min_conf in ('feature', 'offset') else 'rough')
    if geom is None:
        if anchor is None:
            fail['位置特定不可'] += 1
            unplaced.append({'no': rec['no'], 'location': loc, 'name': FIX_NAME.get(rec['name'], rec['name']),
                             'region': region_of(rec['no']), 'area_text': rec['area'], 'pages': rec['pages']})
            continue
        geom = Point(sea_point(anchor))
        acc = MANUAL[loc][1] if loc in MANUAL else 'point'
        if err: fail[err.split(' ')[0]] += 1
        if err and '特定できません' in err:
            k = err.split(' ')[1]
            unres.append((rec['no'], k, rec['bases'].get(k) or rec['verts'].get(k)))
    stats[acc] += 1
    name = FIX_NAME.get(rec['name'], rec['name'])
    props = {
        'no': rec['no'], 'holder': rec['holder'], 'location': loc, 'region': region_of(rec['no']),
        'kind': rec['kind'], 'name': name, 'category': category(name), 'period': rec['period'], 'term': rec['term'],
        'type': rec['type'], 'districts': rec['districts'], 'conditions': rec['conditions'],
        'area_text': rec['area'], 'pages': rec['pages'], 'accuracy': acc,
        'note': '；'.join(ctx.notes + ([err] if (err and acc == 'point') else [])),
    }
    features.append({'type': 'Feature', 'properties': props,
                     'geometry': mapping(shapely.set_precision(geom, 1e-6))})

json.dump({'type': 'FeatureCollection', 'features': features}, open(OUT, 'w'), ensure_ascii=False)
print('features', len(features), dict(stats), file=sys.stderr)
print('fail', dict(fail), file=sys.stderr)

json.dump(unres, open(f'{S}/unres.json','w'), ensure_ascii=False, indent=0)
json.dump(unplaced, open(f'{S}/unplaced.json','w'), ensure_ascii=False, indent=0)
