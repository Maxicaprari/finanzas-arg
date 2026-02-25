from tvscreener import StockScreener, StockField, IndexSymbol
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

ss = StockScreener()
ss.set_index(IndexSymbol.SP500)
ss.select(
    StockField.NAME,
    StockField.PRICE,
    StockField.CHANGE_PERCENT,
    StockField.VOLUME,
    StockField.AVERAGE_VOLUME_30D_CALC_1,
    StockField.SECTOR,
    StockField.INDUSTRY,
    StockField.MARKET_CAPITALIZATION,
)
ss.set_range(0, 500)
df = ss.get()
df = df.dropna(subset=['Change %'])

vol_col = None
for c in df.columns:
    if 'average' in c.lower() and 'volume' in c.lower():
        vol_col = c
        break

total_stocks  = len(df)
advances      = len(df[df['Change %'] > 0])
declines      = len(df[df['Change %'] < 0])
unchanged     = total_stocks - advances - declines
ad_ratio      = advances / declines if declines > 0 else float('inf')
avg_change    = df['Change %'].mean()
median_change = df['Change %'].median()
std_change    = df['Change %'].std()

top_gainers = df.nlargest(20, 'Change %')[['Name', 'Sector', 'Industry', 'Change %', 'Price', 'Volume']].copy()
top_losers  = df.nsmallest(20, 'Change %')[['Name', 'Sector', 'Industry', 'Change %', 'Price', 'Volume']].copy()

has_volume_data  = False
volume_outliers  = pd.DataFrame()

if vol_col:
    df_vol = df.dropna(subset=[vol_col, 'Volume']).copy()
    df_vol[vol_col] = pd.to_numeric(df_vol[vol_col], errors='coerce')
    df_vol = df_vol.dropna(subset=[vol_col])
    df_vol = df_vol[df_vol[vol_col] > 0]
    df_vol['Volume Ratio'] = df_vol['Volume'] / df_vol[vol_col]
    volume_outliers = df_vol[df_vol['Volume Ratio'] >= 2.0].nlargest(20, 'Volume Ratio')[
        ['Name', 'Sector', 'Change %', 'Volume', vol_col, 'Volume Ratio']
    ].copy()
    volume_outliers['Volume Ratio'] = volume_outliers['Volume Ratio'].round(2)
    volume_outliers[vol_col] = volume_outliers[vol_col].astype(int)
    volume_outliers = volume_outliers.rename(columns={vol_col: 'Vol. Prom. 30d'})
    if not volume_outliers.empty:
        has_volume_data = True

sector_stats = df.groupby('Sector').agg(
    avg_change=('Change %', 'mean'),
    count=('Change %', 'count'),
    advances=('Change %', lambda x: (x > 0).sum()),
    declines=('Change %', lambda x: (x < 0).sum()),
).reset_index()
sector_stats = sector_stats[sector_stats['count'] >= 3].sort_values('avg_change', ascending=False)

if ad_ratio >= 2.0 and avg_change >= 0.5:
    market_sentiment = "Alcista amplio"
    sentiment_color  = "#22c55e"
elif ad_ratio >= 1.2 and avg_change >= 0:
    market_sentiment = "Alcista moderado"
    sentiment_color  = "#86efac"
elif ad_ratio <= 0.5 and avg_change <= -0.5:
    market_sentiment = "Bajista amplio"
    sentiment_color  = "#ef4444"
elif ad_ratio <= 0.8 and avg_change <= 0:
    market_sentiment = "Bajista moderado"
    sentiment_color  = "#fca5a5"
else:
    market_sentiment = "Mixto / Sin tendencia clara"
    sentiment_color  = "#94a3b8"

leading_sector = sector_stats.iloc[0]['Sector']  if not sector_stats.empty else "N/D"
lagging_sector = sector_stats.iloc[-1]['Sector'] if not sector_stats.empty else "N/D"

