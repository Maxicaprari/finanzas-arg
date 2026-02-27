#!/usr/bin/env python3
"""
BCRA Dashboard Generator
Lee CSVs históricos, actualiza desde la API solo los datos nuevos,
y escribe data.json para que index.html lo consuma dinámicamente.
"""
import json
import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
from bcra_api_client import BCRAClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

VARIABLES = {
    # ── Tipo de Cambio ────────────────────────────────────────────────────────
    4:    {"nombre": "TC Minorista (B 9791)",      "unidad": "ARS/USD",      "archivo": "tc_minorista",      "grupo": "Tipo de Cambio", "color": "#ff6b6b"},
    5:    {"nombre": "TC Mayorista (A 3500)",       "unidad": "ARS/USD",      "archivo": "tc_mayorista",      "grupo": "Tipo de Cambio", "color": "#ff9f43"},
    1187: {"nombre": "Banda Cambiaria Inferior",    "unidad": "ARS/USD",      "archivo": "banda_inf",         "grupo": "Tipo de Cambio", "color": "#fdcb6e"},
    1188: {"nombre": "Banda Cambiaria Superior",    "unidad": "ARS/USD",      "archivo": "banda_sup",         "grupo": "Tipo de Cambio", "color": "#e17055"},

    # ── Tasas ─────────────────────────────────────────────────────────────────
    160:  {"nombre": "Tasa Política Monetaria",     "unidad": "% TNA",        "archivo": "tasa_politica",     "grupo": "Tasas",          "color": "#a29bfe"},
    7:    {"nombre": "BADLAR Bancos Privados",       "unidad": "% TNA",        "archivo": "badlar",            "grupo": "Tasas",          "color": "#6c5ce7"},
    44:   {"nombre": "TAMAR Bancos Privados",        "unidad": "% TNA",        "archivo": "tamar",             "grupo": "Tasas",          "color": "#fd79a8"},
    14:   {"nombre": "Tasa Préstamos Personales",    "unidad": "% TNA",        "archivo": "tasa_personales",   "grupo": "Tasas",          "color": "#e84393"},
    1189: {"nombre": "Tasa Plazo Fijo",              "unidad": "% TNA",        "archivo": "tasa_plazo_fijo",   "grupo": "Tasas",          "color": "#74b9ff"},

    # ── Inflación ─────────────────────────────────────────────────────────────
    27:   {"nombre": "Inflación Mensual",            "unidad": "%",            "archivo": "inflacion_mensual", "grupo": "Inflación",      "color": "#fd79a8"},
    28:   {"nombre": "Inflación Interanual",         "unidad": "% i.a.",       "archivo": "inflacion_ia",      "grupo": "Inflación",      "color": "#e17055"},
    29:   {"nombre": "Inflación Esperada (REM)",     "unidad": "% i.a.",       "archivo": "inflacion_rem",     "grupo": "Inflación",      "color": "#d63031"},
    31:   {"nombre": "UVA",                          "unidad": "ARS",          "archivo": "uva",               "grupo": "Inflación",      "color": "#fab1a0"},

    # ── Monetario ─────────────────────────────────────────────────────────────
    1:    {"nombre": "Reservas Internacionales",     "unidad": "USD millones", "archivo": "reservas",          "grupo": "Monetario",      "color": "#00e5b8"},
    15:   {"nombre": "Base Monetaria",               "unidad": "millones ARS", "archivo": "base_monetaria",    "grupo": "Monetario",      "color": "#55efc4"},
    17:   {"nombre": "Billetes y Monedas (público)", "unidad": "millones ARS", "archivo": "bill_monedas",      "grupo": "Monetario",      "color": "#00b894"},
    21:   {"nombre": "Depósitos Totales",            "unidad": "millones ARS", "archivo": "depositos",         "grupo": "Monetario",      "color": "#0984e3"},
    26:   {"nombre": "Préstamos Sector Privado",     "unidad": "millones ARS", "archivo": "prestamos",         "grupo": "Monetario",      "color": "#74b9ff"},
    197:  {"nombre": "M2 Transaccional Privado",     "unidad": "millones ARS", "archivo": "m2",                "grupo": "Monetario",      "color": "#81ecec"},
}

# IDs que van en las KPI cards del header
KPI_IDS = [1, 4, 27, 28, 160, 7]


