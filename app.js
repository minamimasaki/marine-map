(function () {
  'use strict';

  var GROUPS = [
    { id: '魚類', color: '#2a78d6', desc: '魚類小割式・くろまぐろ等' },
    { id: '真珠・貝類', color: '#eb6834', desc: '真珠・真珠貝・かき・ひおうぎ・あわび' },
    { id: '海藻類', color: '#1baf7a', desc: 'のり・わかめ・ひじき等' }
  ];
  var MIXED = '#7d7b75';
  var REGIONS = ['燧灘', '伊予灘', '宇和海'];
  var ACC = [
    { id: 'exact', label: '区域（PDFの座標）' },
    { id: 'approx', label: '区域（推定）' },
    { id: 'point', label: '地先の位置' },
    { id: 'district', label: '地先の位置（地区単位）' },
    { id: 'none', label: '位置を特定できず' }
  ];
  var ACC_LABEL = {};
  ACC.forEach(function (a) { ACC_LABEL[a.id] = a.label; });
  var GROUP_COLOR = {};
  GROUPS.forEach(function (g) { GROUP_COLOR[g.id] = g.color; });

  var state = {
    regions: new Set(REGIONS),
    groups: new Set(GROUPS.map(function (g) { return g.id; })),
    acc: new Set(ACC.map(function (a) { return a.id; })),
    name: '',
    q: ''
  };

  // ------------------------------------------------------------ map
  var map = L.map('map', { zoomControl: true, preferCanvas: false }).setView([33.55, 132.75], 9);
  var gsi = 'Tiles: <a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>';
  var base = {
    '地理院 淡色地図': L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png', { maxZoom: 18, attribution: gsi }),
    '地理院 標準地図': L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', { maxZoom: 18, attribution: gsi }),
    '地理院 写真': L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg', { maxZoom: 18, attribution: gsi }),
    'OpenStreetMap': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors' })
  };
  base['地理院 淡色地図'].addTo(map);
  var polyLayer = L.featureGroup().addTo(map);
  var districtLayer = L.featureGroup().addTo(map);
  var markerLayer = L.featureGroup().addTo(map);
  L.control.layers(base, null, { position: 'topright', collapsed: true }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);

  var legend = L.control({ position: 'bottomright' });
  legend.onAdd = function () {
    var d = L.DomUtil.create('div', 'map-legend');
    d.innerHTML = GROUPS.map(function (g) {
      return '<div><span class="sw" style="background:' + g.color + '"></span>' + g.id + '</div>';
    }).join('') + '<div><span class="sw" style="background:' + MIXED + '"></span>複数の種類</div>';
    return d;
  };
  legend.addTo(map);

  // ------------------------------------------------------------ helpers
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function shortLoc(loc) {
    return loc.replace(/^(越智郡|西宇和郡|南宇和郡)/, '').replace(/地先$/, '');
  }
  function groupColor(feats) {
    var gs = new Set(feats.map(function (f) { return f.properties.group; }));
    return gs.size === 1 ? GROUP_COLOR[feats[0].properties.group] : MIXED;
  }
  function featureCenter(f) {
    var g = f.geometry;
    if (!g) return null;
    if (g.type === 'Point') return L.latLng(g.coordinates[1], g.coordinates[0]);
    return L.geoJSON(g).getBounds().getCenter();
  }

  // ------------------------------------------------------------ data
  var all = [];
  var byLoc = new Map();
  var locMarkers = new Map();

  function matches(f) {
    var p = f.properties;
    if (!state.regions.has(p.region)) return false;
    if (!state.groups.has(p.group)) return false;
    if (!state.acc.has(p.accuracy)) return false;
    if (state.name && p.name !== state.name) return false;
    if (state.q) {
      var hay = (p.no + ' ' + p.location + ' ' + p.name + ' ' + p.holder + ' ' + p.districts + ' ' + p.area_text);
      var terms = state.q.split(/\s+/).filter(Boolean);
      for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) < 0) return false;
    }
    return true;
  }

  function licenseHtml(f) {
    var p = f.properties;
    var pages = p.pages.length > 1 ? p.pages[0] + '–' + p.pages[p.pages.length - 1] : p.pages[0];
    return '<div class="lic"><div class="lic-h"><span class="sw" style="background:' + GROUP_COLOR[p.group] + '"></span>' +
      esc(p.no) + '　' + esc(p.name) + '</div>' +
      '<dl>' +
      '<dt>精度</dt><dd>' + esc(ACC_LABEL[p.accuracy]) + '</dd>' +
      '<dt>漁業権者</dt><dd>' + esc(p.holder) + '</dd>' +
      '<dt>漁業の種類</dt><dd>' + esc(p.kind) + '</dd>' +
      '<dt>漁業時期</dt><dd>' + esc(p.period) + '</dd>' +
      '<dt>存続期間</dt><dd>' + esc(p.term) + '</dd>' +
      '<dt>団体・個別</dt><dd>' + esc(p.type) + '</dd>' +
      '<dt>関係地区</dt><dd>' + esc(p.districts) + '</dd>' +
      '<dt>条件</dt><dd>' + esc(p.conditions) + '</dd>' +
      '<dt>原本</dt><dd>PDF ' + pages + 'ページ</dd>' +
      '</dl>' +
      (p.note ? '<div class="warn">' + esc(p.note) + '</div>' : '') +
      '<details><summary>漁場の区域（原文）</summary><pre>' + esc(p.area_text) + '</pre></details></div>';
  }

  function popupHtml(loc, feats) {
    var acc = new Set(feats.map(function (f) { return f.properties.accuracy; }));
    var note = '';
    if (acc.has('point') || acc.has('district')) {
      note = '<div class="warn">マーカーは地先（' + esc(shortLoc(loc)) + '）のおおよその位置です。' +
        (acc.has('district') ? '地区名でしか位置を絞れないため、誤差が1km以上になることがあります。' : '') +
        '実際の区域は原文の基点・方位・距離で定められています。</div>';
    }
    return '<div class="pp"><h3>' + esc(shortLoc(loc)) + '</h3>' +
      '<span class="acc">' + feats.length + '件の漁業権・' + esc(feats[0].properties.region) + '</span>' + note +
      feats.map(licenseHtml).join('') + '</div>';
  }

  // ------------------------------------------------------------ render
  function render() {
    polyLayer.clearLayers();
    districtLayer.clearLayers();
    markerLayer.clearLayers();
    locMarkers.clear();
    var shown = all.filter(matches);
    var groups = new Map();
    shown.forEach(function (f) {
      var k = f.properties.location;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(f);
    });

    var polyCount = 0;
    groups.forEach(function (feats, loc) {
      var placed = feats.filter(function (f) { return f.geometry; });
      if (!placed.length) return;
      var popup = function () { return popupHtml(loc, feats); };
      placed.forEach(function (f) {
        var p = f.properties;
        if (f.geometry.type === 'Point') return;
        polyCount++;
        var c = GROUP_COLOR[p.group];
        L.geoJSON(f, {
          style: {
            color: c, weight: 2, opacity: .95, fillColor: c,
            fillOpacity: p.accuracy === 'exact' ? .45 : .28,
            dashArray: p.accuracy === 'exact' ? null : '6 4'
          }
        }).bindPopup(function () { return popupHtml(loc, [f].concat(feats.filter(function (x) { return x !== f; }))); },
          { maxWidth: 360 })
          .bindTooltip(esc(p.no) + '　' + esc(p.name) + '（' + ACC_LABEL[p.accuracy] + '）', { sticky: true })
          .addTo(polyLayer);
      });
      var pts = placed.filter(function (f) { return f.geometry.type === 'Point'; });
      var center = featureCenter(pts[0] || placed[0]);
      var isDistrict = pts.length && pts.every(function (f) { return f.properties.accuracy === 'district'; });
      var color = groupColor(feats);
      if (isDistrict) {
        L.circle(center, { radius: 1200, color: color, weight: 1.5, dashArray: '4 4', fill: true, fillOpacity: .06, interactive: false })
          .addTo(districtLayer);
      }
      var n = feats.length;
      var m = L.circleMarker(center, {
        radius: Math.min(5 + 2.2 * Math.sqrt(n), 15), color: '#ffffff', weight: 2, fillColor: color,
        fillOpacity: pts.length ? .92 : .55, polyOnly: !pts.length
      }).bindPopup(popup, { maxWidth: 360 })
        .bindTooltip(esc(shortLoc(loc)) + '（' + n + '件）', { direction: 'top', offset: [0, -6] });
      m.addTo(markerLayer);
      locMarkers.set(loc, m);
    });
    updatePolyOnlyMarkers();

    document.getElementById('statShown').textContent = shown.length;
    document.getElementById('statPoly').textContent = polyCount;
    document.getElementById('statLoc').textContent = groups.size;
    renderList(groups);
    renderCounts(shown);
  }

  // markers that only stand for drawn polygons get out of the way once the polygons are legible
  function updatePolyOnlyMarkers() {
    var z = map.getZoom();
    markerLayer.eachLayer(function (m) {
      if (m.options.polyOnly) m.setStyle({ opacity: z >= 14 ? 0 : 1, fillOpacity: z >= 14 ? 0 : .55 });
    });
  }
  map.on('zoomend', updatePolyOnlyMarkers);

  function renderList(groups) {
    var ul = document.getElementById('list');
    var html = [];
    groups.forEach(function (feats, loc) {
      var color = groupColor(feats);
      var names = Array.from(new Set(feats.map(function (f) { return f.properties.name.replace(/（.*$/, ''); }))).join('、');
      var nos = feats.map(function (f) { return f.properties.no; });
      var placed = feats.some(function (f) { return f.geometry; });
      var hasPoly = feats.some(function (f) { return f.geometry && f.geometry.type !== 'Point'; });
      var sub = (nos.length > 3 ? nos.slice(0, 3).join('・') + ' ほか' : nos.join('・')) + '｜' + names +
        (hasPoly ? '｜区域あり' : '') + (placed ? '' : '｜位置を特定できず');
      html.push('<li><button type="button" data-loc="' + esc(loc) + '"' + (placed ? '' : ' disabled') + '>' +
        '<span class="sw" style="background:' + color + '"></span>' +
        '<span class="loc">' + esc(shortLoc(loc)) + '</span><span class="cnt">' + feats.length + '件</span>' +
        '<span class="sub">' + esc(sub) + '</span></button></li>');
    });
    ul.innerHTML = html.join('') || '<li class="more">条件に合う漁業権はありません。</li>';
    document.getElementById('listCount').textContent = groups.size + 'か所';
  }

  function renderCounts(shown) {
    // counts reflect every filter except the dimension the chip itself controls
    function count(key, val) {
      var save = state[key];
      state[key] = new Set([val]);
      var n = all.filter(matches).length;
      state[key] = save;
      return n;
    }
    document.querySelectorAll('#regionChips .chip').forEach(function (b) { b.querySelector('.n').textContent = count('regions', b.dataset.v); });
    document.querySelectorAll('#groupChips .chip').forEach(function (b) { b.querySelector('.n').textContent = count('groups', b.dataset.v); });
    document.querySelectorAll('#accLegend input').forEach(function (i) { i.closest('label').querySelector('.n').textContent = count('acc', i.value); });
  }

  document.getElementById('list').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-loc]');
    if (!b) return;
    var m = locMarkers.get(b.dataset.loc);
    if (!m) return;
    map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 14), { duration: .6 });
    map.once('moveend', function () { m.openPopup(); });
    if (window.matchMedia('(max-width: 760px)').matches) setCollapsed(true);
  });

  // ------------------------------------------------------------ controls
  function chip(container, val, swatch, key) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'chip'; b.dataset.v = val; b.setAttribute('aria-pressed', 'true');
    b.innerHTML = (swatch ? '<span class="sw" style="background:' + swatch + '"></span>' : '') + esc(val) + ' <span class="n"></span>';
    b.addEventListener('click', function () {
      var s = state[key];
      if (s.has(val)) s.delete(val); else s.add(val);
      b.setAttribute('aria-pressed', s.has(val) ? 'true' : 'false');
      render();
    });
    container.appendChild(b);
  }
  REGIONS.forEach(function (r) { chip(document.getElementById('regionChips'), r, null, 'regions'); });
  GROUPS.forEach(function (g) {
    chip(document.getElementById('groupChips'), g.id, g.color, 'groups');
  });
  document.querySelectorAll('#groupChips .chip').forEach(function (b, i) { b.title = GROUPS[i].desc; });

  var accSvg = {
    exact: '<svg width="18" height="14" aria-hidden="true"><rect x="2" y="2" width="14" height="10" fill="#2a78d6" fill-opacity=".45" stroke="#2a78d6" stroke-width="2"/></svg>',
    approx: '<svg width="18" height="14" aria-hidden="true"><rect x="2" y="2" width="14" height="10" fill="#2a78d6" fill-opacity=".25" stroke="#2a78d6" stroke-width="2" stroke-dasharray="4 2"/></svg>',
    point: '<svg width="18" height="14" aria-hidden="true"><circle cx="9" cy="7" r="5" fill="#2a78d6" stroke="#fff" stroke-width="2"/></svg>',
    district: '<svg width="18" height="14" aria-hidden="true"><circle cx="9" cy="7" r="6" fill="none" stroke="#2a78d6" stroke-width="1.5" stroke-dasharray="3 2"/><circle cx="9" cy="7" r="2.5" fill="#2a78d6"/></svg>',
    none: '<svg width="18" height="14" aria-hidden="true"><path d="M5 3l8 8M13 3l-8 8" stroke="currentColor" stroke-width="1.5"/></svg>'
  };
  var accUl = document.getElementById('accLegend');
  ACC.forEach(function (a) {
    var li = document.createElement('li');
    li.innerHTML = '<label><input type="checkbox" value="' + a.id + '" checked>' + accSvg[a.id] + esc(a.label) + '<span class="n"></span></label>';
    li.querySelector('input').addEventListener('change', function (e) {
      if (e.target.checked) state.acc.add(a.id); else state.acc.delete(a.id);
      render();
    });
    accUl.appendChild(li);
  });

  var qTimer;
  document.getElementById('q').addEventListener('input', function (e) {
    clearTimeout(qTimer);
    qTimer = setTimeout(function () { state.q = e.target.value.trim(); render(); }, 150);
  });
  document.getElementById('nameSel').addEventListener('change', function (e) { state.name = e.target.value; render(); });

  var panel = document.getElementById('panel');
  var toggle = document.getElementById('panelToggle');
  function setCollapsed(c) {
    panel.classList.toggle('collapsed', c);
    toggle.setAttribute('aria-expanded', c ? 'false' : 'true');
    toggle.textContent = c ? '絞り込みと一覧を開く' : '閉じる';
    setTimeout(function () { map.invalidateSize(); }, 50);
  }
  toggle.addEventListener('click', function () { setCollapsed(!panel.classList.contains('collapsed')); });
  if (window.matchMedia('(max-width: 760px)').matches) setCollapsed(true);

  // ------------------------------------------------------------ load
  function init(data) {
    all = data.features;
    var names = new Map();
    all.forEach(function (f) { names.set(f.properties.name, (names.get(f.properties.name) || 0) + 1); });
    var sel = document.getElementById('nameSel');
    Array.from(names).sort(function (a, b) { return b[1] - a[1]; }).forEach(function (e) {
      var o = document.createElement('option');
      o.value = e[0]; o.textContent = e[0] + '（' + e[1] + '）';
      sel.appendChild(o);
    });
    render();
    var b = L.featureGroup([polyLayer, markerLayer]).getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [20, 20] });
  }
  if (window.FISHING_GROUNDS) init(window.FISHING_GROUNDS);
  else fetch('data/fishing_grounds.geojson').then(function (r) { return r.json(); }).then(init)
    .catch(function (err) {
      document.getElementById('list').innerHTML = '<li class="more">データを読み込めませんでした（' + esc(err.message) +
        '）。ローカルで開く場合は <code>python3 -m http.server</code> などでサーバー経由で表示してください。</li>';
    });
})();