def build_summary():
    lines = []
    lines.append(
        f"En la jornada analizada, el universo de {total_stocks} acciones registró un avance/caída "
        f"de {advances}/{declines} (ratio {ad_ratio:.2f}), con un cambio promedio de {avg_change:+.2f}%."
    )
    if ad_ratio >= 1.5:
        lines.append(
            "La amplitud del mercado es positiva: más de la mitad de los instrumentos terminaron "
            "en verde, lo que indica un movimiento de base amplia y no concentrado en pocos nombres."
        )
    elif ad_ratio <= 0.67:
        lines.append(
            "La amplitud del mercado es negativa: la mayoría de los instrumentos cedieron terreno, "
            "lo cual sugiere un deterioro generalizado y no puntual."
        )
    else:
        lines.append(
            "La amplitud del mercado es mixta: el movimiento del día no muestra una dirección "
            "dominante clara, lo que suele indicar rotación sectorial o falta de catalizadores definidos."
        )
    lines.append(
        f"El sector con mejor desempeño promedio fue {leading_sector}, "
        f"mientras que el de peor desempeño fue {lagging_sector}."
    )
    lines.append(
        f"La dispersión de los cambios (desvío estándar: {std_change:.2f}%) "
        + ("es elevada, lo que refleja alta selectividad entre instrumentos."
           if std_change > 2 else
           "es moderada, con movimientos relativamente homogéneos en el universo.")
    )
    if has_volume_data:
        lines.append(
            f"Se detectaron {len(volume_outliers)} acciones con volumen significativamente superior "
            f"al promedio de 30 ruedas (ratio ≥ 2x), lo que puede anticipar continuidad o reversión "
            f"de tendencia en esos instrumentos."
        )
    return " ".join(lines)

executive_summary = build_summary()

PALETTE_POS  = "#3b82f6"
PALETTE_NEG  = "#f97316"
PALETTE_NEUT = "#94a3b8"

n = len(sector_stats)
cols_grid = min(n, 6)
rows_grid = int(np.ceil(n / cols_grid))

z_matrix = np.full((rows_grid, cols_grid), np.nan)
text_matrix = [['' for _ in range(cols_grid)] for _ in range(rows_grid)]
hover_matrix = [['' for _ in range(cols_grid)] for _ in range(rows_grid)]

for i, row in sector_stats.reset_index(drop=True).iterrows():
    col_i = i % cols_grid
    row_i = i // cols_grid
    val = row['avg_change']
    z_matrix[row_i, col_i] = val
    text_matrix[row_i][col_i] = f"{row['Sector'][:15]}<br>{val:+.2f}% ({int(row['count'])})"
    hover_matrix[row_i][col_i] = (
        f"<b>{row['Sector']}</b><br>"
        f"Cambio promedio: {val:+.2f}%<br>"
        f"Acciones: {int(row['count'])}<br>"
        f"Alcistas: {int(row['advances'])}<br>"
        f"Bajistas: {int(row['declines'])}"
    )

fig_heatmap = go.Figure(data=go.Heatmap(
    z=z_matrix,
    text=text_matrix,
    hovertext=hover_matrix,
    hoverinfo='text',
    texttemplate='%{text}',
    textfont=dict(size=9, family="monospace", color="white"),
    colorscale='RdYlGn',
    zmid=0,
    colorbar=dict(title=dict(text="Cambio %", side="right")),
    showscale=True
))

fig_heatmap.update_layout(
    title="Heatmap de Sectores",
    xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
    yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
    height=400,
    plot_bgcolor='#161b22',
    paper_bgcolor='#0d1117',
    font=dict(family='DM Sans, sans-serif', color='#e6edf3'),
    margin=dict(l=20, r=20, t=60, b=20)
)

html_heatmap = fig_heatmap.to_html(
    include_plotlyjs='cdn',
    div_id='heatmap',
    config={'displayModeBar': True, 'displaylogo': False}
)

fig_breadth = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Distribución de Cambios del Día", "Market Breadth"),
    specs=[[{"type": "histogram"}, {"type": "bar"}]],
    horizontal_spacing=0.12
)

fig_breadth.add_trace(
    go.Histogram(
        x=df['Change %'],
        nbinsx=45,
        marker_color=PALETTE_POS,
        opacity=0.75,
        name='Frecuencia',
        hovertemplate='Cambio: %{x:.2f}%<br>Cantidad: %{y}<extra></extra>'
    ),
    row=1, col=1
)

fig_breadth.add_vline(
    x=avg_change,
    line_dash="dash",
    line_color="#8b949e",
    line_width=2,
    annotation_text=f"Media: {avg_change:+.2f}%",
    row=1,
    col=1
)

fig_breadth.add_vline(
    x=median_change,
    line_dash="dot",
    line_color=PALETTE_NEG,
    line_width=1.5,
    row=1,
    col=1
)

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

html_breadth = fig_breadth.to_html(
    include_plotlyjs=False,
    div_id='breadth',
    config={'displayModeBar': True, 'displaylogo': False}
)

fig_movers = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Top 20 Ganadores", "Top 20 Perdedores"),
    specs=[[{"type": "bar"}, {"type": "bar"}]],
    horizontal_spacing=0.10
)

