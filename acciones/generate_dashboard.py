import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

BASE_URL = "https://data912.com"

TICKERS_ARG = [
    'ALUA', 'BBAR', 'BMA', 'BYMA', 'CEPU', 'COME', 'CRES', 'CVH',
    'EDN', 'GGAL', 'LOMA', 'MIRG', 'PAMP', 'SUPV', 'TECO2', 'TGNO4',
    'TGSU2', 'TRAN', 'TXAR', 'VALO', 'YPFD', 'AGRO', 'BHIP', 'BOLT',
    'BPAT', 'CGPA2', 'CTIO', 'DGCE', 'FERR', 'HARG', 'INVJ', 'LEDE',
    'LONG', 'METR', 'MOLA', 'MOLI', 'MORI', 'OEST', 'RICH', 'SAMI'
]

def fetch_ticker(ticker, max_retries=3):
    url = f"{BASE_URL}/historical/stocks/{ticker}"
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            df = pd.DataFrame(data)
            df['ticker'] = ticker
            df['date'] = pd.to_datetime(df['date'])
            df = df.rename(columns={
                'o': 'open', 'h': 'high', 'l': 'low',
                'c': 'close', 'v': 'volume',
                'dr': 'daily_return'
            })
            return df.sort_values('date').reset_index(drop=True)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
    return None

def load_all_tickers(tickers, delay=0.4):
    frames = []
    for tk in tickers:
        df = fetch_ticker(tk)
        if df is not None and not df.empty:
            frames.append(df)
        time.sleep(delay)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

df_raw = load_all_tickers(TICKERS_ARG)

if df_raw.empty:
    raise ValueError("No se pudieron descargar datos")

metrics_rows = []
for tk, g in df_raw.groupby('ticker'):
    g = g.sort_values('date').copy()
    close = g['close'].values
    vol = g['volume'].values
    if len(close) < 2:
        continue
    close_last = close[-1]
    close_prev = close[-2]
    daily_ret = ((close_last / close_prev) - 1) * 100
    date_last = g['date'].iloc[-1]
    vol_last = vol[-1]
    vol_avg20 = np.mean(vol[-21:-1]) if len(vol) > 21 else np.mean(vol[:-1])
    vol_rel20 = (vol_last / vol_avg20) if vol_avg20 > 0 else np.nan
    metrics_rows.append({
        'ticker': tk,
        'close_last': round(close_last, 2),
        'date_last': date_last,
        'daily_ret': round(daily_ret, 2),
        'volume_last': int(vol_last),
        'vol_rel20': round(vol_rel20, 2),
    })

metrics = pd.DataFrame(metrics_rows).dropna(subset=['daily_ret'])

total_stocks = len(metrics)
advances = len(metrics[metrics['daily_ret'] > 0])
declines = len(metrics[metrics['daily_ret'] < 0])
unchanged = total_stocks - advances - declines
ad_ratio = advances / declines if declines > 0 else float('inf')
avg_change = metrics['daily_ret'].mean()
median_change = metrics['daily_ret'].median()
std_change = metrics['daily_ret'].std()

top_gainers = metrics.nlargest(15, 'daily_ret')[['ticker', 'close_last', 'daily_ret', 'volume_last', 'vol_rel20']].copy()
top_losers = metrics.nsmallest(15, 'daily_ret')[['ticker', 'close_last', 'daily_ret', 'volume_last', 'vol_rel20']].copy()

if ad_ratio >= 2.0 and avg_change >= 0.5:
    market_sentiment = "Alcista amplio"
    sentiment_color = "#22c55e"
elif ad_ratio >= 1.2 and avg_change >= 0:
    market_sentiment = "Alcista moderado"
    sentiment_color = "#86efac"
elif ad_ratio <= 0.5 and avg_change <= -0.5:
    market_sentiment = "Bajista amplio"
    sentiment_color = "#ef4444"
elif ad_ratio <= 0.8 and avg_change <= 0:
    market_sentiment = "Bajista moderado"
    sentiment_color = "#fca5a5"
else:
    market_sentiment = "Mixto / Sin tendencia"
    sentiment_color = "#94a3b8"

