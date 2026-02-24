#!/usr/bin/env python3
import json
import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
from bcra_api_client import BCRAClient

# Directorio base del script (independiente de desde dónde se corra)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

VARIABLES = {
    1:  {"nombre": "Reservas Internacionales", "unidad": "USD millones", "archivo": "reservas"},
    4:  {"nombre": "Tipo de Cambio (B 9791)",   "unidad": "ARS/USD",      "archivo": "tipo_cambio_oficial"},
    5:  {"nombre": "TC Referencia (A 3500)",     "unidad": "ARS/USD",      "archivo": "tipo_cambio_referencia"},
    7:  {"nombre": "BADLAR Bancos Privados",     "unidad": "% TNA",        "archivo": "badlar"},
    12: {"nombre": "Tasa Plazo Fijo",            "unidad": "% TNA",        "archivo": "tasa_plazo_fijo"},
    15: {"nombre": "Base Monetaria",             "unidad": "millones ARS", "archivo": "base_monetaria"},
    27: {"nombre": "Inflación Mensual",          "unidad": "%",            "archivo": "inflacion"},
}

# Variables donde el eje Y arranca en 0
ZERO_BASED = {1, 15, 27}

COLORES = {
    1:  "#00e5b8",
    4:  "#ff6b6b",
    5:  "#ff9f43",
    7:  "#a29bfe",
    12: "#74b9ff",
    15: "#55efc4",
    27: "#fd79a8",
}


def cargar_desde_csv(info):
    """Carga datos históricos desde el CSV local."""
    path = os.path.join(DATA_DIR, f"{info['archivo']}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["fecha"])
    if "fecha" in df.columns:
        df = df.sort_values("fecha").reset_index(drop=True)
    return df


def actualizar_con_api(id_var, info, df_local):
    """Llama a la API solo para fechas nuevas y mergea con el histórico local."""
    bcra = BCRAClient()
    hasta = datetime.now().strftime("%Y-%m-%d")

    if df_local.empty:
        # Sin datos locales: descargar los últimos 2 años completos
        desde = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    else:
        ultimo = df_local["fecha"].max()
        desde = (ultimo + timedelta(days=1)).strftime("%Y-%m-%d")
        if desde > hasta:
            print(f"  [var {id_var}] Ya está al día ({ultimo.date()}).")
            return df_local

    print(f"  [var {id_var}] Descargando desde {desde}...")
    df_nuevo = bcra.get_datos_historicos(id_var, desde=desde, hasta=hasta)

    if df_nuevo.empty:
        print(f"  [var {id_var}] Sin datos nuevos en la API.")
        return df_local

    df_combined = pd.concat([df_local, df_nuevo], ignore_index=True)
    df_combined = (df_combined
                   .drop_duplicates(subset=["fecha"])
                   .sort_values("fecha")
                   .reset_index(drop=True))

    os.makedirs(DATA_DIR, exist_ok=True)
    df_combined.to_csv(os.path.join(DATA_DIR, f"{info['archivo']}.csv"), index=False)
    print(f"  [var {id_var}] +{len(df_nuevo)} registros -> total {len(df_combined)}")
    return df_combined


def df_a_dict(info, df, color="#ffffff"):
    """Convierte un DataFrame en la estructura que usa el dashboard."""
    if df.empty or "valor" not in df.columns:
        return None
    fechas   = df["fecha"].dt.strftime("%Y-%m-%d").tolist()
    valores  = df["valor"].tolist()
    ultimo   = valores[-1] if valores else None
    primero  = valores[0]  if valores else None
    variacion = ((ultimo - primero) / primero * 100) if primero and ultimo else None
    return {
        "nombre":    info["nombre"],
        "unidad":    info["unidad"],
        "color":     color,
        "fechas":    fechas,
        "valores":   valores,
        "ultimo":    ultimo,
        "variacion": variacion,
    }


def fetch_datos(actualizar=False):
    datos = {}
    for id_var, info in VARIABLES.items():
        try:
            df = cargar_desde_csv(info)

            if actualizar:
                df = actualizar_con_api(id_var, info, df)
            elif df.empty:
                print(f"  [var {id_var}] Sin CSV local. Ejecutá con --actualizar para descargar.")
                continue

            d = df_a_dict(info, df, color=COLORES.get(id_var, "#ffffff"))
            if d:
                datos[id_var] = d
            else:
                print(f"  [var {id_var}] Sin columna 'valor' o sin datos.")
        except Exception as e:
            print(f"  [var {id_var}] Error: {e}")
    return datos


def generar_html(datos):
    """Inyecta los datos en el template HTML y escribe index.html."""
    lines = []
    for id_var, d in datos.items():
        lines.append(f"ALL_DATA[{id_var}] = {json.dumps(d)};")
    all_data_js = "\n".join(lines)

    template = os.path.join(BASE_DIR, "template.html")
    with open(template, "r", encoding="utf-8") as f:
        html = f.read()

    MARKER = "// PLACEHOLDER_DATA — el script reemplaza esta línea con los datos reales\nconst ALL_DATA = {};"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    reemplazo = f"// Datos generados: {timestamp}\nconst ALL_DATA = {{}};\n{all_data_js}"
    if MARKER not in html:
        print("ADVERTENCIA: no se encontró el marcador en el template. Verificá template.html.")
    html = html.replace(MARKER, reemplazo)

    out = os.path.join(BASE_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    total_pts = sum(len(d["fechas"]) for d in datos.values())
    print(f"\nindex.html generado — {len(datos)} variables — {total_pts:,} puntos de datos — {len(html):,} bytes")


def main():
    parser = argparse.ArgumentParser(description="BCRA Dashboard Generator")
    parser.add_argument(
        "--actualizar",
        action="store_true",
        help="Llama a la API para traer datos nuevos y actualiza los CSVs locales.",
    )
    args = parser.parse_args()

    print("=== BCRA Dashboard Generator ===")
    if args.actualizar:
        print("Modo: actualizando datos desde la API BCRA...")
    else:
        print("Modo: usando datos históricos locales (pasá --actualizar para refrescar).")

    datos = fetch_datos(actualizar=args.actualizar)
    if datos:
        generar_html(datos)
    else:
        print("Sin datos. Ejecutá con --actualizar para descargar desde la API.")

if __name__ == "__main__":
    main()
