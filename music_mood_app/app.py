from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import mysql.connector
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
import json
import os

app = Flask(__name__)
CORS(app)

# ── Load R script once at startup ────────────────────────────────────────────
pandas2ri.activate()
ro.r.source("r_scripts/mood_analysis.R")
run_analysis = ro.globalenv["run_analysis"]

# ── DB connection ─────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",       # ← update to your password
        database="music_mood_db"
    )

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/songs")
def get_songs():
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM songs ORDER BY id")
    songs = cur.fetchall()
    db.close()
    return jsonify(songs)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data       = request.get_json()
    song_id    = data.get("song_id")
    session_id = data.get("session_id", "default")

    db  = get_db()
    cur = db.cursor(dictionary=True)

    # Get clicked song
    cur.execute("SELECT * FROM songs WHERE id = %s", (song_id,))
    song = cur.fetchone()

    # Get listening history for this session
    cur.execute("""
        SELECT s.* FROM listening_history lh
        JOIN songs s ON lh.song_id = s.id
        WHERE lh.session_id = %s
        ORDER BY lh.played_at DESC LIMIT 10
    """, (session_id,))
    history = cur.fetchall()

    # Get all songs for training pool
    cur.execute("SELECT * FROM songs")
    all_songs = cur.fetchall()

    # Save to history
    cur.execute(
        "INSERT INTO listening_history (session_id, song_id) VALUES (%s, %s)",
        (session_id, song_id)
    )
    db.commit()
    db.close()

    # Call R analysis
    result_json = run_analysis(
        json.dumps(song),
        json.dumps(history if history else []),
        json.dumps(all_songs)
    )
    result = json.loads(str(result_json[0]))
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)