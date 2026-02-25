import feedparser
import requests
import re
import html as html_module
from datetime import datetime
from email.utils import parsedate_to_datetime
import warnings

warnings.filterwarnings('ignore')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

FEEDS_NACIONALES = [
    {"name": "Ámbito",    "url": "https://www.ambito.com/rss/pages/economia.xml",                     "color": "#2563eb"},
    {"name": "La Nación", "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", "color": "#7c3aed"},
    {"name": "Infobae",   "url": "https://www.infobae.com/feeds/rss/economia/",                       "color": "#e63946"},
]

FEEDS_INTERNACIONALES = [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex",               "color": "#6d28d9"},
    {"name": "MarketWatch",   "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "color": "#0891b2"},
    {"name": "CNBC",          "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "color": "#dc2626"},
]


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text).strip()


def fetch_feed(feed_info, max_items=5):
    try:
        resp = requests.get(feed_info["url"], headers=HEADERS, timeout=15)
        parsed = feedparser.parse(resp.content)
        entries = []
        for entry in parsed.entries[:max_items]:
            title   = html_module.unescape(strip_html(entry.get("title", "Sin título")))
            link    = entry.get("link", "#")
            summary = html_module.unescape(strip_html(
                entry.get("summary", entry.get("description", ""))
            ))
            summary = summary[:220] + "…" if len(summary) > 220 else summary

            pub_date = entry.get("published", entry.get("updated", ""))
            try:
                dt       = parsedate_to_datetime(pub_date)
                date_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                date_str = ""

            entries.append({
                "title":   title,
                "link":    link,
                "summary": summary,
                "date":    date_str,
                "source":  feed_info["name"],
                "color":   feed_info["color"],
            })
        return entries
    except Exception as e:
        print(f"  ✗ Error en {feed_info['name']}: {e}")
        return []


def translate_es(text):
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target='es').translate(text)
    except Exception:
        return text


# ── Fetch ──────────────────────────────────────────────────────────────────────
print("Obteniendo noticias nacionales...")
noticias_nac = []
for feed in FEEDS_NACIONALES:
    items = fetch_feed(feed)
    noticias_nac.extend(items)
    print(f"  {'✓' if items else '✗'} {feed['name']}: {len(items)} artículos")

print("Obteniendo noticias internacionales...")
noticias_int = []
for feed in FEEDS_INTERNACIONALES:
    items = fetch_feed(feed)
    noticias_int.extend(items)
    print(f"  {'✓' if items else '✗'} {feed['name']}: {len(items)} artículos")

noticias_nac = noticias_nac[:15]
noticias_int = noticias_int[:15]

# ── Traducir top 3 internacionales para destacadas ─────────────────────────────
print("Traduciendo destacadas internacionales...")
dest_int = []
for n in noticias_int[:3]:
    traducido = dict(n)
    traducido['title']   = translate_es(n['title'])
    traducido['summary'] = translate_es(n['summary'])
    dest_int.append(traducido)
    print(f"  ✓ {traducido['source']}: traducido")

now_str  = datetime.utcnow().strftime('%Y-%m-%d  %H:%M UTC')
date_str = datetime.utcnow().strftime('%Y-%m-%d')


# ── HTML builders ──────────────────────────────────────────────────────────────
def build_destacadas(items, numerar=True):
    if not items:
        return '<p class="empty-msg">Sin noticias disponibles.</p>'
    cards = []
    for i, n in enumerate(items, 1):
        c = n["color"]
        num = f'<span class="dest-num">{i}</span>' if numerar else ''
        cards.append(f"""
        <a class="dest-card" href="{n['link']}" target="_blank" rel="noopener noreferrer">
          {num}
          <div class="dest-body">
            <div class="news-meta">
              <span class="source-badge" style="color:{c};background:{c}18;border-color:{c}35;">{n['source']}</span>
              <span class="news-date">{n['date']}</span>
            </div>
            <div class="dest-title">{n['title']}</div>
            <div class="news-summary">{n['summary']}</div>
          </div>
        </a>""")
    return '\n'.join(cards)


def build_cards(noticias):
    if not noticias:
        return '<p class="empty-msg">No se pudieron cargar noticias en este momento.</p>'
    cards = []
    for n in noticias:
        c = n["color"]
        cards.append(f"""
        <a class="news-card" href="{n['link']}" target="_blank" rel="noopener noreferrer">
          <div class="news-meta">
            <span class="source-badge" style="color:{c};background:{c}18;border-color:{c}35;">{n['source']}</span>
            <span class="news-date">{n['date']}</span>
          </div>
          <div class="news-title">{n['title']}</div>
          <div class="news-summary">{n['summary']}</div>
          <span class="read-more">Leer nota →</span>
        </a>""")
    return '\n'.join(cards)


html_dest_nac = build_destacadas(noticias_nac[:3])
html_dest_int = build_destacadas(dest_int)
html_nac      = build_cards(noticias_nac)
html_int      = build_cards(noticias_int)

fuentes_nac = " · ".join(f["name"] for f in FEEDS_NACIONALES)
fuentes_int = " · ".join(f["name"] for f in FEEDS_INTERNACIONALES)

