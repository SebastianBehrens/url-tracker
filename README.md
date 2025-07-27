This repository contains a simple web application that tracks the locations of URLs over time.
In intervals some urls are polled for their location using the (ip-api.com)[https://ip-api.com] API.

# Launch
## Without Docker
With uvicorn:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --reload-include "config.yml"
```

With python:

```bash
.venv/bin/python run.py
```
## Using Docker
```bash
docker compose -f app/compose.yml up --build
```