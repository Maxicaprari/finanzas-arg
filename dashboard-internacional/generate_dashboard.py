from tvscreener import StockScreener, StockField, IndexSymbol
import pandas as pd
import numpy as np
import json
from datetime import datetime
import warnings

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

# Detect volume avg column
vol_col = None
for c in df.columns:
    if 'average' in c.lower() and 'volume' in c.lower():
        vol_col = c
        break

# Market metrics
total_stocks  = len(df)
advances      = int((df['Change %'] > 0).sum())
declines      = int((df['Change %'] < 0).sum())
unchanged     = total_stocks - advances - declines
ad_ratio      = advances / declines if declines > 0 else float('inf')
avg_change    = float(df['Change %'].mean())
median_change = float(df['Change %'].median())
std_change    = float(df['Change %'].std())

# Sector stats
sector_stats = df.groupby('Sector').agg(
    avg_change=('Change %', 'mean'),
    count=('Change %', 'count'),
    advances=('Change %', lambda x: int((x > 0).sum())),
    declines=('Change %', lambda x: int((x < 0).sum())),
).reset_index()
sector_stats = sector_stats[sector_stats['count'] >= 3].sort_values('avg_change', ascending=False)

leading_sector = sector_stats.iloc[0]['Sector']  if not sector_stats.empty else "N/D"
lagging_sector = sector_stats.iloc[-1]['Sector'] if not sector_stats.empty else "N/D"

# Sentiment
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
    market_sentiment = "Mixto / Sin tendencia"
    sentiment_color  = "#94a3b8"

# Volume outliers
volume_outliers = []
if vol_col:
    df_vol = df.dropna(subset=[vol_col, 'Volume']).copy()
    df_vol[vol_col] = pd.to_numeric(df_vol[vol_col], errors='coerce')
    df_vol = df_vol.dropna(subset=[vol_col])
    df_vol = df_vol[df_vol[vol_col] > 0]
    df_vol['vol_ratio'] = df_vol['Volume'] / df_vol[vol_col]
    vol_out = df_vol[df_vol['vol_ratio'] >= 2.0].nlargest(20, 'vol_ratio')
    for ticker_sym, row in vol_out.iterrows():
        volume_outliers.append({
            "name":       str(row.get('Name', '')),
            "ticker":     str(ticker_sym),
            "sector":     str(row.get('Sector', '')),
            "change_pct": round(float(row['Change %']), 3),
            "price":      round(float(row['Price']), 2) if pd.notna(row.get('Price')) else None,
            "volume":     int(row['Volume']),
            "vol_avg_30d":int(row[vol_col]),
            "vol_ratio":  round(float(row['vol_ratio']), 2),
        })

# Executive summary
def build_summary():
    lines = [
        f"El universo de {total_stocks} acciones del S&P 500 registró {advances} alzas y {declines} bajas "
        f"(ratio A/D: {ad_ratio:.2f}), con un cambio promedio de {avg_change:+.2f}%."
    ]
    if ad_ratio >= 1.5:
        lines.append("La amplitud es positiva: movimiento de base amplia, no concentrado en pocos nombres.")
    elif ad_ratio <= 0.67:
        lines.append("La amplitud es negativa: deterioro generalizado en el universo analizado.")
    else:
        lines.append("La amplitud es mixta: sin dirección dominante clara, posible rotación sectorial.")
    lines.append(
        f"Sector líder: {leading_sector} · Sector rezagado: {lagging_sector}. "
        f"Desvío estándar: {std_change:.2f}% "
        f"({'alta selectividad entre instrumentos' if std_change > 2 else 'movimientos relativamente homogéneos'})."
    )
    if volume_outliers:
        lines.append(
            f"Se detectaron {len(volume_outliers)} acciones con volumen ≥2x su promedio de 30 ruedas."
        )
    return " ".join(lines)

executive_summary = build_summary()
now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

# Build JSON export
data_export = {
    "generated_at": now_str,
    "market_summary": {
        "total_stocks":    total_stocks,
        "advances":        advances,
        "declines":        declines,
        "unchanged":       unchanged,
        "ad_ratio":        round(ad_ratio, 3),
        "avg_change":      round(avg_change, 3),
        "median_change":   round(median_change, 3),
        "std_change":      round(std_change, 3),
        "sentiment":       market_sentiment,
        "sentiment_color": sentiment_color,
        "executive_summary": executive_summary,
        "leading_sector":  leading_sector,
        "lagging_sector":  lagging_sector,
    },
    "sectors": [
        {
            "sector":     row["Sector"],
            "avg_change": round(float(row["avg_change"]), 3),
            "count":      int(row["count"]),
            "advances":   int(row["advances"]),
            "declines":   int(row["declines"]),
        }
        for _, row in sector_stats.iterrows()
    ],
    "tickers":          [],
    "changes":          [round(float(v), 3) for v in df['Change %'].dropna().tolist()],
    "volume_outliers":  volume_outliers,
}

for ticker_sym, row in df.iterrows():
    vol_ratio = None
    vol_avg   = None
    if vol_col and pd.notna(row.get(vol_col)) and float(row.get(vol_col, 0)) > 0:
        vol_avg   = int(row[vol_col])
        vol_ratio = round(float(row['Volume']) / float(row[vol_col]), 2)

    mktcap = None
    for cap_col in ['Market capitalization', 'Market Capitalization', 'market_cap']:
        if cap_col in row.index and pd.notna(row.get(cap_col)):
            mktcap = float(row[cap_col])
            break

    data_export["tickers"].append({
        "name":       str(row.get('Name', '')),
        "ticker":     str(ticker_sym),
        "sector":     str(row.get('Sector', '')),
        "industry":   str(row.get('Industry', '')),
        "change_pct": round(float(row['Change %']), 3),
        "price":      round(float(row['Price']), 2) if pd.notna(row.get('Price')) else None,
        "volume":     int(row['Volume']) if pd.notna(row.get('Volume')) else None,
        "vol_avg_30d":vol_avg,
        "vol_ratio":  vol_ratio,
        "market_cap": mktcap,
    })

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data_export, f, ensure_ascii=False, separators=(',', ':'))

print(f"S&P 500 data.json actualizado: {now_str}")
print(f"  {total_stocks} acciones · {advances} alcistas · {declines} bajistas · {len(volume_outliers)} vol outliers · {len(data_export['sectors'])} sectores")
