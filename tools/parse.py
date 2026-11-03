import json,sys,re,unicodedata,collections
S=sys.argv[1]
recs=json.load(open(f'{S}/recs.json'))[:-1]
Z2H=str.maketrans('０１２３４５６７８９','0123456789')
BASE='ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺABCDEFGHIJKLMNOPQRSTUVWXYZ'
KANA='アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'
def norm_letter(c):
    if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ': return chr(ord(c)-ord('A')+ord('Ａ'))
    return c
def parse(area):
    a=area.replace('－','-').replace('ー','ー')
    lines=a.split('\n')
    head=[];bases=collections.OrderedDict();verts=collections.OrderedDict();mode='head';cur=None
    for ln in lines:
        s=ln.strip()
        m=re.match(r'^基点\s*([Ａ-ＺA-Z])\s*(.*)$',s)
        if m: mode='base'; cur=('b',norm_letter(m.group(1))); bases[cur[1]]=m.group(2); continue
        m=re.match(r'^点\s*([ア-ン])\s*(.*)$',s)
        if m: mode='vert'; cur=('v',m.group(1)); verts[cur[1]]=m.group(2); continue
        if mode=='base':
            m=re.match(r'^([Ａ-ＺA-Z])\s+(.*)$',s)
            if m: cur=('b',norm_letter(m.group(1))); bases[cur[1]]=m.group(2); continue
            bases[cur[1]]+=s; continue
        if mode=='vert':
            m=re.match(r'^([ア-ン])\s+(.*)$',s)
            if m: cur=('v',m.group(1)); verts[cur[1]]=m.group(2); continue
            verts[cur[1]]+=s; continue
        head.append(s)
    return ''.join(head),bases,verts
out=[];stats=collections.Counter()
for r in recs:
    h,b,v=parse(r['area'])
    r['head']=h; r['bases']=b; r['verts']=v
    for k,d in v.items():
        d=d.translate(Z2H).replace(',','')
        if re.fullmatch(r'(.)から(\d+)度(\d+分)?(\d+(\.\d+)?)メートルの点',d): stats['bearing']+=1
        elif re.fullmatch(r'(.)から(.+?)見通し(\d+(\.\d+)?)メートルの点',d): stats['sight']+=1
        elif '交点' in d: stats['intersect']+=1
        elif '北緯' in d: stats['latlon']+=1
        else: stats['other']+=1; print('OTHER',r['no'],k,d)
    out.append(r)
print(stats)
json.dump(out,open(f'{S}/recs2.json','w'),ensure_ascii=False,indent=0)
