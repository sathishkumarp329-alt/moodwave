from flask import (Flask, render_template, jsonify, request,
                   session, redirect, url_for, send_from_directory)
from flask_cors import CORS
from werkzeug.utils import secure_filename
import mysql.connector
import bcrypt
import random
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "moodwave_secret_key_2026")
app.config["SESSION_COOKIE_SAMESITE"]       = "Lax"
app.config["SESSION_COOKIE_SECURE"]         = False
app.config["PERMANENT_SESSION_LIFETIME"]    = 86400 * 7
app.config["MAX_CONTENT_LENGTH"]            = 200 * 1024 * 1024
CORS(app)

# ── Upload folders ─────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_AUDIO = os.path.join(BASE_DIR, "static", "uploads", "audio")
UPLOAD_VIDEO = os.path.join(BASE_DIR, "static", "uploads", "video")
ALLOWED_AUDIO = {"mp3","wav","ogg","flac","aac","m4a"}
ALLOWED_VIDEO = {"mp4","webm","mkv","avi","mov"}
os.makedirs(UPLOAD_AUDIO, exist_ok=True)
os.makedirs(UPLOAD_VIDEO, exist_ok=True)

def allowed_audio(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_AUDIO
def allowed_video(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_VIDEO

# ── Database ───────────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host     = os.getenv("MYSQLHOST",     os.getenv("DB_HOST",     "localhost")),
        port     = int(os.getenv("MYSQLPORT", os.getenv("DB_PORT",     "3306"))),
        user     = os.getenv("MYSQLUSER",     os.getenv("DB_USER",     "root")),
        password = os.getenv("MYSQLPASSWORD", os.getenv("DB_PASSWORD", "root123")),
        database = os.getenv("MYSQLDATABASE", os.getenv("DB_NAME",     "music_mood_db")),
    )

# ── Mood analysis ──────────────────────────────────────────────────────────────
def analyze_mood(song, history):
    mood = song["mood"]
    if len(history) >= 2:
        freq = {}
        for h in history[:6]:
            freq[h["mood"]] = freq.get(h["mood"], 0) + 1
        dominant = sorted(freq.items(), key=lambda x: x[1], reverse=True)[0][0]
        if freq[dominant] / len(history[:6]) > 0.5:
            mood = dominant
    return mood, round(random.uniform(0.72, 0.95), 2)

# ── Init DB tables ─────────────────────────────────────────────────────────────
def init_db():
    try:
        db  = get_db()
        cur = db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150),
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) DEFAULT '',
            google_id VARCHAR(150) DEFAULT '',
            avatar VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS songs(
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            artist VARCHAR(200) NOT NULL,
            mood VARCHAR(50) NOT NULL,
            genre VARCHAR(100) DEFAULT 'Unknown',
            tempo FLOAT DEFAULT 120,
            energy FLOAT DEFAULT 0.5,
            valence FLOAT DEFAULT 0.5,
            danceability FLOAT DEFAULT 0.5,
            audio_filename VARCHAR(300) DEFAULT '',
            video_filename VARCHAR(300) DEFAULT '',
            audio_url VARCHAR(500) DEFAULT '',
            has_audio TINYINT(1) DEFAULT 0,
            has_video TINYINT(1) DEFAULT 0,
            file_size_mb FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS listening_history(
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(100) NOT NULL,
            song_id INT NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE)""")
        db.commit()
        db.close()
        print("✓ Database ready")
    except Exception as e:
        print("DB init error:", e)

# ── Serve uploaded files ───────────────────────────────────────────────────────
@app.route("/uploads/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(UPLOAD_AUDIO, filename)

@app.route("/uploads/video/<path:filename>")
def serve_video(filename):
    return send_from_directory(UPLOAD_VIDEO, filename)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES  (each route defined ONLY ONCE)
#  Flow: / → home → /register → /dashboard
#                 → /login    → /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def root():
    return render_template("home.html")

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/auth")
def auth():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html")

@app.route("/stats")
def stats():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("stats.html")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/register", methods=["POST"])
def register():
    try:
        d     = request.get_json()
        fname = d.get("fname", "").strip()
        lname = d.get("lname", "").strip()
        email = d.get("email", "").strip().lower()
        pw    = d.get("password", "")

        if not fname or not lname:
            return jsonify({"ok": False, "error": "Please enter your first and last name."}), 400
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400
        if len(pw) < 6:
            return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

        hashed = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt())
        db  = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            db.close()
            return jsonify({
                "ok":    False,
                "error": "An account with this email already exists. Please sign in instead."
            }), 409

        name = fname + " " + lname
        cur.execute(
            "INSERT INTO users(name, email, password) VALUES(%s, %s, %s)",
            (name, email, hashed.decode("utf-8"))
        )
        db.commit()
        uid = cur.lastrowid
        db.close()

        session.permanent     = True
        session["user_id"]    = uid
        session["user_name"]  = name
        session["user_email"] = email

        return jsonify({"ok": True, "name": name, "redirect": "/dashboard"})

    except Exception as e:
        return jsonify({"ok": False, "error": "Registration failed: " + str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    try:
        d     = request.get_json()
        email = d.get("email", "").strip().lower()
        pw    = d.get("password", "")

        if not email:
            return jsonify({"ok": False, "error": "Please enter your email address."}), 400
        if not pw:
            return jsonify({"ok": False, "error": "Please enter your password."}), 400

        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        db.close()

        if not user:
            return jsonify({
                "ok":    False,
                "error": "No account found with this email. Please create an account first."
            }), 401

        if not user.get("password"):
            return jsonify({
                "ok":    False,
                "error": "This account uses Google sign-in. Please use Continue with Google."
            }), 401

        if not bcrypt.checkpw(pw.encode("utf-8"), user["password"].encode("utf-8")):
            return jsonify({
                "ok":    False,
                "error": "Incorrect password. Please try again or use Forgot Password."
            }), 401

        session.permanent     = True
        session["user_id"]    = user["id"]
        session["user_name"]  = user["name"]
        session["user_email"] = user["email"]
        session["avatar"]     = user.get("avatar", "")

        return jsonify({"ok": True, "name": user["name"], "redirect": "/dashboard"})

    except Exception as e:
        return jsonify({"ok": False, "error": "Login failed: " + str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/home"})


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    try:
        email = request.get_json().get("email", "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Please enter a valid email."}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/me")
def me():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "user_id":   session["user_id"],
            "name":      session.get("user_name", ""),
            "email":     session.get("user_email", ""),
            "avatar":    session.get("avatar", ""),
        })
    return jsonify({"logged_in": False})

# ══════════════════════════════════════════════════════════════════════════════
#  SONGS API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/songs", methods=["GET"])
def get_songs():
    try:
        mood = request.args.get("mood")
        db   = get_db()
        cur  = db.cursor(dictionary=True)
        if mood and mood != "all":
            cur.execute("SELECT * FROM songs WHERE mood = %s ORDER BY id", (mood,))
        else:
            cur.execute("SELECT * FROM songs ORDER BY id")
        songs = cur.fetchall()
        db.close()
        for s in songs:
            if s.get("has_audio") and s.get("audio_filename"):
                s["audio_url"] = "/uploads/audio/" + s["audio_filename"]
            if s.get("has_video") and s.get("video_filename"):
                s["video_url"] = "/uploads/video/" + s["video_filename"]
        return jsonify(songs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/songs/<int:sid>", methods=["GET"])
def get_song(sid):
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id = %s", (sid,))
        s = cur.fetchone()
        db.close()
        if not s:
            return jsonify({"error": "Not found"}), 404
        if s.get("has_audio") and s.get("audio_filename"):
            s["audio_url"] = "/uploads/audio/" + s["audio_filename"]
        if s.get("has_video") and s.get("video_filename"):
            s["video_url"] = "/uploads/video/" + s["video_filename"]
        return jsonify(s)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/songs/upload", methods=["POST"])
def upload_song():
    try:
        title        = request.form.get("title", "").strip()
        artist       = request.form.get("artist", "").strip()
        mood         = request.form.get("mood", "").strip()
        genre        = request.form.get("genre", "Unknown").strip()
        tempo        = float(request.form.get("tempo", 120))
        energy       = float(request.form.get("energy", 0.5))
        valence      = float(request.form.get("valence", 0.5))
        danceability = float(request.form.get("danceability", 0.5))
        manual_url   = request.form.get("audio_url", "").strip()

        if not title or not artist or not mood:
            return jsonify({"ok": False, "error": "Title, artist and mood are required."}), 400

        audio_filename = ""
        video_filename = ""
        has_audio      = 0
        has_video      = 0
        fsz            = 0.0

        af = request.files.get("audio_file")
        if af and af.filename:
            if not allowed_audio(af.filename):
                return jsonify({"ok": False, "error": "Invalid audio format."}), 400
            safe   = secure_filename(af.filename)
            base, ext = os.path.splitext(safe)
            unique = f"{base}_{random.randint(10000,99999)}{ext}"
            path   = os.path.join(UPLOAD_AUDIO, unique)
            af.save(path)
            sz = os.path.getsize(path) / 1024 / 1024
            if sz > 50:
                os.remove(path)
                return jsonify({"ok": False, "error": "Audio too large (max 50MB)."}), 400
            audio_filename = unique
            has_audio      = 1
            fsz            = round(sz, 2)

        vf = request.files.get("video_file")
        if vf and vf.filename:
            if not allowed_video(vf.filename):
                return jsonify({"ok": False, "error": "Invalid video format."}), 400
            safe   = secure_filename(vf.filename)
            base, ext = os.path.splitext(safe)
            unique = f"{base}_{random.randint(10000,99999)}{ext}"
            path   = os.path.join(UPLOAD_VIDEO, unique)
            vf.save(path)
            sz = os.path.getsize(path) / 1024 / 1024
            if sz > 200:
                os.remove(path)
                return jsonify({"ok": False, "error": "Video too large (max 200MB)."}), 400
            video_filename = unique
            has_video      = 1

        db  = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO songs
               (title,artist,mood,genre,tempo,energy,valence,danceability,
                audio_filename,video_filename,audio_url,has_audio,has_video,file_size_mb)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (title, artist, mood, genre, tempo, energy, valence, danceability,
             audio_filename, video_filename, manual_url, has_audio, has_video, fsz)
        )
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return jsonify({"ok": True, "id": new_id,
                        "has_audio": bool(has_audio),
                        "has_video": bool(has_video)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/songs/<int:sid>", methods=["DELETE"])
def delete_song(sid):
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id = %s", (sid,))
        s = cur.fetchone()
        if s:
            for fname, folder in [
                (s.get("audio_filename"), UPLOAD_AUDIO),
                (s.get("video_filename"), UPLOAD_VIDEO)
            ]:
                if fname:
                    p = os.path.join(folder, fname)
                    if os.path.exists(p):
                        os.remove(p)
            cur.execute("DELETE FROM listening_history WHERE song_id = %s", (sid,))
            cur.execute("DELETE FROM songs WHERE id = %s", (sid,))
            db.commit()
        db.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  MOOD ANALYSIS + RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/analyze", methods=["POST"])
def analyze_route():
    try:
        d          = request.get_json()
        song_id    = d.get("song_id")
        session_id = d.get("session_id", "default")

        if not song_id:
            return jsonify({"error": "song_id required"}), 400

        db  = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT * FROM songs WHERE id = %s", (song_id,))
        song = cur.fetchone()
        if not song:
            db.close()
            return jsonify({"error": "Song not found"}), 404

        cur.execute(
            """SELECT s.* FROM listening_history lh
               JOIN songs s ON lh.song_id = s.id
               WHERE lh.session_id = %s
               ORDER BY lh.played_at DESC LIMIT 10""",
            (session_id,)
        )
        history = cur.fetchall()

        cur.execute(
            "INSERT INTO listening_history(session_id, song_id) VALUES(%s, %s)",
            (session_id, song_id)
        )
        db.commit()

        final_mood, conf = analyze_mood(song, history)

        cur.execute(
            "SELECT * FROM songs WHERE mood = %s AND id != %s ORDER BY energy DESC LIMIT 6",
            (final_mood, song_id)
        )
        recs = cur.fetchall()
        if len(recs) < 3:
            cur.execute(
                "SELECT * FROM songs WHERE id != %s ORDER BY RAND() LIMIT 6",
                (song_id,)
            )
            recs = cur.fetchall()
        db.close()

        def add_urls(s):
            if s.get("has_audio") and s.get("audio_filename"):
                s["audio_url"] = "/uploads/audio/" + s["audio_filename"]
            if s.get("has_video") and s.get("video_filename"):
                s["video_url"] = "/uploads/video/" + s["video_filename"]
            return s

        return jsonify({
            "mood":            final_mood,
            "predicted_mood":  song["mood"],
            "confidence":      conf,
            "song":            add_urls(song),
            "recommendations": [add_urls(r) for r in recs],
            "history_count":   len(history)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def get_history():
    try:
        sid = request.args.get("session_id", "default")
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            """SELECT s.*, lh.played_at FROM listening_history lh
               JOIN songs s ON lh.song_id = s.id
               WHERE lh.session_id = %s
               ORDER BY lh.played_at DESC LIMIT 20""",
            (sid,)
        )
        rows = cur.fetchall()
        db.close()
        for r in rows:
            if r.get("played_at"):
                r["played_at"] = str(r["played_at"])
            if r.get("has_audio") and r.get("audio_filename"):
                r["audio_url"] = "/uploads/audio/" + r["audio_filename"]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/stats")
def admin_stats():
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS t FROM songs")
        total = cur.fetchone()["t"]
        cur.execute("SELECT mood, COUNT(*) AS c FROM songs GROUP BY mood")
        mood_dist = cur.fetchall()
        cur.execute("SELECT COUNT(DISTINCT session_id) AS s FROM listening_history")
        sessions = cur.fetchone()["s"]
        cur.execute("SELECT COUNT(*) AS p FROM listening_history")
        plays = cur.fetchone()["p"]
        cur.execute("SELECT COUNT(*) AS u FROM users")
        users = cur.fetchone()["u"]
        db.close()
        return jsonify({
            "total_songs": total,
            "mood_dist":   mood_dist,
            "sessions":    sessions,
            "total_plays": plays,
            "total_users": users
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)