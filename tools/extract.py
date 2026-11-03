import pdfplumber,sys,json
pdf=pdfplumber.open(sys.argv[1])
KEYS=['no','holder','location','area','area_alt','kind','name','period','term','type','districts','conditions']
recs=[];cont=0;hdr=0
for pn,p in enumerate(pdf.pages):
    for t in p.extract_tables():
        for r in t:
            r=[(c or '').strip() for c in r]
            if len(r)!=12: print("WARN cols",pn,len(r),r[:2],file=sys.stderr); continue
            if r[0].startswith('免許番号'): hdr+=1; continue
            if not r[0]:
                if not recs: continue
                cont+=1
                for k,v in zip(KEYS,r):
                    if v: recs[-1][k]+= '\n'+v
                recs[-1]['pages'].append(pn+1)
                continue
            d=dict(zip(KEYS,r)); d['pages']=[pn+1]; recs.append(d)
for d in recs:
    for k in ['no','holder','location','kind','name','period','term','type','districts','conditions']:
        d[k]=d[k].replace('\n','')
json.dump(recs,open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
print(len(recs),"records; continuation rows",cont,"headers",hdr,file=sys.stderr)