def build_summary():
    lines = []
    lines.append(
        f"Panel General de acciones argentinas: {total_stocks} instrumentos analizados, "
        f"{advances} alcistas / {declines} bajistas (ratio A/D {ad_ratio:.2f}), "
        f"cambio promedio {avg_change:+.2f}%."
    )
    if ad_ratio >= 1.5:
        lines.append("Amplitud positiva: más de la mitad del panel en verde.")
    elif ad_ratio <= 0.67:
        lines.append("Amplitud negativa: deterioro generalizado en el panel.")
    else:
        lines.append("Amplitud mixta: movimiento sin dirección dominante.")
    top_gain = metrics.loc[metrics['daily_ret'].idxmax()]
    top_loss = metrics.loc[metrics['daily_ret'].idxmin()]
    lines.append(
        f"Mayor ganador: {top_gain['ticker']} ({top_gain['daily_ret']:+.2f}%). "
        f"Mayor perdedor: {top_loss['ticker']} ({top_loss['daily_ret']:+.2f}%)."
    )
    return " ".join(lines)

executive_summary = build_summary()

PALETTE_POS = "#3b82f6"
PALETTE_NEG = "#f97316"
PALETTE_NEUT = "#94a3b8"

df_plot = metrics.sort_values('daily_ret', ascending=False).reset_index(drop=True)
n = len(df_plot)
cols_grid = 8
rows_grid = int(np.ceil(n / cols_grid))

z_matrix = np.full((rows_grid, cols_grid), np.nan)
text_matrix = [['' for _ in range(cols_grid)] for _ in range(rows_grid)]
hover_matrix = [['' for _ in range(cols_grid)] for _ in range(rows_grid)]

for i, row in df_plot.iterrows():
    col_i = i % cols_grid
    row_i = i // cols_grid
    val = row['daily_ret']
    z_matrix[row_i, col_i] = val
    text_matrix[row_i][col_i] = f"{row['ticker']}<br>{val:+.1f}%"
    hover_matrix[row_i][col_i] = (
        f"<b>{row['ticker']}</b><br>"
        f"Cambio: {val:+.2f}%<br>"
        f"Precio: ${row['close_last']:.2f}<br>"
        f"Vol Rel: {row['vol_rel20']:.2f}x"
    )

fig_heatmap = go.Figure(data=go.Heatmap(
    z=z_matrix,
    text=text_matrix,
    hovertext=hover_matrix,
    hoverinfo='text',
    texttemplate='%{text}',
    textfont=dict(size=10, family="monospace", color="white"),
    colorscale='RdYlGn',
    zmid=0,
    colorbar=dict(title=dict(text="Cambio %", side="right")),
    showscale=True
))

fig_heatmap.update_layout(
    title="Heatmap de Variaciones",
    xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
    yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
    height=450,
    plot_bgcolor='#161b22',
    paper_bgcolor='#0d1117',
    font=dict(family='DM Sans, sans-serif', color='#e6edf3'),
    margin=dict(l=20, r=20, t=60, b=20)
)

html_heatmap = fig_heatmap.to_html(include_plotlyjs='cdn', div_id='heatmap', config={'displayModeBar': True, 'displaylogo': False})

fig_breadth = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Distribución de Cambios", "Market Breadth"),
    specs=[[{"type": "histogram"}, {"type": "bar"}]],
    horizontal_spacing=0.12
)

fig_breadth.add_trace(
    go.Histogram(
        x=metrics['daily_ret'],
        nbinsx=35,
        marker_color=PALETTE_POS,
        opacity=0.75,
        name='Frecuencia',
        hovertemplate='Cambio: %{x:.2f}%<br>Cantidad: %{y}<extra></extra>'
    ),
    row=1, col=1
)

fig_breadth.add_vline(x=avg_change, line_dash="dash", line_color="#8b949e", line_width=2, 
                      annotation_text=f"Media: {avg_change:+.2f}%", row=1, col=1)
fig_breadth.add_vline(x=median_change, line_dash="dot", line_color=PALETTE_NEG, line_width=1.5,
                      annotation_text=f"Mediana: {median_change:+.2f}%", row=1, col=1)

