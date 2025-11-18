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

5) Copy env (create apikey and app key in Datadog)
```bash
cp .env.example .env
```

6) Run Datadog Agent 
```bash
docker compose up -d
## to restart the agent (apply changes)
docker restart dd-agent
```

7) Run Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

8) Build Datadog Dashboard
```bash
DD_API_KEY=dd_api_key DD_APP_KEY=dd_app_key python scripts/import_dashboard.py
```