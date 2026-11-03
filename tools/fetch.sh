#!/bin/sh
# 位置推定に使う公開データを作業ディレクトリ $1 に取得する
set -eu
W=$1; mkdir -p "$W/dl/muni" "$W/dl/towns"
for c in 38201 38202 38203 38204 38205 38206 38207 38210 38213 38214 38215 38356 38386 38401 38402 38422 38442 38484 38488 38506; do
  curl -sf -o "$W/dl/muni/$c.json" "https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/38/$c.json"
done
for n in 松山市 今治市 宇和島市 八幡浜市 新居浜市 西条市 大洲市 伊予市 四国中央市 西予市 越智郡上島町 伊予郡松前町 西宇和郡伊方町 南宇和郡愛南町; do
  e=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$n")
  curl -sf -o "$W/dl/towns/$n.json" "https://raw.githubusercontent.com/geolonia/japanese-addresses/master/api/ja/%E6%84%9B%E5%AA%9B%E7%9C%8C/$e.json"
done