fig_breadth.add_trace(
    go.Bar(
        y=['Market'],
        x=[advances],
        orientation='h',
        marker_color=PALETTE_POS,
        name=f'Alcistas ({advances})',
        text=[f'{advances}'],
        textposition='inside',
        hovertemplate='Alcistas: %{x}<extra></extra>'
    ),
    row=1, col=2
)

fig_breadth.add_trace(
    go.Bar(
        y=['Market'],
        x=[unchanged],
        orientation='h',
        marker_color=PALETTE_NEUT,
        name=f'Sin cambio ({unchanged})',
        text=[f'{unchanged}'],
        textposition='inside',
        hovertemplate='Sin cambio: %{x}<extra></extra>'
    ),
    row=1, col=2
)

fig_breadth.add_trace(
    go.Bar(
        y=['Market'],
        x=[declines],
        orientation='h',
        marker_color=PALETTE_NEG,
        name=f'Bajistas ({declines})',
        text=[f'{declines}'],
        textposition='inside',
        hovertemplate='Bajistas: %{x}<extra></extra>'
    ),
    row=1, col=2
)

fig_breadth.update_xaxes(title_text="Cambio %", row=1, col=1)
fig_breadth.update_yaxes(title_text="Cantidad", row=1, col=1)
fig_breadth.update_xaxes(title_text="", showticklabels=False, row=1, col=2)
fig_breadth.update_yaxes(title_text="", showticklabels=False, row=1, col=2)

fig_breadth.update_layout(
    barmode='stack',
    height=400,
    showlegend=True,
    plot_bgcolor='#161b22',
    paper_bgcolor='#0d1117',
    font=dict(family='DM Sans, sans-serif', color='#e6edf3'),
    margin=dict(l=40, r=40, t=60, b=40)
)

html_breadth = fig_breadth.to_html(include_plotlyjs=False, div_id='breadth', config={'displayModeBar': True, 'displaylogo': False})

vol_outliers = metrics[metrics['vol_rel20'] >= 1.5].nlargest(15, 'vol_rel20')

if not vol_outliers.empty:
    vol_sorted = vol_outliers.sort_values('vol_rel20', ascending=True)
    colors_vol = [PALETTE_POS if v > 0 else PALETTE_NEG for v in vol_sorted['daily_ret']]
    
    fig_volume = go.Figure()
    
    fig_volume.add_trace(go.Bar(
        y=vol_sorted['ticker'],
        x=vol_sorted['vol_rel20'],
        orientation='h',
        marker_color=colors_vol,
        opacity=0.85,
        hovertemplate='<b>%{y}</b><br>Vol Rel: %{x:.2f}x<br>Cambio: %{customdata:.2f}%<extra></extra>',
        customdata=vol_sorted['daily_ret']
    ))
    
    fig_volume.add_vline(x=1.5, line_dash="dash", line_color="#475569", line_width=1,
                        annotation_text="Umbral 1.5x")
    
    fig_volume.update_layout(
        title="Acciones con Volumen Inusual",
        xaxis_title="Ratio Volumen / Promedio 20 días",
        height=400,
        plot_bgcolor='#161b22',
        paper_bgcolor='#0d1117',
        font=dict(family='DM Sans, sans-serif', color='#e6edf3'),
        margin=dict(l=100, r=40, t=60, b=40),
        showlegend=False
    )
    
    html_volume = fig_volume.to_html(include_plotlyjs=False, div_id='volume', config={'displayModeBar': True, 'displaylogo': False})
    has_volume_chart = True
else:
    has_volume_chart = False

def df_to_html_table(data, table_id):
    return data.to_html(classes='data-table', table_id=table_id, escape=False, index=False)

def format_change(val):
    try:
        v = float(val)
        cls = 'positive' if v >= 0 else 'negative'
        return f'<span class="{cls}">{v:+.2f}%</span>'
    except:
        return val

top_gainers_html = top_gainers.copy()
top_losers_html = top_losers.copy()
top_gainers_html['daily_ret'] = top_gainers_html['daily_ret'].apply(format_change)
top_losers_html['daily_ret'] = top_losers_html['daily_ret'].apply(format_change)
top_gainers_html.columns = ['Ticker', 'Precio', 'Cambio %', 'Volumen', 'Vol Rel 20d']
top_losers_html.columns = ['Ticker', 'Precio', 'Cambio %', 'Volumen', 'Vol Rel 20d']