colors_gain = [PALETTE_POS if v > 0 else PALETTE_NEG for v in top_gainers['Change %']]
fig_movers.add_trace(
    go.Bar(
        y=[f"{row['Name'][:20]} · {row['Sector']}" for _, row in top_gainers.iterrows()],
        x=top_gainers['Change %'],
        orientation='h',
        marker_color=colors_gain,
        opacity=0.85,
        name='Ganadores',
        hovertemplate='<b>%{y}</b><br>Cambio: %{x:.2f}%<extra></extra>'
    ),
    row=1, col=1
)

colors_loss = [PALETTE_POS if v > 0 else PALETTE_NEG for v in top_losers['Change %']]
fig_movers.add_trace(
    go.Bar(
        y=[f"{row['Name'][:20]} · {row['Sector']}" for _, row in top_losers.iterrows()],
        x=top_losers['Change %'],
        orientation='h',
        marker_color=colors_loss,
        opacity=0.85,
        name='Perdedores',
        hovertemplate='<b>%{y}</b><br>Cambio: %{x:.2f}%<extra></extra>'
    ),
    row=1, col=2
)

fig_movers.add_vline(x=0, line_color="#334155", line_width=0.8, row=1, col=1)
fig_movers.add_vline(x=0, line_color="#334155", line_width=0.8, row=1, col=2)

fig_movers.update_xaxes(title_text="Cambio %", row=1, col=1)
fig_movers.update_xaxes(title_text="Cambio %", row=1, col=2)
fig_movers.update_yaxes(autorange="reversed", row=1, col=1)
fig_movers.update_yaxes(autorange="reversed", row=1, col=2)

fig_movers.update_layout(
    height=600,
    showlegend=False,
    plot_bgcolor='#161b22',
    paper_bgcolor='#0d1117',
    font=dict(family="DM Sans, sans-serif", size=9),
    margin=dict(l=180, r=180, t=60, b=40)
)

html_movers = fig_movers.to_html(
    include_plotlyjs=False,
    div_id='movers',
    config={'displayModeBar': True, 'displaylogo': False}
)

has_volume_chart = False
if has_volume_data:
    vol_sorted = volume_outliers.sort_values('Volume Ratio', ascending=True)
    colors_vol = [PALETTE_POS if v > 0 else PALETTE_NEG for v in vol_sorted['Change %']]

    fig_volume = go.Figure()

    fig_volume.add_trace(go.Bar(
        y=[f"{row['Name'][:25]} · {row['Sector']} ({row['Change %']:+.2f}%)" for _, row in vol_sorted.iterrows()],
        x=vol_sorted['Volume Ratio'],
        orientation='h',
        marker_color=colors_vol,
        opacity=0.85,
        hovertemplate='<b>%{y}</b><br>Vol Ratio: %{x:.2f}x<br>Cambio: %{customdata:.2f}%<extra></extra>',
        customdata=vol_sorted['Change %']
    ))

    fig_volume.add_vline(
        x=2.0, line_dash="dash", line_color="#475569", line_width=1,
        annotation_text="Umbral 2x"
    )

    fig_volume.update_layout(
        title="Acciones con Volumen Inusual",
        xaxis_title="Ratio Volumen / Promedio 30 ruedas",
        height=500,
        plot_bgcolor='#161b22',
        paper_bgcolor='#0d1117',
        font=dict(family="DM Sans, sans-serif", size=9),
        margin=dict(l=300, r=40, t=60, b=40),
        showlegend=False
    )

    fig_volume.update_yaxes(autorange="reversed")

    html_volume = fig_volume.to_html(
        include_plotlyjs=False,
        div_id='volume',
        config={'displayModeBar': True, 'displaylogo': False}
    )
    has_volume_chart = True

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
top_gainers_html['Change %'] = top_gainers_html['Change %'].apply(format_change)
top_losers_html['Change %'] = top_losers_html['Change %'].apply(format_change)

volume_section = ""
if has_volume_chart:
    vol_outliers_html = volume_outliers.copy()
    vol_outliers_html['Change %'] = vol_outliers_html['Change %'].apply(format_change)
    volume_section = f"""
    <section class="card full-width">
      <div class="card-header">
        <span class="card-title">Acciones con Volumen Inusual</span>
        <span class="badge">interactivo</span>
      </div>
      <div class="chart-wrap">
        {html_volume}
      </div>
      <div class="table-scroll">{df_to_html_table(vol_outliers_html, 'volume-outliers')}</div>
      <div class="explainer">
        Acciones cuyo volumen del día supera al menos el doble de su promedio de las últimas 30 ruedas.
        Lecturas elevadas suelen preceder movimientos importantes o confirmar rupturas técnicas.
      </div>
    </section>
    """

