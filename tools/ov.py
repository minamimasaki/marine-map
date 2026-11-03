import pyarrow.dataset as ds, pyarrow.fs as pfs, pyarrow.compute as pc, pyarrow.parquet as pq, sys, json, time
out=sys.argv[1]; typ=sys.argv[2]
fs=pfs.S3FileSystem(anonymous=True,region='us-west-2')
path=f'overturemaps-us-west-2/release/2026-10-21.0/theme={typ}'
d=ds.dataset(path,filesystem=fs,format='parquet')
print(d.schema.names, file=sys.stderr)
b=pc.field('bbox')
f=(pc.field('bbox','xmin')>132.0)&(pc.field('bbox','xmax')<133.8)&(pc.field('bbox','ymin')>32.8)&(pc.field('bbox','ymax')<34.45)
cols=[c for c in ['id','names','subtype','class','geometry','bbox','country','region'] if c in d.schema.names]
t0=time.time()
t=d.to_table(filter=f,columns=cols)
print(typ,t.num_rows,time.time()-t0,file=sys.stderr)
pq.write_table(t,out)