volume_section = ""
if has_volume_chart:
    vol_outliers_html = vol_outliers.copy()
    vol_outliers_html['daily_ret'] = vol_outliers_html['daily_ret'].apply(format_change)
    vol_outliers_html.columns = ['Ticker', 'Precio', 'Fecha', 'Cambio %', 'Volumen', 'Vol Rel 20d']
    volume_section = f"""
    <section class="card full-width">
      <div class="card-header">
        <span class="card-title">Acciones con Volumen Inusual</span>
        <span class="badge">interactivo</span>
      </div>
      <div class="chart-wrap">
        {html_volume}
      </div>
      <div class="table-scroll">{df_to_html_table(vol_outliers_html[['Ticker', 'Cambio %', 'Vol Rel 20d']], 'vol')}</div>
      <div class="explainer">
        Instrumentos con volumen significativamente superior al promedio de 20 ruedas.
        Lecturas elevadas pueden anticipar continuidad o reversión de tendencia.
      </div>
    </section>
    """

now_str = datetime.now().strftime('%Y-%m-%d  %H:%M')
date_str = datetime.now().strftime('%Y-%m-%d')

html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard Panel General ARG</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg:#0d1117;--surface:#161b22;--surface2:#1c2128;--border:#30363d;--border2:#21262d;
      --text:#e6edf3;--muted:#8b949e;--muted2:#6e7681;
      --blue:#58a6ff;--orange:#e3b341;--green:#3fb950;--red:#f85149;--slate:#8b949e;
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);padding:28px 20px 60px;line-height:1.6;}}
    .page-wrap{{max-width:1380px;margin:0 auto;}}
    .page-header{{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:32px;padding-bottom:20px;border-bottom:2px solid var(--border);}}
    .back-link{{font-size:0.82rem;color:var(--blue);text-decoration:none;font-family:'DM Mono',monospace;display:flex;align-items:center;gap:6px;margin-bottom:10px;}}
    .back-link:hover{{text-decoration:underline;}}
    .page-header h1{{font-size:1.9rem;font-weight:600;letter-spacing:-0.03em;}}
    .page-header h1 span{{color:var(--blue);}}
    .meta{{font-size:0.82rem;color:var(--muted);font-family:'DM Mono',monospace;text-align:right;}}
    .sentiment-banner{{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--border);border-left:5px solid {sentiment_color};border-radius:10px;padding:16px 22px;margin-bottom:28px;}}
    .sentiment-label{{font-weight:600;font-size:1rem;color:{sentiment_color};white-space:nowrap;}}
    .sentiment-text{{color:var(--muted);font-size:0.87rem;}}
    .kpi-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:28px;}}
    .kpi{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 20px;}}
    .kpi-label{{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:6px;}}
    .kpi-value{{font-size:1.7rem;font-weight:600;font-family:'DM Mono',monospace;}}
    .kpi-value.pos{{color:var(--blue);}}
    .kpi-value.neg{{color:var(--orange);}}
    .kpi-value.neu{{color:var(--text);}}
    .grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-bottom:22px;}}
    .full-width{{margin-bottom:22px;}}
    .card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;}}
    .card-header{{display:flex;align-items:center;gap:10px;padding:18px 22px 12px;border-bottom:1px solid var(--border);}}
    .card-title{{font-size:1rem;font-weight:600;}}
    .badge{{margin-left:auto;font-size:0.72rem;font-family:'DM Mono',monospace;background:rgba(88,166,255,0.1);color:var(--blue);border:1px solid rgba(88,166,255,0.25);border-radius:99px;padding:2px 10px;}}
    .chart-wrap{{padding:18px 18px 10px;}}
    .explainer{{font-size:0.83rem;color:var(--muted);padding:12px 22px 18px;border-top:1px dashed var(--border);line-height:1.65;}}
    .summary-card{{background:var(--surface2);border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:10px;padding:20px 24px;margin-bottom:28px;font-size:0.9rem;line-height:1.75;color:var(--text);}}
    .summary-title{{font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;color:var(--blue);font-weight:600;margin-bottom:10px;}}
    .table-scroll{{overflow-x:auto;padding:0 18px 18px;}}
    .data-table{{width:100%;border-collapse:collapse;font-size:0.83rem;font-family:'DM Mono',monospace;}}
    .data-table th{{background:var(--surface2);color:var(--muted);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.05em;padding:10px 12px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;}}
    .data-table td{{padding:9px 12px;border-bottom:1px solid var(--border2);white-space:nowrap;transition:background 0.15s ease;}}
    .data-table tr:last-child td{{border-bottom:none;}}
    .data-table tr:hover td{{background:var(--surface2);}}
    .positive{{color:var(--blue);font-weight:600;}}
    .negative{{color:var(--orange);font-weight:600;}}
    .page-footer{{text-align:center;margin-top:48px;font-size:0.78rem;color:var(--muted);font-family:'DM Mono',monospace;}}
    @media (max-width:860px){{.grid-2{{grid-template-columns:1fr;}}.page-header{{flex-direction:column;align-items:flex-start;gap:8px;}}}}
  </style>
