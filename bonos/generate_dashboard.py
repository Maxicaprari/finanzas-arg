"""
Bonos ARG Dashboard Generator
- Primera corrida: descarga todo el histórico y guarda CSVs en bonos/data/
- Corridas siguientes: solo descarga datos nuevos desde la última fecha conocida
- Siempre regenera data.json al final
"""
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
import json

warnings.filterwarnings('ignore')

BASE_URL  = "https://data912.com"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")

BOND_TICKERS = [
    'AE38', 'AE38D', 'AL29', 'AL29D', 'AL30', 'AL30C', 'AL30D', 'AL35', 'AL35D',
    'AL41', 'AL41D', 'BA37D', 'BB37D', 'BC37D', 'BDC28', 'BPY26', 'CO26', 'CO26D',
    'CUAP', 'DICP', 'DIP0', 'GD29', 'GD29D', 'GD30', 'GD30C', 'GD30D', 'GD35',
    'GD35D', 'GD38', 'GD38D', 'GD41', 'GD41D', 'GD46', 'GD46D', 'NDT25', 'PAP0',
    'PARP', 'PBA25', 'T2X5', 'TDE25', 'TO26', 'TVPA', 'TVPE', 'TVPP', 'TVPY',
    'TX25', 'TX26', 'TX28'
]

BOND_TYPE = {}
for tk in ['GD29', 'GD29D', 'GD30', 'GD30C', 'GD30D', 'GD35', 'GD35D', 'GD38', 'GD38D', 'GD41', 'GD41D', 'GD46', 'GD46D']:
    BOND_TYPE[tk] = 'Global (Ley NY)'
for tk in ['AL29', 'AL29D', 'AL30', 'AL30C', 'AL30D', 'AL35', 'AL35D', 'AL41', 'AL41D', 'AE38', 'AE38D']:
    BOND_TYPE[tk] = 'Soberano (Ley ARG)'
for tk in ['TX25', 'TX26', 'TX28', 'T2X5', 'CUAP', 'DICP']:
    BOND_TYPE[tk] = 'CER / Inflación'
for tk in ['TDE25', 'TO26', 'TVPA', 'TVPE', 'TVPP', 'TVPY']:
    BOND_TYPE[tk] = 'ARS Nominal'
for tk in ['BA37D', 'BB37D', 'BC37D', 'BDC28', 'BPY26', 'CO26', 'CO26D', 'NDT25', 'PAP0', 'PARP', 'PBA25']:
    BOND_TYPE[tk] = 'Provincias'
BOND_TYPE['DIP0'] = 'Otros'


# ── CSV helpers ──────────────────────────────────────────────────────────────

def csv_path(ticker):
    return os.path.join(DATA_DIR, f"{ticker}.csv")

def cargar_csv(ticker):
    path = csv_path(ticker)
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=['date'])
    return df.sort_values('date').reset_index(drop=True)

def guardar_csv(ticker, df):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(csv_path(ticker), index=False)


# ── API fetch (solo el rango necesario) ──────────────────────────────────────

def fetch_desde_api(ticker, desde=None, max_retries=3):
    """
    Descarga datos del ticker desde `desde` hasta hoy.
    Si `desde` es None, trae todo el histórico disponible.
    La API de data912 devuelve todo el histórico en un solo llamado
    (no soporta filtro de fecha), así que filtramos post-descarga.
    """
    url = f"{BASE_URL}/historical/bonds/{ticker}"
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                    'c': 'close', 'v': 'volume', 'dr': 'daily_return'})
            df = df.sort_values('date').reset_index(drop=True)
            if desde is not None:
                df = df[df['date'] > pd.Timestamp(desde)]
            return df
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"  [{ticker}] error: {e}")
    return pd.DataFrame()


# ── Actualización incremental ────────────────────────────────────────────────

def actualizar_ticker(ticker, i, total):
    df_local = cargar_csv(ticker)
    hoy = datetime.now().date()

    if df_local.empty:
        print(f"  [{i:2}/{total}] {ticker:<6}  sin CSV -> descarga completa")
        df_new = fetch_desde_api(ticker)
        if df_new.empty:
            return df_local
        guardar_csv(ticker, df_new)
        return df_new
    else:
        ultimo = df_local['date'].max().date()
        if ultimo >= hoy:
            print(f"  [{i:2}/{total}] {ticker:<6}  ya al dia ({ultimo})")
            return df_local
        print(f"  [{i:2}/{total}] {ticker:<6}  actualiz. desde {ultimo + timedelta(days=1)}")
        df_new = fetch_desde_api(ticker, desde=ultimo)
        if df_new.empty:
            return df_local
        df_combined = (pd.concat([df_local, df_new], ignore_index=True)
                       .drop_duplicates(subset=['date'])
                       .sort_values('date')
                       .reset_index(drop=True))
        guardar_csv(ticker, df_combined)
        nuevos = len(df_combined) - len(df_local)
        print(f"  [{i:2}/{total}] {ticker:<6}  +{nuevos} registros -> total {len(df_combined)}")
        return df_combined


# ── Cálculo de métricas ──────────────────────────────────────────────────────

