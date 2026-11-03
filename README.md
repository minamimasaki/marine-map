# 愛媛県 区画漁業権マップ

水産庁が公表している「[区画漁業権に関する情報一覧（愛媛県）](https://www.jfa.maff.go.jp/j/enoki/attach/pdf/gyogyouken_jouhou3-346.pdf)」（存続期間 令和6年4月1日から）に記載された漁場を、ウェブ地図（Leaflet＋地理院タイル）で表示します。

## 見かた

静的なページなので、リポジトリ直下をウェブサーバーで配信すれば動きます（GitHub Pages でも可）。

```sh
python3 -m http.server 8000
# http://localhost:8000/ を開く
```

- 色は漁業の種類（魚類／真珠・貝類／海藻類）です。1か所に複数の種類があるときは灰色で示します。
- 左のパネルで、海域（燧灘・伊予灘・宇和海）・種類・漁業の名称・表示精度による絞り込みと検索ができます。
- マーカーや区域をクリックすると、免許番号・漁業権者・漁業時期・存続期間・関係地区・条件、区域の原文、原本PDFのページ番号を表示します。

## 表示の精度

PDFでは、漁場の区域の大部分が「基点（岬・防波堤・番地の標識など）から何度何メートルの点」で定められています。基点の多くは小さな目標物で、公開されている地名データにありません。そのため、区域を正確に描けるのは一部だけです。精度は次のように分けて表示しています。

| 区分 | 件数 | 方法 |
|---|---:|---|
| 区域（PDFの座標） | 2 | PDFに書かれた緯度経度から区域を描画（燧区第37号、宇珠区第113号） |
| 区域（推定） | 9 | 基点の岬・小島などを地名データで特定し、方位・距離から区域を計算 |
| 地先の位置 | 446 | 「漁場の位置」欄の地先（集落・大字・島）の沖にマーカーを配置 |
| 地先の位置（地区単位） | 21 | 地区名でしか絞れないもの。破線の円（半径1.2km）で表示 |
| 位置を特定できず | 12 | 地図には出さず、一覧にだけ掲載 |

推定した区域は、次の条件で検証したものだけを採用しています。

- 基点の位置が、行政区域データの海岸線から200m以内にあること
- 区域の6割以上が陸地に重ならないこと
- 地先から大きく離れていないこと

それでも数十〜百m程度の誤差はあり得ます。方位は真方位とみなしています（PDFに真方位・磁針方位の別の記載はありません）。除外区域は、点で定義されているものだけ差し引いています。

**正確な区域は必ず原本PDFで確認してください。この地図は参考資料であり、法的な効力はありません。**

## データの作り方

`data/fishing_grounds.geojson` は `tools/` のスクリプトで生成しています（Python 3.11、`tools/requirements.txt`）。作業ディレクトリ `W` に元PDFを `W/pdf/g.pdf` として置き、次の順に実行します。

```sh
tools/fetch.sh W                                   # 行政区域・町字データの取得
python -I tools/extract.py W/pdf/g.pdf W/recs.json # PDFの表を抽出（490件）
python -I tools/parse.py W                         # 区域の記述を基点・点に分解
python -I tools/ov.py W/dl/div.parquet "divisions/type=division"   # Overture Maps から地名を取得
python -I tools/ov.py W/dl/land.parquet "base/type=land"
python -I tools/ov.py W/dl/water.parquet "base/type=water"
python -I tools/gaz.py W && python -I tools/gaz2.py W              # 地名辞書の作成
python -I tools/geo3.py W > /dev/null              # 地先の位置の照合
python -I tools/build.py W W/out.geojson           # 区域の計算・検証、マーカー位置の決定
python -I tools/export.py W data/fishing_grounds.geojson
```

各フィーチャーの `properties` には、`no`（免許番号）、`holder`、`location`、`region`、`kind`、`name`、`category`、`group`、`period`、`term`、`type`、`districts`、`conditions`、`area_text`（区域の原文）、`pages`（PDFのページ）、`accuracy`（`exact` / `approx` / `point` / `district` / `none`）、`note` があります。位置を特定できなかったものは `geometry` が `null` です。

## 出典・クレジット

- 漁業権の情報：水産庁「区画漁業権に関する情報一覧（愛媛県）」
- 地名（位置推定に使用）：© OpenStreetMap contributors, Overture Maps Foundation（ODbL）
- 海岸線・行政区域：国土数値情報（行政区域データ）を加工した [niiyz/JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson)
- 町字の代表点：[Geolonia 住所データ](https://github.com/geolonia/japanese-addresses)（CC BY 4.0）
- 背景地図：地理院タイル、OpenStreetMap
