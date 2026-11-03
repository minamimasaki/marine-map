"""Write the web map's data file from build.py's outputs.

usage: python -I export.py <work dir> <out geojson>
"""
import json, sys

W, OUT = sys.argv[1], sys.argv[2]
GROUP = {'真珠・真珠貝': '真珠・貝類', 'かき': '真珠・貝類', '貝類（ひおうぎ・あわび）': '真珠・貝類',
         '魚類養殖': '魚類', 'くろまぐろ': '魚類', 'のり': '海藻類', '海藻類（わかめ・ひじき等）': '海藻類'}


def category(name):
    if '真珠' in name: return '真珠・真珠貝'
    if 'まぐろ' in name and '除く' not in name: return 'くろまぐろ'
    if '魚類' in name: return '魚類養殖'
    if 'のり' in name and 'とさか' not in name: return 'のり'
    if 'かき' in name: return 'かき'
    if 'ひおうぎ' in name or 'あわび' in name: return '貝類（ひおうぎ・あわび）'
    return '海藻類（わかめ・ひじき等）'


feats = json.load(open(f'{W}/out.geojson'))['features']
for f in feats:
    p = f['properties']
    p['group'] = GROUP[p['category']]
    if p['accuracy'] in ('point', 'district'):
        p['note'] = ''
for u in json.load(open(f'{W}/unplaced.json')):
    cat = category(u['name'])
    recs = {r['no']: r for r in json.load(open(f'{W}/recs2.json'))}
    r = recs[u['no']]
    feats.append({'type': 'Feature', 'geometry': None, 'properties': {
        'no': r['no'], 'holder': r['holder'], 'location': r['location'], 'region': u['region'], 'kind': r['kind'],
        'name': u['name'], 'category': cat, 'group': GROUP[cat], 'period': r['period'], 'term': r['term'],
        'type': r['type'], 'districts': r['districts'], 'conditions': r['conditions'], 'area_text': r['area'],
        'pages': r['pages'], 'accuracy': 'none', 'note': ''}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(feats), 'features')
