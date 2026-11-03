import pyarrow.parquet as pq, shapely, json, sys
S=sys.argv[1]; G=[]
keep={('land','island'),('land','islet'),('land','rock'),('land','reef'),('land','stone'),('water','cape'),('water','bay'),('water','strait'),('land','beach'),('land','cliff'),('land','peak'),('water','river'),('water','stream'),('div','hamlet'),('div','village'),('div','town')}
for f in ['div','land','water']:
    for r in pq.read_table(f'{S}/dl/{f}.parquet').to_pylist():
        n=r.get('names') or {}
        nm=set([n['primary']] if n.get('primary') else [])
        for k,v in (n.get('common') or []):
            if k=='ja': nm.add(v)
        if not nm: continue
        cls=r.get('class') or r.get('subtype')
        if (f,cls) not in keep and not (f=='div' and r.get('subtype') in ('neighborhood','microhood')): continue
        g=shapely.from_wkb(r['geometry'])
        G.append({'n':sorted(nm),'t':f,'c':cls,'s':r.get('subtype'),'wkt':shapely.to_wkt(g,rounding_precision=6)})
json.dump(G,open(f'{S}/gaz2.json','w'),ensure_ascii=False)
print(len(G))
