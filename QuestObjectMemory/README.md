# Quest Object Memory

This component stores object observations from the Quest application and exposes retrieval tasks to the YOR robot.

The committed sample data includes:

- `database/object_memory.db` — SQLite database with 12 object observations and 2 retrieval tasks.
- `database/schema.sql` — human-readable database schema.
- `images/full/cup_test_001.png` and `images/crops/cup_test_001.png` — sample full-frame and cropped detections.
- `server/memory_server.py` — FastAPI service used by the Quest and robot clients.

## Run locally

Python 3.12 was used for the current environment.

```powershell
cd QuestObjectMemory
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server.memory_server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/docs` for the generated API documentation or `http://localhost:8000/health` for a health check.

By default, the service reads and writes `database/` and `images/` under this directory. Set `QUEST_OBJECT_MEMORY_DIR` to use another data directory:

```powershell
$env:QUEST_OBJECT_MEMORY_DIR = 'C:\path\to\QuestObjectMemory'
```

## Main API routes

- `POST /objects` — save an object observation.
- `POST /objects/{observation_id}/images` — attach full and cropped images.
- `GET /objects/search?label=...` — find stored observations with images.
- `POST /objects/{observation_id}/confirm` — create a retrieval task after user confirmation.
- `GET /tasks/next` — return the oldest queued task.
- `PUT /tasks/{task_id}/status` — update robot task progress.

The service currently permits all CORS origins and has no authentication. Keep it on a trusted development network unless those controls are tightened.