def cargar_desde_csv(info):
    path = os.path.join(DATA_DIR, f"{info['archivo']}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["fecha"])
    if "fecha" in df.columns:
        df = df.sort_values("fecha").reset_index(drop=True)
    return df


def actualizar_con_api(id_var, info, df_local):
    bcra = BCRAClient()
    hasta = datetime.now().strftime("%Y-%m-%d")

    if df_local.empty:
        desde = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    else:
        ultimo = df_local["fecha"].max()
        desde = (ultimo + timedelta(days=1)).strftime("%Y-%m-%d")
        if desde > hasta:
            print(f"  [{id_var:4}] ya al dia ({ultimo.date()})")
            return df_local

    print(f"  [{id_var:4}] descargando desde {desde}...")
    df_nuevo = bcra.get_datos_historicos(id_var, desde=desde, hasta=hasta)

    if df_nuevo.empty:
        print(f"  [{id_var:4}] sin datos nuevos")
        return df_local

    df_combined = (pd.concat([df_local, df_nuevo], ignore_index=True)
                   .drop_duplicates(subset=["fecha"])
                   .sort_values("fecha")
                   .reset_index(drop=True))

    os.makedirs(DATA_DIR, exist_ok=True)
    df_combined.to_csv(os.path.join(DATA_DIR, f"{info['archivo']}.csv"), index=False)
    print(f"  [{id_var:4}] +{len(df_nuevo)} registros -> total {len(df_combined)}")
    return df_combined


def df_a_dict(id_var, info, df):
    if df.empty or "valor" not in df.columns:
        return None
    df = df.dropna(subset=["valor"]).sort_values("fecha").reset_index(drop=True)
    if df.empty:
        return None

    fechas  = df["fecha"].dt.strftime("%Y-%m-%d").tolist()
    valores = [round(v, 4) for v in df["valor"].tolist()]
    ultimo  = valores[-1]
    ultimo_fecha = fechas[-1]

    # variacion 30 dias
    cutoff_30 = df["fecha"].iloc[-1] - timedelta(days=30)
    df_30 = df[df["fecha"] <= cutoff_30]
    val_30 = df_30["valor"].iloc[-1] if not df_30.empty else None
    var_30d = round((ultimo - val_30) / abs(val_30) * 100, 2) if val_30 and val_30 != 0 else None

    # variacion 1 año
    cutoff_1a = df["fecha"].iloc[-1] - timedelta(days=365)
    df_1a = df[df["fecha"] <= cutoff_1a]
    val_1a = df_1a["valor"].iloc[-1] if not df_1a.empty else None
    var_1a = round((ultimo - val_1a) / abs(val_1a) * 100, 2) if val_1a and val_1a != 0 else None

    return {
        "id":           id_var,
        "nombre":       info["nombre"],
        "unidad":       info["unidad"],
        "grupo":        info["grupo"],
        "color":        info["color"],
        "fechas":       fechas,
        "valores":      valores,
        "ultimo":       ultimo,
        "ultimo_fecha": ultimo_fecha,
        "var_30d":      var_30d,
        "var_1a":       var_1a,
    }


def fetch_datos(actualizar=False):
    datos = {}
    for id_var, info in VARIABLES.items():
        try:
            df = cargar_desde_csv(info)
            if actualizar:
                df = actualizar_con_api(id_var, info, df)
            elif df.empty:
                print(f"  [{id_var:4}] sin CSV local — ejecuta con --actualizar")
                continue
            d = df_a_dict(id_var, info, df)
            if d:
                datos[id_var] = d
        except Exception as e:
            print(f"  [{id_var:4}] error: {e}")
    return datos


def generar_json(datos):
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "kpi_ids":      KPI_IDS,
        "variables":    {str(id_var): d for id_var, d in datos.items()},
    }
    path = os.path.join(BASE_DIR, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    total_pts = sum(len(d["fechas"]) for d in datos.values())
    print(f"\ndata.json actualizado — {len(datos)} variables — {total_pts:,} puntos de datos")


def main():
    parser = argparse.ArgumentParser(description="BCRA Dashboard Generator")
    parser.add_argument("--actualizar", action="store_true",
                        help="Descarga datos nuevos desde la API BCRA.")
    args = parser.parse_args()

    print("=== BCRA Dashboard Generator ===")
    print("Modo: actualizando API..." if args.actualizar else "Modo: datos locales (--actualizar para refrescar)")

    datos = fetch_datos(actualizar=args.actualizar)
    if datos:
        generar_json(datos)
    else:
        print("Sin datos. Ejecuta con --actualizar para descargar.")

if __name__ == "__main__":
    main()
