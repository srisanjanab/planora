# Planora

Personal planner: recurring bills, trips with expense splitting, expenses and groceries.

## Backend setup (Windows 11, PowerShell)

```powershell
docker compose up -d        # starts PostgreSQL (run from the planora folder)
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Open http://127.0.0.1:8000/docs to try the API (use the Authorize button after registering).

## Run tests

```powershell
python -m pytest -q
```

## Database

PostgreSQL runs in Docker (see `docker-compose.yml`). Useful commands:

```powershell
docker compose up -d      # start
docker compose stop       # stop (data is kept)
docker compose down -v    # stop and DELETE all data
```

Port 5432 already used by a local Postgres? Change `"5432:5432"` to `"5433:5432"` in
`docker-compose.yml` and use port 5433 in `DATABASE_URL`.
No Docker? Set `DATABASE_URL=sqlite:///./planora.db` in `.env`.
