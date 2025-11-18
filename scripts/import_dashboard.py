#!/usr/bin/env python3
"""
Script para importar el dashboard de Datadog desde el archivo JSON.

Uso:
    python scripts/import_dashboard.py

O con variables de entorno:
    DD_API_KEY=tu_api_key DD_APP_KEY=tu_app_key python scripts/import_dashboard.py
"""

import os
import json
import sys
from pathlib import Path

try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v1.api.dashboards_api import DashboardsApi
    from datadog_api_client.v1.model.dashboard import Dashboard
except ImportError:
    print("Error: datadog-api-client no está instalado.")
    print("Instala con: pip install datadog-api-client")
    sys.exit(1)


def load_dashboard_json(file_path: str) -> dict:
    """Carga el archivo JSON del dashboard."""
    dashboard_path = Path(__file__).parent.parent / file_path
    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found: {dashboard_path}")
    
    with open(dashboard_path, 'r') as f:
        return json.load(f)


def create_dashboard(api_key: str, app_key: str, dashboard_data: dict):
    """Crea el dashboard en Datadog usando la API."""
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    
    with ApiClient(configuration) as api_client:
        api_instance = DashboardsApi(api_client)
        
        try:
            # Crear el dashboard
            dashboard = Dashboard(**dashboard_data)
            response = api_instance.create_dashboard(body=dashboard)
            
            print(f"✅ Dashboard creado exitosamente!")
            print(f"   ID: {response.id}")
            print(f"   URL: https://app.datadoghq.com{response.url}")
            return response
        except Exception as e:
            print(f"❌ Error al crear el dashboard: {e}")
            if hasattr(e, 'body'):
                print(f"   Detalles: {e.body}")
            raise


def main():
    """Función principal."""
    # Obtener credenciales de variables de entorno o terraform.tfvars
    # api_key = os.getenv("DD_API_KEY") or os.getenv("DATADOG_API_KEY")
    # app_key = os.getenv("DD_APP_KEY") or os.getenv("DATADOG_APP_KEY")
    api_key = "fcbd7c891d95343fb27e59f537b1761a"
    app_key = "b9ac015912cdf80541ccb2da8befcd87f032d9c3"
    
    # Intentar leer de terraform.tfvars si no están en env
    if not api_key or not app_key:
        tfvars_path = Path(__file__).parent.parent / "terraform" / "terraform.tfvars"
        if tfvars_path.exists():
            print("📖 Leyendo credenciales de terraform.tfvars...")
            # Parse simple de terraform.tfvars
            with open(tfvars_path, 'r') as f:
                content = f.read()
                for line in content.split('\n'):
                    if 'datadog_api_key' in line and '=' in line:
                        api_key = line.split('=')[1].strip().strip('"')
                    elif 'datadog_app_key' in line and '=' in line:
                        app_key = line.split('=')[1].strip().strip('"')
    
    if not api_key or not app_key:
        print("❌ Error: No se encontraron credenciales de Datadog.")
        print("\nOpciones:")
        print("1. Variables de entorno:")
        print("   export DD_API_KEY=tu_api_key")
        print("   export DD_APP_KEY=tu_app_key")
        print("2. O edita terraform/terraform.tfvars con tus credenciales")
        sys.exit(1)
    
    # Cargar el dashboard (usar el archivo corregido con namespaces)
    dashboard_file = "metrics/dashboard_datadog_fixed_namespaces.json"
    print(f"📂 Cargando dashboard desde {dashboard_file}...")
    try:
        dashboard_data = load_dashboard_json(dashboard_file)
    except Exception as e:
        print(f"❌ Error al cargar el dashboard: {e}")
        sys.exit(1)
    
    # Crear el dashboard
    print("🚀 Creando dashboard en Datadog...")
    try:
        response = create_dashboard(api_key, app_key, dashboard_data)
        print(f"\n✨ Dashboard disponible en: {response.url}")
    except Exception as e:
        print(f"\n❌ No se pudo crear el dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