</head>
<body>
<script>
document.addEventListener('DOMContentLoaded', function() {{
  const tables = document.querySelectorAll('.data-table');
  tables.forEach(table => {{
    const headers = table.querySelectorAll('th');
    const tbody = table.querySelector('tbody');
    headers.forEach((header, index) => {{
      header.style.cursor = 'pointer';
      header.style.userSelect = 'none';
      header.title = 'Click para ordenar';
      const arrow = document.createElement('span');
      arrow.style.marginLeft = '6px';
      arrow.style.opacity = '0.3';
      arrow.innerHTML = '⇅';
      header.appendChild(arrow);
      let ascending = true;
      header.addEventListener('click', () => {{
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((a, b) => {{
          const aCell = a.cells[index].textContent.trim();
          const bCell = b.cells[index].textContent.trim();
          const aNum = parseFloat(aCell.replace(/[^0-9.-]/g, ''));
          const bNum = parseFloat(bCell.replace(/[^0-9.-]/g, ''));
          let comparison = 0;
          if (!isNaN(aNum) && !isNaN(bNum)) {{
            comparison = aNum - bNum;
          }} else {{
            comparison = aCell.localeCompare(bCell);
          }}
          return ascending ? comparison : -comparison;
        }});
        headers.forEach(h => {{
          const arr = h.querySelector('span');
          if (arr) arr.innerHTML = '⇅';
        }});
        arrow.innerHTML = ascending ? '▲' : '▼';
        arrow.style.opacity = '1';
        ascending = !ascending;
        rows.forEach(row => tbody.appendChild(row));
        tbody.style.opacity = '0.7';
        setTimeout(() => tbody.style.opacity = '1', 100);
      }});
    }});
  }});
  document.querySelectorAll('.data-table tr').forEach(row => {{
    row.addEventListener('mouseenter', function() {{
      this.style.transform = 'scale(1.01)';
      this.style.transition = 'transform 0.15s ease';
    }});
    row.addEventListener('mouseleave', function() {{
      this.style.transform = 'scale(1)';
    }});
  }});
}});
</script>
<div class="page-wrap">
  <header class="page-header">
    <div>
      <a class="back-link" href="../index.html">← Volver al inicio</a>
      <h1>Dashboard <span>Panel General ARG</span></h1>
    </div>
    <div class="meta">API: data912.com — {total_stocks} instrumentos<br>Actualizado: {now_str}</div>
  </header>

  <div class="sentiment-banner">
    <span class="sentiment-label">{market_sentiment}</span>
    <span class="sentiment-text">
      Ratio A/D: <strong>{ad_ratio:.2f}</strong> &nbsp;·&nbsp;
      Media: <strong>{avg_change:+.2f}%</strong> &nbsp;·&nbsp;
      Mediana: <strong>{median_change:+.2f}%</strong>
    </span>
  </div>

  <div class="kpi-strip">
    <div class="kpi"><div class="kpi-label">Total</div><div class="kpi-value neu">{total_stocks}</div></div>
    <div class="kpi"><div class="kpi-label">Alcistas</div><div class="kpi-value pos">{advances}</div></div>
    <div class="kpi"><div class="kpi-label">Bajistas</div><div class="kpi-value neg">{declines}</div></div>
    <div class="kpi"><div class="kpi-label">Ratio A/D</div><div class="kpi-value {'pos' if ad_ratio >= 1 else 'neg'}">{ad_ratio:.2f}</div></div>
    <div class="kpi"><div class="kpi-label">Cambio promedio</div><div class="kpi-value {'pos' if avg_change >= 0 else 'neg'}">{avg_change:+.2f}%</div></div>
    <div class="kpi"><div class="kpi-label">Mediana</div><div class="kpi-value {'pos' if median_change >= 0 else 'neg'}">{median_change:+.2f}%</div></div>
  </div>

  <div class="summary-card">
    <div class="summary-title">Resumen ejecutivo</div>
    {executive_summary}
  </div>

  <section class="card full-width">
    <div class="card-header"><span class="card-title">Heatmap de Variaciones</span><span class="badge">panel completo · interactivo</span></div>
    <div class="chart-wrap">
      {html_heatmap}
    </div>
    <div class="explainer">Mapa de calor de los retornos del día. Verde = subas, rojo = bajas. Hover muestra detalles (precio, volumen relativo). Zoom y pan disponibles.</div>
  </section>

  <section class="card full-width">
    <div class="card-header"><span class="card-title">Distribución de Cambios y Market Breadth</span><span class="badge">panel completo · interactivo</span></div>
    <div class="chart-wrap">
      {html_breadth}
    </div>
    <div class="explainer">
      Histograma de cambios con media/mediana. Hover para valores exactos. Click en leyenda para filtrar categorías.
    </div>
  </section>

  <div class="grid-2">
    <section class="card">
      <div class="card-header"><span class="card-title">Top 15 Ganadores</span><span class="badge">% cambio</span></div>
      <div class="table-scroll">{df_to_html_table(top_gainers_html, 'gainers')}</div>
      <div class="explainer">Las 15 acciones con mayor suba. Click en headers para ordenar. Hover en filas para highlight.</div>
    </section>
    <section class="card">
      <div class="card-header"><span class="card-title">Top 15 Perdedores</span><span class="badge">% cambio</span></div>
      <div class="table-scroll">{df_to_html_table(top_losers_html, 'losers')}</div>
      <div class="explainer">Las 15 acciones con mayor caída. Permite distinguir evento puntual vs presión sectorial.</div>
    </section>
  </div>

  {volume_section}

  <footer class="page-footer">
    Datos: API912 (data912.com) &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; Solo con fines informativos
  </footer>
