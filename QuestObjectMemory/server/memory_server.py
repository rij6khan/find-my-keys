import os
import uuid
import sqlite3

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(
    os.environ.get(
        "QUEST_OBJECT_MEMORY_DIR",
        Path(__file__).resolve().parents[1]
    )
).expanduser().resolve()

DATABASE_DIR = (
    BASE_DIR / "database"
)

DATABASE_PATH = (
    DATABASE_DIR / "object_memory.db"
)

IMAGES_DIR = (
    BASE_DIR / "images"
)

FULL_IMAGES_DIR = (
    IMAGES_DIR / "full"
)

CROP_IMAGES_DIR = (
    IMAGES_DIR / "crops"
)


# ============================================================
# Create directories
# ============================================================

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

FULL_IMAGES_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CROP_IMAGES_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="Quest-YOR Object Memory Server",
    version="2.0"
)


# ============================================================
# CORS
#
# Useful if another computer/browser eventually accesses
# the API from a web interface.
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Static image server
#
# Example:
# http://172.25.230.76:8000/images/crops/cup_test_001.png
# ============================================================

app.mount(
    "/images",
    StaticFiles(
        directory=str(IMAGES_DIR)
    ),
    name="images"
)


# ============================================================
# Database helper
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = (
        sqlite3.Row
    )

    return conn


# ============================================================
# Initialize database
# ============================================================

def initialize_database():

    conn = get_db()


    # --------------------------------------------------------
    # Object observations
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS object_observations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            observation_id TEXT NOT NULL UNIQUE,

            label TEXT NOT NULL,

            confidence REAL NOT NULL,

            timestamp TEXT NOT NULL,

            quest_x REAL NOT NULL,
            quest_y REAL NOT NULL,
            quest_z REAL NOT NULL,

            yor_world_x REAL,
            yor_world_y REAL,
            yor_world_z REAL,

            full_image_path TEXT,
            crop_image_path TEXT,

            created_at TEXT NOT NULL
        )
        """
    )


    # --------------------------------------------------------
    # Retrieval tasks
    #
    # User confirms exact object →
    # server creates queued task →
    # YOR retrieves it.
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS retrieval_tasks (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_id TEXT NOT NULL UNIQUE,

            observation_id TEXT NOT NULL,

            status TEXT NOT NULL,

            created_at TEXT NOT NULL,

            updated_at TEXT,

            FOREIGN KEY(observation_id)
                REFERENCES object_observations(
                    observation_id
                )
        )
        """
    )


    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# Pydantic models
# ============================================================

class QuestObject(BaseModel):

    observation_id: str

    label: str

    confidence: float

    timestamp: str

    quest_x: float
    quest_y: float
    quest_z: float

    yor_world_x: Optional[float] = None
    yor_world_y: Optional[float] = None
    yor_world_z: Optional[float] = None


class YorPositionUpdate(BaseModel):

    yor_world_x: float
    yor_world_y: float
    yor_world_z: float


class ObjectConfirmation(BaseModel):

    confirmed: bool


class TaskStatusUpdate(BaseModel):

    status: str


# ============================================================
# Utility
# ============================================================

def clean_label(
    label: str
) -> str:

    if label is None:
        return ""

    return label.strip()


def row_to_object(
    row
):

    result = dict(row)


    # --------------------------------------------------------
    # Full image URL
    # --------------------------------------------------------

    if result.get(
        "full_image_path"
    ):

        result[
            "full_image_url"
        ] = (
            "/images/" +
            result[
                "full_image_path"
            ]
        )

    else:

        result[
            "full_image_url"
        ] = None


    # --------------------------------------------------------
    # Crop URL
    # --------------------------------------------------------

    if result.get(
        "crop_image_path"
    ):

        result[
            "crop_image_url"
        ] = (
            "/images/" +
            result[
                "crop_image_path"
            ]
        )

    else:

        result[
            "crop_image_url"
        ] = None


    # --------------------------------------------------------
    # Preferred image
    #
    # Crop first.
    # Full frame used only as fallback.
    # --------------------------------------------------------

    if result.get(
        "crop_image_url"
    ):

        result[
            "image_url"
        ] = result[
            "crop_image_url"
        ]

    else:

        result[
            "image_url"
        ] = result.get(
            "full_image_url"
        )


    return result


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "database": str(
            DATABASE_PATH
        )
    }


