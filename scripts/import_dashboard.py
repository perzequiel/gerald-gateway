#!/usr/bin/env python3
"""
Script to import the Datadog dashboard from the JSON file.

Usage:
    python scripts/import_dashboard.py

Or with environment variables:
    DD_API_KEY=dd_api_key DD_APP_KEY=dd_app_key python scripts/import_dashboard.py
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
    print("Error: datadog-api-client is not installed.")
    print("Instala con: pip install datadog-api-client")
    sys.exit(1)


def load_dashboard_json(file_path: str) -> dict:
    """Load the dashboard JSON file."""
    dashboard_path = Path(__file__).parent.parent / file_path
    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found: {dashboard_path}")
    
    with open(dashboard_path, 'r') as f:
        return json.load(f)


def create_dashboard(api_key: str, app_key: str, dashboard_data: dict):
    """Create the dashboard in Datadog using the API."""
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    
    with ApiClient(configuration) as api_client:
        api_instance = DashboardsApi(api_client)
        
        try:
            # Create the dashboard
            dashboard = Dashboard(**dashboard_data)
            response = api_instance.create_dashboard(body=dashboard)
            
            print(f"✅ Dashboard created successfully!")
            print(f"   ID: {response.id}")
            print(f"   URL: https://app.datadoghq.com{response.url}")
            return response
        except Exception as e:
            print(f"❌ Error creating the dashboard: {e}")
            if hasattr(e, 'body'):
                print(f"   Details: {e.body}")
            raise


def main():
    """Main function."""
    # Obtener credenciales de variables de entorno o terraform.tfvars
    api_key = os.getenv("DD_API_KEY") or os.getenv("DATADOG_API_KEY")
    app_key = os.getenv("DD_APP_KEY") or os.getenv("DATADOG_APP_KEY")
    
    # Try to read from terraform.tfvars if not in env
    if not api_key or not app_key:
        tfvars_path = Path(__file__).parent.parent / "terraform" / "terraform.tfvars"
        if tfvars_path.exists():
            print("📖 Reading credentials from terraform.tfvars...")
            # Parse simple de terraform.tfvars
            with open(tfvars_path, 'r') as f:
                content = f.read()
                for line in content.split('\n'):
                    if 'datadog_api_key' in line and '=' in line:
                        api_key = line.split('=')[1].strip().strip('"')
                    elif 'datadog_app_key' in line and '=' in line:
                        app_key = line.split('=')[1].strip().strip('"')
    
    if not api_key or not app_key:
        print("❌ Error: No credentials found for Datadog.")
        print("\nOptions:")
        print("1. Variables de entorno:")
        print("   export DD_API_KEY=dd_api_key")
        print("   export DD_APP_KEY=dd_app_key")
        print("2. Or edit terraform/terraform.tfvars with your credentials")
        sys.exit(1)
    
    # Load the dashboard (use the corrected file with namespaces)
    dashboard_file = "metrics/dashboard_datadog_fixed_namespaces.json"
    print(f"📂 Loading dashboard from {dashboard_file}...")
    try:
        dashboard_data = load_dashboard_json(dashboard_file)
    except Exception as e:
        print(f"❌ Error loading the dashboard: {e}")
        sys.exit(1)
    
    # Create the dashboard
    print("🚀 Creating dashboard in Datadog...")
    try:
        response = create_dashboard(api_key, app_key, dashboard_data)
        print(f"\n✨ Dashboard disponible en: {response.url}")
    except Exception as e:
        print(f"\n❌ Could not create the dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

