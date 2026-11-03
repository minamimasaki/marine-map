import json,sys,re,collections,math
from shapely.geometry import shape,Point
from shapely.ops import unary_union
S=sys.argv[1]
recs=json.load(open(f'{S}/recs.json'))[:-1]
CODE={'四国中央市':'38213','新居浜市':'38205','西条市':'38206','今治市':'38202','越智郡上島町':'38356','松山市':'38201','西宇和郡伊方町':'38442','八幡浜市':'38204','西予市':'38214','宇和島市':'38203','南宇和郡愛南町':'38506'}
muni={}
for c,code in CODE.items():
    fc=json.load(open(f'{S}/dl/muni/{code}.json'))
    muni[c]=unary_union([shape(f['geometry']) for f in fc['features']])
gaz=json.load(open(f'{S}/gaz.json'))
towns={c:json.load(open(f'{S}/dl/towns/{c}.json')) for c in CODE}
def nz(s): return s.replace('ヶ','ケ').replace('ヵ','ケ').replace('之','の').replace('ノ','の')
idx=collections.defaultdict(list)
for g in gaz:
    for n in g['n']: idx[nz(n)].append(g)
def km(a,b): return math.hypot((a[0]-b[0])*92.5,(a[1]-b[1])*111)
def ov(name,c,near=None,r=6):
    out=[]
    for g in idx.get(nz(name),[]):
        if g['t']=='water' and g['s'] in('river','stream','canal','pond') and not name.endswith('川'): continue
        if muni[c].distance(Point(g['x'],g['y']))>0.03: continue
        if near and km((g['x'],g['y']),near)>r: continue
        out.append(g)
    return out
res={}
for loc in sorted(set(r['location'] for r in recs)):
    c=next((c for c in CODE if loc.startswith(c)),'宇和島市')
    rest=loc[len(c):] if loc.startswith(c) else loc[3:]
    rest=re.sub('地先$','',rest)
    parts=[p for p in re.split('、|及び同町|及び',rest) if p]
    p=re.sub('(北東部|東南部|北部|東部|西部|南部|西海岸)$','',parts[0])
    # town: longest prefix in geolonia
    town=None
    for t in towns[c]:
        n=nz(t['town'])
        if nz(p).startswith(n) and (town is None or len(n)>len(nz(town['town']))): town=t
    tp=(town['lng'],town['lat']) if town else None
    remainder=p[len(town['town']):] if town else p
    hit=None
    if remainder:
        subs=sorted({remainder[i:j] for i in range(len(remainder)) for j in range(i+2,len(remainder)+1)},key=lambda s:(-len(s), -remainder.endswith(s)))
        for s in subs:
            cs=ov(s,c,tp,6 if tp else None)
            if not cs and town: cs=ov(town['town']+s,c,tp,6)
            if cs: hit=(s,cs); break
    if not hit and town:
        cs=ov(town['town'],c,tp,3)
        hit=(town['town'],cs) if cs else None
    res[loc]={'city':c,'part':p,'town':town,'rem':remainder,'hit':hit}
    hs=[(x['n'][0],x['s'],x['c'],x['x'],x['y']) for x in hit[1]][:3] if hit else None
    print(loc,'| T:',town['town'] if town else None,'| R:',remainder,'| H:',hit[0] if hit else None,hs)
json.dump(res,open(f'{S}/geo3.json','w'),ensure_ascii=False)