# ============================================================
# Save Quest observation
# ============================================================

@app.post("/objects")
def save_object(
    obj: QuestObject
):

    cleanLabel = clean_label(
        obj.label
    )


    if not cleanLabel:

        raise HTTPException(
            status_code=400,
            detail="Object label is empty."
        )


    conn = get_db()


    # --------------------------------------------------------
    # Prevent duplicate observation ID
    # --------------------------------------------------------

    existing = conn.execute(
        """
        SELECT id
        FROM object_observations
        WHERE observation_id = ?
        """,
        (
            obj.observation_id,
        )
    ).fetchone()


    if existing is not None:

        conn.close()

        raise HTTPException(
            status_code=409,
            detail=(
                "Observation ID "
                "already exists."
            )
        )


    cursor = conn.execute(
        """
        INSERT INTO object_observations (

            observation_id,

            label,

            confidence,

            timestamp,

            quest_x,
            quest_y,
            quest_z,

            yor_world_x,
            yor_world_y,
            yor_world_z,

            full_image_path,
            crop_image_path,

            created_at

        )
        VALUES (
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            NULL, NULL,
            ?
        )
        """,
        (
            obj.observation_id,

            cleanLabel,

            obj.confidence,

            obj.timestamp,

            obj.quest_x,
            obj.quest_y,
            obj.quest_z,

            obj.yor_world_x,
            obj.yor_world_y,
            obj.yor_world_z,

            datetime.now(
                timezone.utc
            ).isoformat()
        )
    )


    conn.commit()


    database_id = (
        cursor.lastrowid
    )


    conn.close()


    print()
    print(
        "=============================="
    )
    print(
        "OBJECT SAVED TO DATABASE"
    )
    print(
        "=============================="
    )
    print(
        "Database ID:",
        database_id
    )
    print(
        "Observation:",
        obj.observation_id
    )
    print(
        "Label:",
        cleanLabel
    )
    print(
        "Confidence:",
        obj.confidence
    )
    print(
        "Quest XYZ:",
        obj.quest_x,
        obj.quest_y,
        obj.quest_z
    )
    print(
        "=============================="
    )
    print()


    return {
        "status": "saved",
        "database_id":
            database_id,
        "observation_id":
            obj.observation_id,
        "label":
            cleanLabel
    }


# ============================================================
# Upload images for observation
#
# full_image = required
# crop_image = optional
# ============================================================

@app.post(
    "/objects/{observation_id}/images"
)
async def upload_images(
    observation_id: str,

    full_image: UploadFile = File(...),

    crop_image: Optional[
        UploadFile
    ] = File(None)
):

    conn = get_db()


    row = conn.execute(
        """
        SELECT *
        FROM object_observations
        WHERE observation_id = ?
        """,
        (
            observation_id,
        )
    ).fetchone()


    if row is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail=(
                "Observation "
                "not found."
            )
        )


    # --------------------------------------------------------
    # Save full image
    # --------------------------------------------------------

    full_suffix = (
        Path(
            full_image.filename
            or "image.png"
        ).suffix
        or ".png"
    )


    full_filename = (
        observation_id +
        full_suffix
    )


    full_path = (
        FULL_IMAGES_DIR /
        full_filename
    )


    full_bytes = (
        await full_image.read()
    )


    full_path.write_bytes(
        full_bytes
    )


    full_relative_path = (
        "full/" +
        full_filename
    )


    # --------------------------------------------------------
    # Save crop if supplied
    # --------------------------------------------------------

    crop_relative_path = None


    if crop_image is not None:

        crop_suffix = (
            Path(
                crop_image.filename
                or "crop.png"
            ).suffix
            or ".png"
        )


        crop_filename = (
            observation_id +
            crop_suffix
        )


        crop_path = (
            CROP_IMAGES_DIR /
            crop_filename
        )


        crop_bytes = (
            await crop_image.read()
        )


        crop_path.write_bytes(
            crop_bytes
        )


        crop_relative_path = (
            "crops/" +
            crop_filename
        )


    # --------------------------------------------------------
    # Update database
    # --------------------------------------------------------

    conn.execute(
        """
        UPDATE object_observations

        SET
            full_image_path = ?,
            crop_image_path =
                COALESCE(
                    ?,
                    crop_image_path
                )

        WHERE observation_id = ?
        """,
        (
            full_relative_path,
            crop_relative_path,
            observation_id
        )
    )


    conn.commit()
    conn.close()


    return {
        "status":
            "images_saved",

        "observation_id":
            observation_id,

        "full_image_url":
            (
                "/images/" +
                full_relative_path
            ),

        "crop_image_url":
            (
                "/images/" +
                crop_relative_path
            )
            if crop_relative_path
            else None
    }


