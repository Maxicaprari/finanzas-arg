#!/usr/bin/env python3
"""
Cliente para la API de Estadísticas del BCRA (Banco Central de Argentina)
Permite consultar principales variables económicas y monetarias
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import urllib3
from typing import Optional, List, Dict

# Suprimir warnings de SSL (común con APIs de gobierno argentino)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BCRAClient:
    """Cliente para interactuar con la API del BCRA"""
    
    BASE_URL = "https://api.bcra.gob.ar/estadisticas/v4.0"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # APIs gov.ar suelen tener problemas de SSL
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def get_metodologia(self, id_variable: Optional[int] = None) -> Dict:
        """
        Obtiene la metodología de las variables
        
        Args:
            id_variable: ID de la variable específica (opcional)
            
        Returns:
            Diccionario con la metodología
        """
        if id_variable:
            url = f"{self.BASE_URL}/Metodologia/{id_variable}"
        else:
            url = f"{self.BASE_URL}/Metodologia"
        
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_variables_monetarias(self, id_variable: Optional[int] = None, 
                                  desde: Optional[str] = None,
                                  hasta: Optional[str] = None) -> Dict:
        """
        Obtiene datos de variables monetarias
        
        Args:
            id_variable: ID de la variable específica (opcional)
            desde: Fecha desde en formato YYYY-MM-DD (opcional)
            hasta: Fecha hasta en formato YYYY-MM-DD (opcional)
            
        Returns:
            Diccionario con los datos
        """
        if id_variable:
            url = f"{self.BASE_URL}/Monetarias/{id_variable}"
        else:
            url = f"{self.BASE_URL}/Monetarias"
        
        params = {}
        if desde:
            params['desde'] = desde
        if hasta:
            params['hasta'] = hasta
            
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def listar_variables(self) -> pd.DataFrame:
        """
        Lista todas las variables disponibles con su descripción

        Returns:
            DataFrame con las variables disponibles
        """
        data = self.get_metodologia()

        if 'results' in data:
            df = pd.DataFrame(data['results'])
            if not df.empty:
                cols_disponibles = [c for c in ['idVariable', 'descripcion', 'nombreCorto'] if c in df.columns]
                return df[cols_disponibles] if cols_disponibles else df
        return pd.DataFrame()
    
    def _parsear_respuesta(self, data: Dict) -> pd.DataFrame:
        """Convierte la respuesta de la API en un DataFrame limpio."""
        if 'results' not in data:
            return pd.DataFrame()

        results = data['results']
        if isinstance(results, dict) and 'detalle' in results:
            df = pd.DataFrame(results['detalle'])
        elif isinstance(results, list) and len(results) > 0 and 'detalle' in results[0]:
            df = pd.DataFrame(results[0]['detalle'])
        else:
            df = pd.DataFrame(results)

        if not df.empty and 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df = df.sort_values('fecha').reset_index(drop=True)
        return df

    def get_datos_variable(self, id_variable: int,
                           dias_atras: int = 30) -> pd.DataFrame:
        """
        Obtiene datos de una variable específica

        Args:
            id_variable: ID de la variable
            dias_atras: Cantidad de días hacia atrás a consultar

        Returns:
            DataFrame con los datos de la variable
        """
        fecha_hasta = datetime.now().strftime('%Y-%m-%d')
        fecha_desde = (datetime.now() - timedelta(days=dias_atras)).strftime('%Y-%m-%d')

        data = self.get_variables_monetarias(
            id_variable=id_variable,
            desde=fecha_desde,
            hasta=fecha_hasta
        )
        return self._parsear_respuesta(data)

    def get_datos_historicos(self, id_variable: int,
                             desde: str,
                             hasta: Optional[str] = None) -> pd.DataFrame:
        """
        Obtiene datos históricos de una variable en un rango de fechas explícito.

        Args:
            id_variable: ID de la variable
            desde: Fecha de inicio en formato YYYY-MM-DD
            hasta: Fecha de fin en formato YYYY-MM-DD (por defecto: hoy)

        Returns:
            DataFrame con los datos históricos
        """
        if hasta is None:
            hasta = datetime.now().strftime('%Y-%m-%d')

        data = self.get_variables_monetarias(
            id_variable=id_variable,
            desde=desde,
            hasta=hasta
        )
        return self._parsear_respuesta(data)

    def get_historico_todas_variables(self, desde: str,
                                      hasta: Optional[str] = None,
                                      ids_variables: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Obtiene datos históricos de múltiples variables y los combina en un único DataFrame.

        Args:
            desde: Fecha de inicio en formato YYYY-MM-DD
            hasta: Fecha de fin en formato YYYY-MM-DD (por defecto: hoy)
            ids_variables: Lista de IDs a consultar. Si es None, usa las variables disponibles.

        Returns:
            DataFrame combinado con columnas: fecha, idVariable, descripcion, valor
        """
        if hasta is None:
            hasta = datetime.now().strftime('%Y-%m-%d')

        if ids_variables is None:
            variables_df = self.listar_variables()
            if variables_df.empty:
                print("No se pudieron obtener las variables disponibles.")
                return pd.DataFrame()
            ids_variables = variables_df['idVariable'].tolist()
            desc_map = dict(zip(variables_df['idVariable'], variables_df.get('descripcion', variables_df.iloc[:, 1])))
        else:
            desc_map = {}

        frames = []
        total = len(ids_variables)
        for i, id_var in enumerate(ids_variables, 1):
            print(f"  Descargando variable {id_var} ({i}/{total})...", end='\r')
            try:
                df = self.get_datos_historicos(id_var, desde, hasta)
                if not df.empty:
                    df['idVariable'] = id_var
                    if id_var in desc_map:
                        df['descripcion'] = desc_map[id_var]
                    frames.append(df)
            except Exception as e:
                print(f"\n  Error en variable {id_var}: {e}")

        print()  # nueva línea tras el progreso
        if not frames:
            return pd.DataFrame()

        combinado = pd.concat(frames, ignore_index=True)
        # Reordenar columnas: fecha primero
        cols = ['fecha', 'idVariable'] + [c for c in combinado.columns if c not in ('fecha', 'idVariable')]
        return combinado[cols]

    def get_multiple_variables(self, ids_variables: List[int],
                               dias_atras: int = 30) -> Dict[int, pd.DataFrame]:
        """
        Obtiene datos de múltiples variables

        Args:
            ids_variables: Lista de IDs de variables
            dias_atras: Cantidad de días hacia atrás a consultar

        Returns:
            Diccionario con DataFrames por cada variable
        """
        resultados = {}

        for id_var in ids_variables:
            try:
                df = self.get_datos_variable(id_var, dias_atras)
                resultados[id_var] = df
            except Exception as e:
                print(f"Error al obtener variable {id_var}: {e}")
                resultados[id_var] = pd.DataFrame()

        return resultados


