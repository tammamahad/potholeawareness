from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

DB_PATH = "potholes.db"
EXPIRATION_DAYS = 30


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            direction TEXT NOT NULL,
            lane TEXT NOT NULL,
            severity INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/reports")
def get_reports():
    # Only return reports newer than EXPIRATION_DAYS
    cutoff_iso = (
        (datetime.utcnow() - timedelta(days=EXPIRATION_DAYS))
        .replace(microsecond=0).isoformat() + "Z"
    )

    conn = get_db()
    rows = conn.execute("""
        SELECT id, lat, lng, direction, lane, severity, notes, created_at
        FROM reports
        WHERE created_at >= ?
        ORDER BY id DESC
    """, (cutoff_iso,)).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@app.post("/api/reports")
def create_report():
    data = request.get_json(silent=True)
    if not data:
        return {"error": "Missing JSON body"}, 400

    required = ["lat", "lng", "direction", "lane", "severity"]
    for key in required:
        if key not in data:
            return {"error": f"Missing field: {key}"}, 400

    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
        severity = int(data["severity"])
    except (ValueError, TypeError):
        return {"error": "lat/lng must be numbers and severity must be an integer"}, 400

    direction = str(data["direction"]).strip().lower()
    lane = str(data["lane"]).strip().lower()
    notes = (str(data.get("notes", "")).strip())[:200]

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return {"error": "Invalid lat/lng range"}, 400
    if not (1 <= severity <= 5):
        return {"error": "Severity must be between 1 and 5"}, 400

    allowed_directions = {"northbound", "southbound", "eastbound", "westbound"}
    allowed_lanes = {"left", "center", "right", "shoulder", "unknown"}
    if direction not in allowed_directions:
        return {"error": "Invalid direction"}, 400
    if lane not in allowed_lanes:
        return {"error": "Invalid lane"}, 400

    created_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (lat, lng, direction, lane, severity, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lat, lng, direction, lane, severity, notes, created_at))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return {
        "id": new_id,
        "lat": lat,
        "lng": lng,
        "direction": direction,
        "lane": lane,
        "severity": severity,
        "notes": notes,
        "created_at": created_at
    }, 201


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5050)