# ============================================================
# Update YOR-world position
#
# Use this after applying your already-validated
# Quest → YOR transform.
# ============================================================

@app.put(
    "/objects/{observation_id}/yor-position"
)
def update_yor_position(
    observation_id: str,
    position: YorPositionUpdate
):

    conn = get_db()


    row = conn.execute(
        """
        SELECT id
        FROM object_observations
        WHERE observation_id = ?
        """,
        (
            observation_id,
        )
    ).fetchone()


    if row is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail=(
                "Observation "
                "not found."
            )
        )


    conn.execute(
        """
        UPDATE object_observations

        SET
            yor_world_x = ?,
            yor_world_y = ?,
            yor_world_z = ?

        WHERE
            observation_id = ?
        """,
        (
            position.yor_world_x,
            position.yor_world_y,
            position.yor_world_z,
            observation_id
        )
    )


    conn.commit()
    conn.close()


    return {
        "status":
            "yor_position_updated",

        "observation_id":
            observation_id,

        "yor_world_x":
            position.yor_world_x,

        "yor_world_y":
            position.yor_world_y,

        "yor_world_z":
            position.yor_world_z
    }


# ============================================================
# Get one exact observation by observation ID
# ============================================================

@app.get(
    "/objects/by-id/{observation_id}"
)
def get_object_by_id(
    observation_id: str
):

    conn = get_db()


    row = conn.execute(
        """
        SELECT *
        FROM object_observations
        WHERE observation_id = ?
        """,
        (
            observation_id,
        )
    ).fetchone()


    conn.close()


    if row is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Observation "
                "not found."
            )
        )


    return row_to_object(
        row
    )


# ============================================================
# Get latest object by label
#
# Correctly handles old values such as "cup\\r"
# ============================================================

@app.get(
    "/objects/latest/{label}"
)
def get_latest_object(
    label: str
):

    cleanLabel = clean_label(
        label
    )


    conn = get_db()


    row = conn.execute(
        """
        SELECT *

        FROM object_observations

        WHERE lower(
            trim(
                label,
                char(13) ||
                char(10) ||
                ' '
            )
        )
        =
        lower(
            trim(?)
        )

        ORDER BY id DESC

        LIMIT 1
        """,
        (
            cleanLabel,
        )
    ).fetchone()


    conn.close()


    if row is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"No object found "
                f"for label: "
                f"{cleanLabel}"
            )
        )


    return row_to_object(
        row
    )


# ============================================================
# List recent objects
# ============================================================

@app.get("/objects")
def list_objects(
    limit: int = 20
):

    # Prevent huge accidental requests.
    limit = max(
        1,
        min(
            limit,
            500
        )
    )


    conn = get_db()


    rows = conn.execute(
        """
        SELECT *

        FROM object_observations

        ORDER BY id DESC

        LIMIT ?
        """,
        (
            limit,
        )
    ).fetchall()


    conn.close()


    return [
        row_to_object(row)
        for row in rows
    ]


# ============================================================
# Search matching memories that have an image
#
# Quest uses this endpoint to ask:
#
# "Show me stored cup images."
#
# Example:
# /objects/search?label=cup
# ============================================================