def main():
    """Función principal que consulta la API del BCRA"""
    bcra = BCRAClient()

    # 1. Listar todas las variables
    print("=" * 60)
    print("VARIABLES DISPONIBLES EN LA API DEL BCRA")
    print("=" * 60)
    try:
        variables = bcra.listar_variables()
        if not variables.empty:
            print(variables.to_string(index=False))
        else:
            print("No se pudieron obtener las variables.")
    except Exception as e:
        print(f"Error al listar variables: {e}")

    # 2. Datos históricos de Reservas Internacionales (ID: 1) — último año
    print("\n" + "=" * 60)
    print("RESERVAS INTERNACIONALES — histórico último año")
    print("=" * 60)
    try:
        desde = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        reservas = bcra.get_datos_historicos(id_variable=1, desde=desde)
        if not reservas.empty:
            print(f"Registros obtenidos: {len(reservas)}")
            print(reservas.tail(10).to_string(index=False))
            reservas.to_csv('reservas_historico.csv', index=False)
            print("\nDatos guardados en reservas_historico.csv")
        else:
            print("No se obtuvieron datos de reservas.")
    except Exception as e:
        print(f"Error al obtener reservas: {e}")

    # 3. Datos históricos de variables clave: Reservas (1), Base Monetaria (15), Tipo de Cambio (4)
    print("\n" + "=" * 60)
    print("VARIABLES CLAVE — histórico último año")
    print("=" * 60)
    IDS_CLAVE = [1, 4, 15]  # Reservas, TC mayorista, Base monetaria
    try:
        desde = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        historico = bcra.get_historico_todas_variables(desde=desde, ids_variables=IDS_CLAVE)
        if not historico.empty:
            print(f"Registros totales: {len(historico)}")
            print(historico.tail(15).to_string(index=False))
            historico.to_csv('historico_variables_bcra.csv', index=False)
            print("\nDatos guardados en historico_variables_bcra.csv")
        else:
            print("No se obtuvieron datos.")
    except Exception as e:
        print(f"Error al obtener histórico de variables: {e}")

    # 4. Descarga completa de TODAS las variables (puede tardar varios minutos)
    # Descomenta las siguientes líneas para ejecutarlo:
    # print("\n" + "=" * 60)
    # print("TODAS LAS VARIABLES — histórico último año")
    # print("=" * 60)
    # desde = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    # todo = bcra.get_historico_todas_variables(desde=desde)
    # if not todo.empty:
    #     todo.to_csv('historico_completo_bcra.csv', index=False)
    #     print(f"Guardado historico_completo_bcra.csv con {len(todo)} registros")

    print("\n" + "=" * 60)
    print("Consulta finalizada.")


if __name__ == "__main__":
    main()