</div>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Dashboard actualizado: {now_str}")


import json

data_export = {
    "generated_at": now_str,
    "market_summary": {
        "total_stocks": total_stocks,
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "ad_ratio": round(ad_ratio, 3),
        "avg_change": round(avg_change, 3),
        "median_change": round(median_change, 3),
        "std_change": round(std_change, 3),
        "sentiment": market_sentiment,
        "sentiment_color": sentiment_color,
        "executive_summary": executive_summary,
    },
    "tickers": []
}

for tk, g in df_raw.groupby('ticker'):
    g = g.sort_values('date').copy()
    history = []
    for _, row in g.iterrows():
        history.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "open": round(float(row['open']), 2),
            "high": round(float(row['high']), 2),
            "low": round(float(row['low']), 2),
            "close": round(float(row['close']), 2),
            "volume": int(row['volume']),
        })
    
    ticker_metrics = metrics[metrics['ticker'] == tk]
    if ticker_metrics.empty:
        continue
    m = ticker_metrics.iloc[0]
    
    data_export["tickers"].append({
        "ticker": tk,
        "close_last": float(m['close_last']),
        "daily_ret": float(m['daily_ret']),
        "volume_last": int(m['volume_last']),
        "vol_rel20": float(m['vol_rel20']),
        "history": history
    })

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data_export, f, ensure_ascii=False)