@app.get(
    "/objects/search"
)
def search_objects(
    label: str,
    limit: int = 10
):

    cleanLabel = clean_label(
        label
    )


    limit = max(
        1,
        min(
            limit,
            100
        )
    )


    conn = get_db()


    rows = conn.execute(
        """
        SELECT *

        FROM object_observations

        WHERE lower(
            trim(
                label,
                char(13) ||
                char(10) ||
                ' '
            )
        )
        =
        lower(
            trim(?)
        )

        AND (
            crop_image_path
                IS NOT NULL

            OR

            full_image_path
                IS NOT NULL
        )

        ORDER BY id DESC

        LIMIT ?
        """,
        (
            cleanLabel,
            limit
        )
    ).fetchall()


    conn.close()


    objects = []


    for row in rows:

        objects.append(
            row_to_object(
                row
            )
        )


    return {
        "label":
            cleanLabel,

        "count":
            len(objects),

        "objects":
            objects
    }


# ============================================================
# User confirms or rejects exact object
#
# YES:
# creates queued task for YOR.
#
# NO:
# no task is created.
# Quest can show next candidate.
# ============================================================

@app.post(
    "/objects/{observation_id}/confirm"
)
def confirm_object(
    observation_id: str,
    confirmation: ObjectConfirmation
):

    conn = get_db()


    observation = conn.execute(
        """
        SELECT *

        FROM object_observations

        WHERE observation_id = ?
        """,
        (
            observation_id,
        )
    ).fetchone()


    if observation is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail=(
                "Observation "
                "not found."
            )
        )


    # --------------------------------------------------------
    # User selected NO
    # --------------------------------------------------------

    if not confirmation.confirmed:

        conn.close()


        return {
            "status":
                "rejected",

            "observation_id":
                observation_id,

            "label":
                observation[
                    "label"
                ]
        }


    # --------------------------------------------------------
    # Prevent accidental duplicate queued task
    # --------------------------------------------------------

    existing_task = conn.execute(
        """
        SELECT *

        FROM retrieval_tasks

        WHERE observation_id = ?

        AND status IN (
            'queued',
            'accepted',
            'navigating',
            'verifying',
            'grasping'
        )

        ORDER BY id DESC

        LIMIT 1
        """,
        (
            observation_id,
        )
    ).fetchone()


    if existing_task is not None:

        conn.close()


        return {
            "status":
                "already_queued",

            "task_id":
                existing_task[
                    "task_id"
                ],

            "observation_id":
                observation_id,

            "task_status":
                existing_task[
                    "status"
                ]
        }


    # --------------------------------------------------------
    # User selected YES
    # --------------------------------------------------------

    task_id = (
        uuid.uuid4().hex
    )


    now = datetime.now(
        timezone.utc
    ).isoformat()


    conn.execute(
        """
        INSERT INTO retrieval_tasks (

            task_id,

            observation_id,

            status,

            created_at,

            updated_at
        )

        VALUES (
            ?, ?, ?, ?, ?
        )
        """,
        (
            task_id,

            observation_id,

            "queued",

            now,

            now
        )
    )


    conn.commit()
    conn.close()


    print()
    print(
        "=============================="
    )
    print(
        "USER CONFIRMED OBJECT"
    )
    print(
        "=============================="
    )
    print(
        "Task:",
        task_id
    )
    print(
        "Observation:",
        observation_id
    )
    print(
        "Label:",
        observation[
            "label"
        ]
    )
    print(
        "Status: queued"
    )
    print(
        "=============================="
    )
    print()


    return {
        "status":
            "confirmed",

        "task_id":
            task_id,

        "observation_id":
            observation_id,

        "label":
            observation[
                "label"
            ],

        "task_status":
            "queued"
    }


# ============================================================
# YOR gets next queued retrieval task
# ============================================================

