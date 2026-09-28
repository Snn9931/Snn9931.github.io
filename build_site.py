# -*- coding: utf-8 -*-
"""
Build a self-contained GitHub Pages site showing GitHub Chinese Top Charts.

Data source: https://github.com/ChHsiching/GitHub-Chinese-Top-Charts-Classified
  content/charts/{overall,growth,new_repo}/{software,knowledge}/*.md

Usage:
  python build_site.py [--data DIR] [--download] [--out PATH]
  --data DIR    read markdown files from a local directory (already extracted)
  --download    download the source tarball fresh
  --out PATH    output html path (default: ./index.html)
"""
import argparse
import base64
import gzip
import io
import json
import os
import re
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_URL = "https://github.com/ChHsiching/GitHub-Chinese-Top-Charts-Classified"
TARBALL_URL = "https://codeload.github.com/ChHsiching/GitHub-Chinese-Top-Charts-Classified/tar.gz/refs/heads/main"

CHART_LABELS = {"overall": "总榜", "growth": "增速榜", "new_repo": "新秀榜"}
CAT_LABELS = {"software": "软件类", "knowledge": "资料类"}
LANG_LABELS = {
    "All-Language": "全部语言",
    "CPP": "C++",
    "CSHARP": "C#",
    "Jupyter-Notebook": "Jupyter Notebook",
    "Objective-C": "Objective-C",
    "Vim-script": "Vim script",
}


def download_data(dest):
    os.makedirs(dest, exist_ok=True)
    print("Downloading tarball ...", flush=True)
    with urllib.request.urlopen(TARBALL_URL, timeout=180) as resp:
        data = resp.read()
    tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    for member in tf.getmembers():
        parts = member.name.split("/", 1)
        member.name = parts[1] if len(parts) == 2 else parts[0]
        tf.extract(member, dest)
    tf.close()
    return os.path.join(dest, "content", "charts")


