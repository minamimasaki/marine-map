import pyarrow.parquet as pq, shapely, json, sys, collections
S=sys.argv[1]; G=[]
for f in ['div','land','water']:
    t=pq.read_table(f'{S}/dl/{f}.parquet').to_pylist()
    for r in t:
        n=r.get('names') or {}
        nm=set()
        if n.get('primary'): nm.add(n['primary'])
        for k,v in (n.get('common') or []): 
            if k in('ja',): nm.add(v)
        if not nm: continue
        g=shapely.from_wkb(r['geometry'])
        p=g if g.geom_type=='Point' else g.representative_point()
        G.append({'n':sorted(nm),'t':f,'s':r.get('subtype'),'c':r.get('class'),'x':round(p.x,6),'y':round(p.y,6),'gt':g.geom_type})
json.dump(G,open(f'{S}/gaz.json','w'),ensure_ascii=False)
print(len(G)); print(collections.Counter((g['t'],g['s'],g['c']) for g in G).most_common(40))