@app.get(
    "/tasks/next"
)
def get_next_task():

    conn = get_db()


    row = conn.execute(
        """
        SELECT

            t.id AS task_database_id,

            t.task_id,

            t.status,

            t.created_at
                AS task_created_at,

            o.id
                AS object_database_id,

            o.observation_id,

            o.label,

            o.confidence,

            o.timestamp,

            o.quest_x,
            o.quest_y,
            o.quest_z,

            o.yor_world_x,
            o.yor_world_y,
            o.yor_world_z,

            o.full_image_path,
            o.crop_image_path

        FROM retrieval_tasks t

        JOIN object_observations o

        ON
            t.observation_id =
            o.observation_id

        WHERE
            t.status = 'queued'

        ORDER BY
            t.id ASC

        LIMIT 1
        """
    ).fetchone()


    conn.close()


    if row is None:

        return {
            "task": None
        }


    task = dict(row)


    if task[
        "full_image_path"
    ]:

        task[
            "full_image_url"
        ] = (
            "/images/" +
            task[
                "full_image_path"
            ]
        )

    else:

        task[
            "full_image_url"
        ] = None


    if task[
        "crop_image_path"
    ]:

        task[
            "crop_image_url"
        ] = (
            "/images/" +
            task[
                "crop_image_path"
            ]
        )

    else:

        task[
            "crop_image_url"
        ] = None


    # Preferred reference image for YOR.
    if task[
        "crop_image_url"
    ]:

        task[
            "image_url"
        ] = task[
            "crop_image_url"
        ]

    else:

        task[
            "image_url"
        ] = task[
            "full_image_url"
        ]


    return {
        "task":
            task
    }


# ============================================================
# Get task status
#
# Quest can poll this to display:
# queued → navigating → verifying → completed
# ============================================================

@app.get(
    "/tasks/{task_id}"
)
def get_task(
    task_id: str
):

    conn = get_db()


    row = conn.execute(
        """
        SELECT

            t.*,

            o.label,

            o.observation_id,

            o.yor_world_x,
            o.yor_world_y,
            o.yor_world_z

        FROM retrieval_tasks t

        JOIN object_observations o

        ON
            t.observation_id =
            o.observation_id

        WHERE
            t.task_id = ?
        """,
        (
            task_id,
        )
    ).fetchone()


    conn.close()


    if row is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Task not found."
            )
        )


    return dict(row)


# ============================================================
# YOR updates task status
#
# Valid examples:
#
# accepted
# navigating
# verifying
# grasping
# completed
# failed
# ============================================================

@app.put(
    "/tasks/{task_id}/status"
)
def update_task_status(
    task_id: str,
    update: TaskStatusUpdate
):

    allowed_statuses = {
        "queued",
        "accepted",
        "navigating",
        "verifying",
        "grasping",
        "completed",
        "failed"
    }


    clean_status = (
        update.status
        .strip()
        .lower()
    )


    if (
        clean_status
        not in allowed_statuses
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid task status."
            )
        )


    conn = get_db()


    task = conn.execute(
        """
        SELECT *

        FROM retrieval_tasks

        WHERE task_id = ?
        """,
        (
            task_id,
        )
    ).fetchone()


    if task is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail=(
                "Task not found."
            )
        )


    conn.execute(
        """
        UPDATE retrieval_tasks

        SET
            status = ?,
            updated_at = ?

        WHERE
            task_id = ?
        """,
        (
            clean_status,

            datetime.now(
                timezone.utc
            ).isoformat(),

            task_id
        )
    )


    conn.commit()
    conn.close()


    return {
        "status":
            "updated",

        "task_id":
            task_id,

        "task_status":
            clean_status
    }


# ============================================================
# List recent retrieval tasks
# ============================================================

@app.get(
    "/tasks"
)
def list_tasks(
    limit: int = 20
):

    limit = max(
        1,
        min(
            limit,
            200
        )
    )


    conn = get_db()


    rows = conn.execute(
        """
        SELECT

            t.*,

            o.label

        FROM retrieval_tasks t

        JOIN object_observations o

        ON
            t.observation_id =
            o.observation_id

        ORDER BY
            t.id DESC

        LIMIT ?
        """,
        (
            limit,
        )
    ).fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]
