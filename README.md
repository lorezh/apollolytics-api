# apollolytics-api

## Installation

### Install dependencies

```bash
pip install -r requirements.txt
```

## update db through alembic

cd into detection_api

```bash
alembic upgrade head
```

## Start the Server
uvicorn detection_api.app:app --host 0.0.0.0 --port 8000 --reload