# ── HTML ───────────────────────────────────────────────────────────────────────
html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Noticias Financieras</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg:#f1f5f9;--surface:#fff;--border:#e2e8f0;--text-main:#0f172a;--text-muted:#64748b;
      --blue:#3b82f6;--slate:#94a3b8;
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text-main);padding:28px 20px 60px;line-height:1.6;}}
    .page-wrap{{max-width:1380px;margin:0 auto;}}

    /* HEADER */
    .page-header{{margin-bottom:32px;padding-bottom:20px;border-bottom:2px solid var(--border);}}
    .page-header h1{{font-size:1.9rem;font-weight:600;letter-spacing:-0.03em;}}
    .page-header h1 span{{color:var(--blue);}}
    .back-link{{font-size:0.82rem;color:var(--blue);text-decoration:none;font-family:'DM Mono',monospace;display:inline-flex;align-items:center;gap:6px;margin-bottom:10px;}}
    .back-link:hover{{text-decoration:underline;}}

    /* SECCIÓN DESTACADAS */
    .section-label{{display:flex;align-items:center;gap:12px;margin-bottom:16px;}}
    .section-label span{{font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:1.2px;color:var(--slate);white-space:nowrap;font-family:'DM Mono',monospace;}}
    .section-label::after{{content:'';flex:1;height:1px;background:var(--border);}}
    .dest-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:40px;}}
    .dest-col-title{{font-size:0.88rem;font-weight:600;margin-bottom:12px;color:var(--text-main);}}
    .dest-card{{display:flex;gap:14px;align-items:flex-start;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin-bottom:10px;text-decoration:none;color:inherit;transition:box-shadow .15s,border-color .15s;}}
    .dest-card:hover{{box-shadow:0 4px 16px rgba(0,0,0,0.07);border-color:#bfdbfe;}}
    .dest-num{{font-size:1.4rem;font-weight:700;font-family:'DM Mono',monospace;color:#cbd5e1;line-height:1;padding-top:2px;flex-shrink:0;min-width:24px;}}
    .dest-body{{flex:1;min-width:0;}}
    .dest-title{{font-size:0.92rem;font-weight:600;color:var(--text-main);line-height:1.4;margin-bottom:6px;}}

    /* GRID DE COLUMNAS */
    .news-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;}}
    @media(max-width:900px){{.news-grid{{grid-template-columns:1fr;}}.dest-grid{{grid-template-columns:1fr;}}}}

    /* COLUMNA */
    .news-col{{display:flex;flex-direction:column;gap:0;}}
    .col-header{{display:flex;align-items:center;gap:10px;margin-bottom:12px;}}
    .col-title{{font-size:1rem;font-weight:600;}}
    .col-count{{font-size:0.72rem;font-family:'DM Mono',monospace;background:#eff6ff;color:var(--blue);border:1px solid #bfdbfe;border-radius:99px;padding:2px 10px;margin-left:auto;}}
    .col-sources{{font-size:0.73rem;color:var(--slate);margin-bottom:14px;font-family:'DM Mono',monospace;}}

    /* CARD */
    .news-card{{display:block;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin-bottom:10px;text-decoration:none;color:inherit;transition:box-shadow .15s,border-color .15s;}}
    .news-card:hover{{box-shadow:0 4px 16px rgba(0,0,0,0.07);border-color:#bfdbfe;}}
    .news-meta{{display:flex;align-items:center;gap:8px;margin-bottom:8px;}}
    .source-badge{{font-size:0.68rem;font-weight:600;font-family:'DM Mono',monospace;border:1px solid;border-radius:99px;padding:2px 9px;white-space:nowrap;}}
    .news-date{{font-size:0.72rem;color:var(--slate);font-family:'DM Mono',monospace;margin-left:auto;white-space:nowrap;}}
    .news-title{{font-size:0.9rem;font-weight:600;color:var(--text-main);margin-bottom:6px;line-height:1.4;}}
    .news-summary{{font-size:0.79rem;color:var(--text-muted);line-height:1.55;margin-bottom:10px;}}
    .read-more{{font-size:0.72rem;color:var(--blue);font-family:'DM Mono',monospace;font-weight:500;}}
    .empty-msg{{color:var(--slate);font-size:0.88rem;padding:20px 0;}}

    /* FOOTER */
    .page-footer{{text-align:center;margin-top:48px;font-size:0.78rem;color:var(--slate);font-family:'DM Mono',monospace;}}
  </style>
</head>
<body>
<div class="page-wrap">

  <header class="page-header">
    <a class="back-link" href="../index.html">← Volver al inicio</a>
    <h1>Noticias <span>Financieras</span></h1>
  </header>

  <!-- DESTACADAS -->
  <div class="section-label"><span>Lo más importante</span></div>
  <div class="dest-grid">
    <div>
      <div class="dest-col-title">🇦🇷 Nacionales</div>
      {html_dest_nac}
    </div>
    <div>
      <div class="dest-col-title">🌎 Internacionales</div>
      {html_dest_int}
    </div>
  </div>

  <!-- TODAS LAS NOTICIAS -->
  <div class="section-label"><span>Todas las noticias</span></div>
  <div class="news-grid">

    <div class="news-col">
      <div class="col-header">
        <span class="col-title">🇦🇷 Nacionales</span>
        <span class="col-count">{len(noticias_nac)} artículos</span>
      </div>
      <div class="col-sources">Fuentes: {fuentes_nac}</div>
      {html_nac}
    </div>

    <div class="news-col">
      <div class="col-header">
        <span class="col-title">🌎 Internacionales</span>
        <span class="col-count">{len(noticias_int)} artículos</span>
      </div>
      <div class="col-sources">Fuentes: {fuentes_int}</div>
      {html_int}
    </div>

  </div>

  <footer class="page-footer">
    Fuentes: RSS públicos de medios financieros &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; Solo con fines informativos
  </footer>

</div>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"\nDashboard de noticias generado: {now_str}")
print(f"  Nacional: {len(noticias_nac)} artículos  |  Internacional: {len(noticias_int)} artículos")
