# Gerald Gateway
## Dependencies

- Python 3.10+
- Docker
- PostgreSQL
- Terraform

## Local Install using virtual environment (venv)

1) Create virtual env
```bash
python -m venv venv
```

2) Activate environment
```bash
# Unix / Linux / macOS
source venv/bin/activate
# Windows (CMD)
venv\Scripts\activate.bat
```

3) Install dependencies
```bash
# For deveopment and testing purpose
pip install -r requirements-dev.txt
# For production or just running
pip install -r requirements.txt
```

4) Run test
```bash
python -m pytest
```

5) Run Datadog Agent
```bash
docker compose up -d
## to restart the agent (apply changes)
docker restart dd-agent
```

6) Run Terraform monitors
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# use datadog keys (secrets)
# datadog_api_key = "your-datadog-api-key-here"
# datadog_app_key = "your-datadog-app-key-here"
terraform init
terraform plan
```

7) Run Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

8) Build Datadog Dashboard
```bash
DD_API_KEY=dd_api_key DD_APP_KEY=dd_app_key python scripts/import_dashboard.py
```