now_str  = datetime.utcnow().strftime('%Y-%m-%d  %H:%M UTC')
date_str = datetime.utcnow().strftime('%Y-%m-%d')

html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="1800">
  <title>S&P 500 · Dashboard de Acciones</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
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
    .data-table td{{padding:9px 12px;border-bottom:1px solid var(--border2);white-space:nowrap;}}
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
      }});
    }});
  }});
}});
</script>

<div class="page-wrap">
  <header class="page-header">
    <div>
      <a class="back-link" href="../index.html">← Volver al inicio</a>
      <h1>S&P 500 · <span>Dashboard de Acciones</span></h1>
    </div>
    <div class="meta">Universo: {total_stocks} instrumentos<br>Actualizado: {now_str}</div>
  </header>

  <div class="sentiment-banner">
    <span class="sentiment-label">{market_sentiment}</span>
    <span class="sentiment-text">
      Sector líder: <strong>{leading_sector}</strong> &nbsp;·&nbsp;
      Sector rezagado: <strong>{lagging_sector}</strong> &nbsp;·&nbsp;
      Ratio A/D: <strong>{ad_ratio:.2f}</strong> &nbsp;·&nbsp;
      Media: <strong>{avg_change:+.2f}%</strong>
    </span>
  </div>

  <div class="kpi-strip">
    <div class="kpi"><div class="kpi-label">Universo</div><div class="kpi-value neu">{total_stocks}</div></div>
    <div class="kpi"><div class="kpi-label">Alcistas</div><div class="kpi-value pos">{advances}</div></div>
    <div class="kpi"><div class="kpi-label">Bajistas</div><div class="kpi-value neg">{declines}</div></div>
    <div class="kpi"><div class="kpi-label">Ratio A/D</div><div class="kpi-value {'pos' if ad_ratio >= 1 else 'neg'}">{ad_ratio:.2f}</div></div>
    <div class="kpi"><div class="kpi-label">Cambio promedio</div><div class="kpi-value {'pos' if avg_change >= 0 else 'neg'}">{avg_change:+.2f}%</div></div>
    <div class="kpi"><div class="kpi-label">Mediana</div><div class="kpi-value {'pos' if median_change >= 0 else 'neg'}">{median_change:+.2f}%</div></div>
    <div class="kpi"><div class="kpi-label">Desvío estándar</div><div class="kpi-value neu">{std_change:.2f}%</div></div>
  </div>

  <div class="summary-card">
    <div class="summary-title">Resumen ejecutivo</div>
    {executive_summary}
  </div>

  <div class="grid-2">
    <section class="card">
      <div class="card-header"><span class="card-title">Top 20 Ganadores</span><span class="badge">ordenable</span></div>
      <div class="table-scroll">{df_to_html_table(top_gainers_html, 'gainers')}</div>
      <div class="explainer">Las 20 acciones con mayor suba. Click en los encabezados para ordenar.</div>
    </section>
    <section class="card">
      <div class="card-header"><span class="card-title">Top 20 Perdedores</span><span class="badge">ordenable</span></div>
      <div class="table-scroll">{df_to_html_table(top_losers_html, 'losers')}</div>
      <div class="explainer">Las 20 acciones con mayor caída. Click en los encabezados para ordenar.</div>
    </section>
  </div>

  <section class="card full-width">
    <div class="card-header"><span class="card-title">Heatmap de Sectores</span><span class="badge">interactivo</span></div>
    <div class="chart-wrap">{html_heatmap}</div>
    <div class="explainer">
      Cada celda representa un sector coloreado según el cambio promedio del día.
      Pasá el cursor para ver detalles completos.
    </div>
  </section>

  <section class="card full-width">
    <div class="card-header"><span class="card-title">Distribución de Cambios y Market Breadth</span><span class="badge">interactivo</span></div>
    <div class="chart-wrap">{html_breadth}</div>
    <div class="explainer">
      Histograma de cambios con media y mediana. Barras apiladas con alcistas/bajistas.
      Click en la leyenda para filtrar categorías.
    </div>
  </section>

  <section class="card full-width">
    <div class="card-header"><span class="card-title">Top 20 Ganadores y Perdedores</span><span class="badge">interactivo</span></div>
    <div class="chart-wrap">{html_movers}</div>
    <div class="explainer">
      Barras horizontales para los 20 mayores ganadores y perdedores del día con su sector.
      Permite ver en qué sectores se concentran los extremos.
    </div>
  </section>

  {volume_section}

  <footer class="page-footer">
    Datos: TradingView Screener · S&P 500 &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; Solo con fines informativos
  </footer>
</div>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Dashboard S&P 500 actualizado: {now_str}")