def calcular_metricas(all_frames):
    metrics_rows = []
    for ticker, df in all_frames.items():
        if df.empty or len(df) < 2:
            continue
        g = df.sort_values('date')
        close = g['close'].values
        vol   = g['volume'].values
        close_last = close[-1]
        close_prev = close[-2]
        daily_ret  = ((close_last / close_prev) - 1) * 100
        vol_last   = vol[-1]
        vol_avg20  = np.mean(vol[-21:-1]) if len(vol) > 21 else np.mean(vol[:-1])
        vol_rel20  = (vol_last / vol_avg20) if vol_avg20 > 0 else np.nan
        metrics_rows.append({
            'ticker':     ticker,
            'bond_type':  BOND_TYPE.get(ticker, 'Otros'),
            'close_last': round(close_last, 2),
            'daily_ret':  round(daily_ret, 2),
            'volume_last': int(vol_last),
            'vol_rel20':  round(vol_rel20, 2),
        })
    return pd.DataFrame(metrics_rows).dropna(subset=['daily_ret'])


# ── Generar data.json ────────────────────────────────────────────────────────

def generar_json(all_frames, metrics):
    total_bonds    = len(metrics)
    advances       = len(metrics[metrics['daily_ret'] > 0])
    declines       = len(metrics[metrics['daily_ret'] < 0])
    unchanged      = total_bonds - advances - declines
    ad_ratio       = advances / declines if declines > 0 else float('inf')
    avg_change     = metrics['daily_ret'].mean()
    median_change  = metrics['daily_ret'].median()
    std_change     = metrics['daily_ret'].std()

    if ad_ratio >= 2.0 and avg_change >= 0.5:
        sentiment, sentiment_color = "Alcista amplio",   "#22c55e"
    elif ad_ratio >= 1.2 and avg_change >= 0:
        sentiment, sentiment_color = "Alcista moderado", "#86efac"
    elif ad_ratio <= 0.5 and avg_change <= -0.5:
        sentiment, sentiment_color = "Bajista amplio",   "#ef4444"
    elif ad_ratio <= 0.8 and avg_change <= 0:
        sentiment, sentiment_color = "Bajista moderado", "#fca5a5"
    else:
        sentiment, sentiment_color = "Mixto / Sin tendencia", "#94a3b8"

    top_gain = metrics.loc[metrics['daily_ret'].idxmax()]
    top_loss = metrics.loc[metrics['daily_ret'].idxmin()]
    executive_summary = (
        f"Panel de bonos argentinos: {total_bonds} instrumentos analizados, "
        f"{advances} alcistas / {declines} bajistas (ratio A/D {ad_ratio:.2f}), "
        f"cambio promedio {avg_change:+.2f}%. "
        f"Mayor ganador: {top_gain['ticker']} ({top_gain['daily_ret']:+.2f}%). "
        f"Mayor perdedor: {top_loss['ticker']} ({top_loss['daily_ret']:+.2f}%)."
    )

    now_str = datetime.now().strftime('%Y-%m-%d  %H:%M')

    out = {
        "generated_at": now_str,
        "market_summary": {
            "total_stocks":   total_bonds,
            "advances":       advances,
            "declines":       declines,
            "unchanged":      unchanged,
            "ad_ratio":       round(ad_ratio, 3),
            "avg_change":     round(avg_change, 3),
            "median_change":  round(median_change, 3),
            "std_change":     round(std_change, 3),
            "sentiment":      sentiment,
            "sentiment_color": sentiment_color,
            "executive_summary": executive_summary,
        },
        "tickers": []
    }

    for tk, df in all_frames.items():
        m = metrics[metrics['ticker'] == tk]
        if m.empty or df.empty:
            continue
        m = m.iloc[0]
        history = [
            {
                "date":   row['date'].strftime('%Y-%m-%d'),
                "open":   round(float(row['open']),   2),
                "high":   round(float(row['high']),   2),
                "low":    round(float(row['low']),    2),
                "close":  round(float(row['close']),  2),
                "volume": int(row['volume']),
            }
            for _, row in df.sort_values('date').iterrows()
        ]
        out["tickers"].append({
            "ticker":      tk,
            "bond_type":   BOND_TYPE.get(tk, 'Otros'),
            "close_last":  float(m['close_last']),
            "daily_ret":   float(m['daily_ret']),
            "volume_last": int(m['volume_last']),
            "vol_rel20":   float(m['vol_rel20']),
            "history":     history,
        })

    path = os.path.join(BASE_DIR, "data.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    total_pts = sum(len(t['history']) for t in out['tickers'])
    print(f"\ndata.json -> {len(out['tickers'])} bonos | {total_pts:,} puntos | {now_str}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Bonos ARG Dashboard Generator ===")
    total = len(BOND_TICKERS)
    all_frames = {}

    for i, tk in enumerate(BOND_TICKERS, 1):
        df = actualizar_ticker(tk, i, total)
        if not df.empty:
            all_frames[tk] = df
        time.sleep(0.2)   # delay reducido: solo pedimos datos nuevos

    if not all_frames:
        print("Sin datos. Verifica la conexion a data912.com")
        return

    metrics = calcular_metricas(all_frames)
    generar_json(all_frames, metrics)


if __name__ == "__main__":
    main()