def parse_md(path):
    """Parse one chart markdown file -> (date, header_cols, rows)."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"数据更新[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    date = m.group(1) if m else ""
    lines = text.splitlines()
    header_cols = []
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        if s.startswith("|#|") or s.startswith("|:-"):
            if s.startswith("|#|"):
                header_cols = [c.strip() for c in s.split("|")][1:-1]
            continue
        parts = [c.strip() for c in s.split("|")]
        if len(parts) != len(header_cols) + 2:
            continue
        fields = parts[1:-1]
        if not fields[0].isdigit():
            continue
        rows.append(fields)
    return date, header_cols, rows


def col_index(header_cols, names):
    for i, c in enumerate(header_cols):
        for n in names:
            if c.lower() == n.lower():
                return i
    return -1


def parse_repo_field(field):
    m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", field)
    if m:
        return m.group(1), m.group(2)
    return field, ""


def load_all_charts(charts_root):
    """Return {chart: {cat: {lang_label: rows}}}."""
    data = {}
    for chart in sorted(os.listdir(charts_root)):
        chart_dir = os.path.join(charts_root, chart)
        if not os.path.isdir(chart_dir):
            continue
        data[chart] = {}
        for cat in sorted(os.listdir(chart_dir)):
            cat_dir = os.path.join(chart_dir, cat)
            if not os.path.isdir(cat_dir):
                continue
            data[chart][cat] = {}
            for fn in sorted(os.listdir(cat_dir)):
                if not fn.endswith(".md"):
                    continue
                lang_file = fn[:-3]
                lang_label = LANG_LABELS.get(lang_file, lang_file)
                date, header_cols, rows = parse_md(os.path.join(cat_dir, fn))
                # column roles
                i_repo = col_index(header_cols, ["Repository"])
                i_desc = col_index(header_cols, ["Description"])
                i_stars = col_index(header_cols, ["Stars"])
                i_lang = col_index(header_cols, ["Language"])
                i_updated = col_index(header_cols, ["Updated"])
                i_extra = col_index(header_cols, ["Average daily growth", "Created"])
                out = []
                for fields in rows:
                    if i_repo < 0 or i_repo >= len(fields):
                        continue
                    name, url = parse_repo_field(fields[i_repo])
                    if not url:
                        continue
                    def val(i):
                        return fields[i] if 0 <= i < len(fields) else ""
                    stars = val(i_stars)
                    try:
                        stars_int = int(stars.replace(",", ""))
                    except ValueError:
                        stars_int = 0
                    row = {
                        "n": name,
                        "u": url,
                        "d": val(i_desc)[:90],
                        "s": stars_int,
                        "l": val(i_lang),
                        "up": val(i_updated),
                        "x": val(i_extra),
                    }
                    out.append(row)
                data[chart][cat][lang_label] = {"date": date, "rows": out}
    return data


def build_json(charts_root):
    all_data = load_all_charts(charts_root)
    dates = set()
    total = 0
    for chart, cats in all_data.items():
        for cat, langs in cats.items():
            for lang, item in langs.items():
                if item["date"]:
                    dates.add(item["date"])
                total += len(item["rows"])
    payload = {
        "meta": {
            "date": max(dates) if dates else "",
            "source": SOURCE_URL,
            "total": total,
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "chartLabels": CHART_LABELS,
            "catLabels": CAT_LABELS,
        },
        "charts": all_data,
    }
    return payload


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 中文项目排行榜</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230c111d'/%3E%3Cpath d='M14 42h8V26h-8zm14 0h8V18h-8zm14 0h8V30h-8z' fill='%233fb950'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#0c111d; --panel:#131a2b; --panel2:#182136; --border:#232e47;
  --text:#e7edf8; --muted:#8b98b3; --accent:#3fb950; --accent-soft:rgba(63,185,80,.13);
  --gold:#e3b341; --silver:#b9c4d4; --bronze:#c98a4d; --danger:#f0887d;
  --mono:ui-monospace,"Cascadia Code",Consolas,"Courier New",monospace;
  --sans:"Segoe UI","Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.55;font-size:15px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.topbar{position:sticky;top:0;z-index:20;background:rgba(12,17,29,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}
.topbar-inner{max-width:1240px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.brand svg{flex:none}
.brand h1{margin:0;font-size:19px;font-weight:700;letter-spacing:.2px}
.brand .sub{margin:2px 0 0;font-size:12.5px;color:var(--muted)}
.stats{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:6px 12px;text-align:center}
.stat b{display:block;font-family:var(--mono);font-size:15px;font-variant-numeric:tabular-nums}
.stat span{font-size:11px;color:var(--muted)}
main{max-width:1240px;margin:0 auto;padding:18px 20px 40px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.seg{display:inline-flex;background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.seg button{appearance:none;border:0;background:transparent;color:var(--muted);font:inherit;font-size:13.5px;padding:8px 16px;cursor:pointer;transition:background .15s,color .15s}
.seg button.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.field{display:flex;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:0 12px}
.field svg{flex:none;color:var(--muted)}
.field input{background:transparent;border:0;color:var(--text);font:inherit;font-size:13.5px;padding:9px 0;width:200px;outline:none}
.field input::placeholder{color:var(--muted)}
select{appearance:none;background:var(--panel) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%238b98b3'/%3E%3C/svg%3E") no-repeat right 10px center;border:1px solid var(--border);color:var(--text);font:inherit;font-size:13.5px;border-radius:10px;padding:8px 30px 8px 12px;cursor:pointer}
select:focus-visible{outline:2px solid var(--accent)}
.card{background:var(--panel);border:1px solid var(--border);border-radius:14px;margin-bottom:16px;overflow:hidden}
.card-head{display:flex;align-items:baseline;gap:12px;padding:14px 18px 0;flex-wrap:wrap}
.card-head h2{margin:0;font-size:15px;font-weight:600}
.card-head .meta{font-size:12px;color:var(--muted)}
#chartBox{height:330px;padding:6px 12px 10px}
.chart-fallback{padding:60px 20px;text-align:center;color:var(--muted);font-size:13px}
.table-wrap{overflow-x:auto;padding:0 8px 8px}
table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:13.5px}
thead th{position:sticky;top:57px;background:var(--panel2);color:var(--muted);font-weight:600;font-size:12px;text-align:left;padding:9px 12px;border-bottom:1px solid var(--border);z-index:10}
tbody td{padding:9px 12px;border-bottom:1px solid rgba(35,46,71,.55);vertical-align:top;overflow:hidden}
tbody tr:hover td{background:rgba(63,185,80,.05)}
td.rank{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--muted)}
td.rank .medal{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;font-family:var(--mono);font-weight:700;font-size:12px}
.medal.gold{background:rgba(227,179,65,.16);color:var(--gold)}
.medal.silver{background:rgba(185,196,212,.16);color:var(--silver)}
.medal.bronze{background:rgba(201,138,77,.18);color:var(--bronze)}
td.repo{font-weight:600;word-break:break-all}
td.desc{color:var(--muted);font-size:12.5px;word-break:break-word}
td.stars{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--text);font-weight:600}
td.lang{font-size:12px}
.lang-chip{display:inline-block;background:var(--panel2);border:1px solid var(--border);border-radius:999px;padding:1px 8px;font-size:11.5px;color:var(--muted)}
td.up{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px;color:var(--muted);white-space:nowrap}
td.extra{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px;color:var(--accent)}
.empty{padding:48px 20px;text-align:center;color:var(--muted);font-size:13.5px}
footer{max-width:1240px;margin:0 auto;padding:0 20px 30px;color:var(--muted);font-size:12.5px}
footer .rules{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 18px;margin-bottom:12px}
footer .rules b{color:var(--text);font-weight:600}
@media (max-width:900px){
  .brand h1{font-size:17px}
  .field input{width:130px}
  .col-desc{display:none}
}
@media (max-width:640px){
  body{font-size:15px}
  .brand .sub{font-size:13px}
  .stat span{font-size:12px}
  .topbar-inner{padding:12px 14px}
  main{padding:14px 12px 28px}
  .controls{gap:8px}
  .seg button{padding:10px 13px;font-size:13px}
  .field input{width:96px;font-size:16px}
  select{font-size:13px}
  #chartBox{height:260px}
  .col-lang{display:none}
  table{font-size:13px}
  thead th, tbody td{padding:8px 10px}
  td.repo{font-size:13px}
  td.rank{font-size:12px}
  td.up{font-size:12px}
  td.extra{font-size:12px}
}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#131a2b" stroke="#232e47"/><path d="M14 42h8V26h-8zm14 0h8V18h-8zm14 0h8V30h-8z" fill="#3fb950"/></svg>
      <div>
        <h1>GitHub 中文项目排行榜</h1>
        <p class="sub" id="headerSub"></p>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><b id="stTotal"></b><span>收录项目</span></div>
      <div class="stat"><b id="stRows"></b><span>当前榜单</span></div>
      <div class="stat"><b id="stLang"></b><span>语言分榜</span></div>
    </div>
  </div>
</header>
<main>
  <section class="controls" aria-label="榜单筛选">
    <div class="seg" id="chartTabs" role="tablist"></div>
    <div class="seg" id="catTabs" role="tablist"></div>
    <select id="langSel" aria-label="选择语言"></select>
    <label class="field" aria-label="搜索">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="search" type="search" placeholder="搜索项目 / 描述 / 作者" autocomplete="off">
    </label>
    <select id="sortSel" aria-label="排序方式">
      <option value="rank">按排名</option>
      <option value="stars">Stars 从高到低</option>
    </select>
  </section>

  <section class="card" aria-label="Stars 排行图">
    <div class="card-head">
      <h2 id="chartTitle">Top 15 · Stars</h2>
      <span class="meta" id="chartSub"></span>
    </div>
    <div id="chartBox"></div>
    <div class="chart-fallback" id="chartFallback" hidden>图表组件加载失败，表格数据不受影响。</div>
  </section>

  <section class="card" aria-label="排行榜表格">
    <div class="card-head">
      <h2 id="listTitle"></h2>
      <span class="meta" id="listMeta"></span>
    </div>
    <div class="table-wrap">
      <table id="rankTable"></table>
    </div>
  </section>
</main>
<footer>
  <div class="rules">
    <b>入选规则</b>：项目描述与 README 含中文说明 · 近半年内有更新 · 按 Stars 排序（榜单每周更新）。
    数据来自 <a id="srcLink" href="" target="_blank" rel="noopener"></a>，本页生成于 <span id="genAt"></span>。
  </div>
</footer>
<script>
const CHARTS_B64 = "__JSON_DATA__";
async function loadCharts() {
  const bin = Uint8Array.from(atob(CHARTS_B64), (c) => c.charCodeAt(0));
  if (typeof DecompressionStream === "undefined") throw new Error("browser too old");
  const stream = new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
</script>
<script>
(async () => {
  const CHARTS = await loadCharts();
  const M = CHARTS.meta;
  const $ = (id) => document.getElementById(id);
  const chartTabs = $("chartTabs"), catTabs = $("catTabs"), langSel = $("langSel");
  const search = $("search"), sortSel = $("sortSel");
  let tbodyHost = $("rankTable");
  const state = { chart: "overall", cat: "software", lang: "全部语言", q: "", sort: "rank" };

  const esc = (s) => { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; };

  /* ---------- header meta ---------- */
  $("headerSub").textContent = "数据更新 " + M.date + " · 来源 " + M.source.replace("https://github.com/", "") + " · 每周更新";
  $("stTotal").textContent = M.total >= 1000 ? (M.total / 1000).toFixed(1) + "k" : M.total;
  $("srcLink").textContent = M.source.replace("https://github.com/", "");
  $("srcLink").href = M.source;
  $("genAt").textContent = M.generated;

  /* ---------- controls ---------- */
  function buildTabs(host, keys, labelOf, current, onPick) {
    host.innerHTML = "";
    keys.forEach((k) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = labelOf[k];
      if (k === current) b.classList.add("active");
      b.addEventListener("click", () => onPick(k));
      host.appendChild(b);
    });
  }
  buildTabs(chartTabs, ["overall", "growth", "new_repo"], M.chartLabels, state.chart, (k) => { state.chart = k; state.lang = "全部语言"; refresh(true); });
  buildTabs(catTabs, ["software", "knowledge"], M.catLabels, state.cat, (k) => { state.cat = k; state.lang = "全部语言"; refresh(true); });

  function buildLangSel() {
    const langs = Object.keys(CHARTS.charts[state.chart][state.cat]);
    langSel.innerHTML = "";
    langs.forEach((l) => {
      const o = document.createElement("option");
      o.value = l; o.textContent = l;
      langSel.appendChild(o);
    });
    langSel.value = state.lang;
  }
  langSel.addEventListener("change", () => { state.lang = langSel.value; refresh(true); });
  search.addEventListener("input", () => { state.q = search.value.trim().toLowerCase(); refresh(false); });
  sortSel.addEventListener("change", () => { state.sort = sortSel.value; refresh(false); });

  /* ---------- data ---------- */
  function currentRows() {
    let rows = (CHARTS.charts[state.chart][state.cat][state.lang] || {}).rows || [];
    if (state.q) {
      rows = rows.filter((r) =>
        r.n.toLowerCase().includes(state.q) || r.d.toLowerCase().includes(state.q) || r.u.toLowerCase().includes(state.q)
      );
    }
    const copy = rows.slice();
    if (state.sort === "stars") copy.sort((a, b) => b.s - a.s);
    return copy;
  }
  const fmtStars = (s) => s >= 1000 ? (s / 1000).toFixed(s >= 10000 ? 1 : 2).replace(/\.0$/, "") + "k" : String(s);
  const chartName = () => M.chartLabels[state.chart] + " · " + M.catLabels[state.cat] + " · " + state.lang;
  const extraCols = { growth: { label: "日增", key: "x" }, new_repo: { label: "创建", key: "x" } };
  const extra = extraCols[state.chart] || null;

  /* ---------- table ---------- */
  function renderTable(rows) {
    $("listTitle").textContent = chartName();
    $("listMeta").textContent = "共 " + rows.length + " 个项目" + (state.q ? "（筛选后）" : "");
    $("stRows").textContent = rows.length;
    const cols = [
      { t: "#", c: "col-rank" }, { t: "仓库", c: "col-repo" }, { t: "描述", c: "col-desc" },
      { t: "Stars", c: "col-stars" }
    ];
    if (extra) cols.splice(4, 0, { t: extra.label, c: "col-extra" });
    cols.push({ t: "语言", c: "col-lang" }, { t: "更新", c: "col-up" });
    const vw = window.innerWidth;
    const widths = (extra
      ? (vw <= 640 ? [12, 38, 0, 17, 11, 0, 22] : vw <= 900 ? [6, 26, 0, 14, 11, 15, 28] : [5, 22, 33, 10, 8, 9, 13])
      : (vw <= 640 ? [12, 43, 0, 21, 0, 0, 24] : vw <= 900 ? [7, 30, 0, 16, 0, 16, 31] : [5, 24, 37, 11, 0, 10, 13]));
    const order = ["col-rank", "col-repo", "col-desc", "col-stars", "col-extra", "col-lang", "col-up"];
    const colHtml = cols.map((o) => '<col style="width:' + widths[order.indexOf(o.c)] + '%">').join("");
    const thHtml = cols.map((o) => '<th class="' + o.c + '">' + o.t + "</th>").join("");
    const frag = document.createDocumentFragment();
    const table = document.createElement("table");
    table.innerHTML = colHtml + "<thead><tr>" + thHtml + "</tr></thead><tbody></tbody>";
    const tb = table.tBodies[0];
    const rankFmt = (i) => {
      if (vw <= 640) return i + 1;
      if (i === 0) return '<span class="medal gold">1</span>';
      if (i === 1) return '<span class="medal silver">2</span>';
      if (i === 2) return '<span class="medal bronze">3</span>';
      return i + 1;
    };
    const fmtUp = (d) => (vw <= 640 && d && d.length === 10 ? d.slice(2) : d);
    rows.forEach((r, i) => {
      const tr = document.createElement("tr");
      const cells = [];
      cells.push('<td class="rank col-rank">' + rankFmt(i) + "</td>");
      cells.push('<td class="repo col-repo"><a href="' + esc(r.u) + '" target="_blank" rel="noopener">' + esc(r.n) + "</a></td>");
      cells.push('<td class="desc col-desc">' + esc(r.d) + "</td>");
      cells.push('<td class="stars col-stars">' + fmtStars(r.s) + "</td>");
      if (extra) cells.push('<td class="extra col-extra">' + esc(r.x || "-") + "</td>");
      cells.push('<td class="lang col-lang"><span class="lang-chip">' + esc(r.l || "-") + "</span></td>");
      cells.push('<td class="up col-up">' + esc(fmtUp(r.up)) + "</td>");
      tr.innerHTML = cells.join("");
      tb.appendChild(tr);
    });
    if (!rows.length) {
      tb.innerHTML = '<tr><td colspan="' + cols.length + '"><div class="empty">没有匹配的项目，换个关键词试试。</div></td></tr>';
    }
    tbodyHost.replaceWith(table);
    tbodyHost = table;
  }

  /* ---------- chart ---------- */
  let chart = null;
  const chartBox = $("chartBox"), chartFallback = $("chartFallback");
  function loadECharts() {
    return new Promise((res, rej) => {
      if (window.echarts) return res(window.echarts);
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js";
      s.onload = () => res(window.echarts);
      s.onerror = () => rej(new Error("cdn failed"));
      document.head.appendChild(s);
    });
  }
  function drawChart(rows) {
    const top = rows.slice().sort((a, b) => b.s - a.s).slice(0, 15);
    if (!chart) return;
    if (!top.length) { chart.clear(); return; }
    const names = top.map((r) => r.n.split("/")[1] || r.n);
    const stars = top.map((r) => r.s);
    chart.setOption({
      animationDuration: 300,
      grid: { left: 8, right: 46, top: 10, bottom: 6, containLabel: true },
      xAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(35,46,71,.6)" } }, axisLabel: { color: "#8b98b3", fontSize: 11, formatter: (v) => v >= 1000 ? v / 1000 + "k" : v } },
      yAxis: { type: "category", inverse: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#c9d3e4", fontSize: 11.5, width: 150, overflow: "truncate" }, data: names },
      series: [{
        type: "bar", data: stars, barMaxWidth: 14,
        itemStyle: { color: "#3fb950", borderRadius: [0, 6, 6, 0] },
        label: { show: true, position: "right", color: "#8b98b3", fontSize: 11, fontFamily: "Consolas,monospace", formatter: (p) => p.value >= 1000 ? (p.value / 1000).toFixed(1) + "k" : p.value }
      }]
    });
  }
  function refreshChart(rows) {
    $("chartSub").textContent = chartName();
    loadECharts().then((ec) => {
      chartFallback.hidden = true;
      if (!chart) { chart = ec.init(chartBox); window.addEventListener("resize", () => chart.resize()); }
      drawChart(rows);
    }).catch(() => {
      if (chartBox.firstChild) chartBox.innerHTML = "";
      chartFallback.hidden = false;
    });
  }

  /* ---------- refresh ---------- */
  function refresh(reInitLang) {
    if (reInitLang) buildLangSel();
    $("stLang").textContent = Object.keys(CHARTS.charts[state.chart][state.cat]).length;
    const rows = currentRows();
    renderTable(rows);
    refreshChart(rows);
  }
  refresh(true);

  /* re-render table only when crossing a breakpoint */
  let lastBr = window.innerWidth <= 640 ? 0 : window.innerWidth <= 900 ? 1 : 2;
  window.addEventListener("resize", () => {
    const now = window.innerWidth;
    const br = now <= 640 ? 0 : now <= 900 ? 1 : 2;
    if (br !== lastBr) { lastBr = br; renderTable(currentRows()); }
  });
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    work = os.path.join(HERE, "_work")
    if args.data:
        charts_root = os.path.join(args.data, "content", "charts") if os.path.isdir(args.data) else args.data
    elif args.download:
        charts_root = download_data(os.path.join(work, "classified"))
    else:
        local = os.path.join(work, "classified", "content", "charts")
        charts_root = local if os.path.isdir(local) else download_data(os.path.join(work, "classified"))

    payload = build_json(charts_root)
    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    gz = gzip.compress(json_str.encode("utf-8"))
    b64 = base64.b64encode(gz).decode("ascii")
    html = HTML_TEMPLATE.replace("__JSON_DATA__", b64)

    out = args.out or os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Rows:", M_total(payload))
    print("JSON size:", len(json_str), "bytes")
    print("GZIP size:", len(gz), "bytes")
    print("HTML size:", len(html.encode("utf-8")), "bytes")
    print("Output:", out)


def M_total(payload):
    n = 0
    for chart, cats in payload["charts"].items():
        for cat, langs in cats.items():
            for lang, item in langs.items():
                n += len(item["rows"])
    return n


if __name__ == "__main__":
    main()
