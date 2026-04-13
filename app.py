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
CORS(app)

# ── Upload folders ─────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
UPLOAD_AUDIO    = os.path.join(BASE_DIR, "static", "uploads", "audio")
UPLOAD_VIDEO    = os.path.join(BASE_DIR, "static", "uploads", "video")
ALLOWED_AUDIO   = {"mp3", "wav", "ogg", "flac", "aac", "m4a"}
ALLOWED_VIDEO   = {"mp4", "webm", "mkv", "avi", "mov"}
MAX_AUDIO_MB    = 50
MAX_VIDEO_MB    = 200

os.makedirs(UPLOAD_AUDIO, exist_ok=True)
os.makedirs(UPLOAD_VIDEO, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024   # 200 MB max request

# ── Helpers ────────────────────────────────────────────────────────────────────
def allowed_audio(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_AUDIO
def allowed_video(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_VIDEO

def get_db():
    return mysql.connector.connect(
        host     = os.getenv("MYSQLHOST",     "localhost"),
        port     = int(os.getenv("MYSQLPORT", "3306")),
        user     = os.getenv("MYSQLUSER",     "root"),
        password = os.getenv("MYSQLPASSWORD", "root123"),
        database = os.getenv("MYSQLDATABASE", "music_mood_db"),
    )

def analyze_mood(song, history):
    mood = song["mood"]
    if len(history) >= 2:
        freq = {}
        for h in history[:6]:
            freq[h["mood"]] = freq.get(h["mood"], 0) + 1
        dominant    = sorted(freq.items(), key=lambda x: x[1], reverse=True)[0][0]
        if freq[dominant] / len(history[:6]) > 0.5:
            mood = dominant
    return mood, round(random.uniform(0.72, 0.95), 2)

# ══════════════════════════════════════════════════════════════════════════════
#  SERVE UPLOADED FILES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/uploads/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(UPLOAD_AUDIO, filename)

@app.route("/uploads/video/<path:filename>")
def serve_video(filename):
    return send_from_directory(UPLOAD_VIDEO, filename)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def root():       return render_template("home.html")

@app.route("/home")
def home():       return render_template("home.html")

@app.route("/auth")
def auth():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return render_template("auth.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: return redirect(url_for("auth"))
    return render_template("index.html")

@app.route("/stats")
def stats():
    if "user_id" not in session: return redirect(url_for("auth"))
    return render_template("stats.html")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH API
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/register", methods=["POST"])
def register():
    try:
        d     = request.get_json()
        fname = d.get("fname","").strip()
        lname = d.get("lname","").strip()
        email = d.get("email","").strip().lower()
        pw    = d.get("password","")
        if not fname or not lname:
            return jsonify({"ok":False,"error":"Enter first and last name."}), 400
        if not email or "@" not in email:
            return jsonify({"ok":False,"error":"Enter a valid email."}), 400
        if len(pw) < 6:
            return jsonify({"ok":False,"error":"Password min 6 characters."}), 400
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT id FROM users WHERE email=%s",(email,))
        if cur.fetchone():
            db.close(); return jsonify({"ok":False,"error":"Email already registered."}), 409
        name = fname+" "+lname
        cur.execute("INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
                    (name,email,hashed.decode()))
        db.commit(); uid = cur.lastrowid; db.close()
        session["user_id"]=uid; session["user_name"]=name; session["user_email"]=email
        return jsonify({"ok":True,"name":name,"redirect":"/dashboard"})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    try:
        d     = request.get_json()
        email = d.get("email","").strip().lower()
        pw    = d.get("password","")
        if not email: return jsonify({"ok":False,"error":"Enter your email."}), 400
        if not pw:    return jsonify({"ok":False,"error":"Enter your password."}), 400
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        user = cur.fetchone(); db.close()
        if not user:
            return jsonify({"ok":False,"error":"No account with this email."}), 401
        if not user.get("password"):
            return jsonify({"ok":False,"error":"Use Google sign-in for this account."}), 401
        if not bcrypt.checkpw(pw.encode(), user["password"].encode()):
            return jsonify({"ok":False,"error":"Incorrect password."}), 401
        session["user_id"]=user["id"]; session["user_name"]=user["name"]
        session["user_email"]=user["email"]; session["avatar"]=user.get("avatar","")
        return jsonify({"ok":True,"name":user["name"],"redirect":"/dashboard"})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok":True,"redirect":"/home"})


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    email = request.get_json().get("email","").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok":False,"error":"Enter a valid email."}), 400
    return jsonify({"ok":True})


@app.route("/api/me")
def me():
    if "user_id" in session:
        return jsonify({"logged_in":True,"user_id":session["user_id"],
                        "name":session.get("user_name",""),
                        "email":session.get("user_email",""),
                        "avatar":session.get("avatar","")})
    return jsonify({"logged_in":False})

# ══════════════════════════════════════════════════════════════════════════════
#  SONGS API — GET / DELETE
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/songs", methods=["GET"])
def get_songs():
    try:
        mood = request.args.get("mood")
        db   = get_db(); cur = db.cursor(dictionary=True)
        if mood and mood != "all":
            cur.execute("SELECT * FROM songs WHERE mood=%s ORDER BY id",(mood,))
        else:
            cur.execute("SELECT * FROM songs ORDER BY id")
        songs = cur.fetchall(); db.close()
        # Build media URLs
        for s in songs:
            if s.get("has_audio") and s.get("audio_filename"):
                s["audio_url"] = "/uploads/audio/" + s["audio_filename"]
            if s.get("has_video") and s.get("video_filename"):
                s["video_url"] = "/uploads/video/" + s["video_filename"]
        return jsonify(songs)
    except Exception as e:
        return jsonify({"error":str(e)}), 500


@app.route("/api/songs/<int:sid>", methods=["GET"])
def get_song(sid):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(sid,))
        song = cur.fetchone(); db.close()
        if not song: return jsonify({"error":"Not found"}), 404
        if song.get("has_audio") and song.get("audio_filename"):
            song["audio_url"] = "/uploads/audio/" + song["audio_filename"]
        if song.get("has_video") and song.get("video_filename"):
            song["video_url"] = "/uploads/video/" + song["video_filename"]
        return jsonify(song)
    except Exception as e:
        return jsonify({"error":str(e)}), 500


@app.route("/api/songs/<int:sid>", methods=["DELETE"])
def delete_song(sid):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(sid,))
        song = cur.fetchone()
        if song:
            # Delete physical files
            if song.get("audio_filename"):
                af = os.path.join(UPLOAD_AUDIO, song["audio_filename"])
                if os.path.exists(af): os.remove(af)
            if song.get("video_filename"):
                vf = os.path.join(UPLOAD_VIDEO, song["video_filename"])
                if os.path.exists(vf): os.remove(vf)
            cur.execute("DELETE FROM listening_history WHERE song_id=%s",(sid,))
            cur.execute("DELETE FROM songs WHERE id=%s",(sid,))
            db.commit()
        db.close()
        return jsonify({"ok":True})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  ADD SONG  — multipart/form-data  (audio file + video file + metadata)
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/songs/upload", methods=["POST"])
def upload_song():
    try:
        # ── Text fields ──
        title        = request.form.get("title","").strip()
        artist       = request.form.get("artist","").strip()
        mood         = request.form.get("mood","").strip()
        genre        = request.form.get("genre","Unknown").strip()
        tempo        = float(request.form.get("tempo",120))
        energy       = float(request.form.get("energy",0.5))
        valence      = float(request.form.get("valence",0.5))
        danceability = float(request.form.get("danceability",0.5))
        manual_url   = request.form.get("audio_url","").strip()

        if not title or not artist or not mood:
            return jsonify({"ok":False,"error":"Title, artist and mood are required."}), 400

        audio_filename = ""
        video_filename = ""
        has_audio      = 0
        has_video      = 0
        file_size_mb   = 0.0

        # ── Audio file ──
        audio_file = request.files.get("audio_file")
        if audio_file and audio_file.filename:
            if not allowed_audio(audio_file.filename):
                return jsonify({"ok":False,"error":"Audio must be MP3, WAV, OGG, FLAC, AAC or M4A."}), 400
            safe      = secure_filename(audio_file.filename)
            # Unique name to avoid collision
            base, ext = os.path.splitext(safe)
            unique    = f"{base}_{random.randint(10000,99999)}{ext}"
            path      = os.path.join(UPLOAD_AUDIO, unique)
            audio_file.save(path)
            size_mb   = os.path.getsize(path) / 1024 / 1024
            if size_mb > MAX_AUDIO_MB:
                os.remove(path)
                return jsonify({"ok":False,"error":f"Audio file too large (max {MAX_AUDIO_MB} MB)."}), 400
            audio_filename = unique
            has_audio      = 1
            file_size_mb   = round(size_mb, 2)

        # ── Video file ──
        video_file = request.files.get("video_file")
        if video_file and video_file.filename:
            if not allowed_video(video_file.filename):
                return jsonify({"ok":False,"error":"Video must be MP4, WebM, MKV, AVI or MOV."}), 400
            safe      = secure_filename(video_file.filename)
            base, ext = os.path.splitext(safe)
            unique    = f"{base}_{random.randint(10000,99999)}{ext}"
            path      = os.path.join(UPLOAD_VIDEO, unique)
            video_file.save(path)
            size_mb   = os.path.getsize(path) / 1024 / 1024
            if size_mb > MAX_VIDEO_MB:
                os.remove(path)
                return jsonify({"ok":False,"error":f"Video file too large (max {MAX_VIDEO_MB} MB)."}), 400
            video_filename = unique
            has_video      = 1

        # ── Save to DB ──
        db  = get_db(); cur = db.cursor()
        cur.execute(
            """INSERT INTO songs
               (title,artist,mood,genre,tempo,energy,valence,danceability,
                audio_filename,video_filename,audio_url,has_audio,has_video,file_size_mb)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (title,artist,mood,genre,tempo,energy,valence,danceability,
             audio_filename,video_filename,manual_url,has_audio,has_video,file_size_mb)
        )
        db.commit(); new_id = cur.lastrowid; db.close()

        return jsonify({
            "ok":True, "id":new_id,
            "has_audio":bool(has_audio),
            "has_video":bool(has_video),
        })

    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  MOOD ANALYSIS + RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/analyze", methods=["POST"])
def analyze_route():
    try:
        data       = request.get_json()
        song_id    = data.get("song_id")
        session_id = data.get("session_id","default")
        if not song_id:
            return jsonify({"error":"song_id required"}), 400

        db  = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(song_id,))
        song = cur.fetchone()
        if not song: db.close(); return jsonify({"error":"Song not found"}), 404

        cur.execute(
            """SELECT s.* FROM listening_history lh
               JOIN songs s ON lh.song_id=s.id
               WHERE lh.session_id=%s ORDER BY lh.played_at DESC LIMIT 10""",
            (session_id,))
        history = cur.fetchall()

        cur.execute("INSERT INTO listening_history(session_id,song_id) VALUES(%s,%s)",
                    (session_id,song_id))
        db.commit()

        final_mood, conf = analyze_mood(song, history)

        cur.execute(
            "SELECT * FROM songs WHERE mood=%s AND id!=%s ORDER BY energy DESC LIMIT 6",
            (final_mood,song_id))
        recs = cur.fetchall()
        if len(recs) < 3:
            cur.execute("SELECT * FROM songs WHERE id!=%s ORDER BY RAND() LIMIT 6",(song_id,))
            recs = cur.fetchall()
        db.close()

        # Attach URLs
        def add_urls(s):
            if s.get("has_audio") and s.get("audio_filename"):
                s["audio_url"] = "/uploads/audio/"+s["audio_filename"]
            if s.get("has_video") and s.get("video_filename"):
                s["video_url"] = "/uploads/video/"+s["video_filename"]
            return s

        return jsonify({
            "mood":final_mood,"predicted_mood":song["mood"],
            "confidence":conf,"song":add_urls(song),
            "recommendations":[add_urls(r) for r in recs],
            "history_count":len(history)
        })
    except Exception as e:
        return jsonify({"error":str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY + STATS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/history")
def get_history():
    try:
        sid = request.args.get("session_id","default")
        db  = get_db(); cur = db.cursor(dictionary=True)
        cur.execute(
            """SELECT s.*,lh.played_at FROM listening_history lh
               JOIN songs s ON lh.song_id=s.id
               WHERE lh.session_id=%s ORDER BY lh.played_at DESC LIMIT 20""",(sid,))
        rows = cur.fetchall(); db.close()
        for r in rows:
            if r.get("played_at"): r["played_at"]=str(r["played_at"])
            if r.get("has_audio") and r.get("audio_filename"):
                r["audio_url"]="/uploads/audio/"+r["audio_filename"]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error":str(e)}), 500


@app.route("/api/admin/stats")
def admin_stats():
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS t FROM songs")
        total_songs = cur.fetchone()["t"]
        cur.execute("SELECT mood,COUNT(*) AS c FROM songs GROUP BY mood")
        mood_dist = cur.fetchall()
        cur.execute("SELECT COUNT(DISTINCT session_id) AS s FROM listening_history")
        sessions = cur.fetchone()["s"]
        cur.execute("SELECT COUNT(*) AS p FROM listening_history")
        plays = cur.fetchone()["p"]
        cur.execute("SELECT COUNT(*) AS u FROM users")
        users = cur.fetchone()["u"]
        cur.execute("SELECT COUNT(*) AS a FROM songs WHERE has_audio=1")
        with_audio = cur.fetchone()["a"]
        cur.execute("SELECT COUNT(*) AS v FROM songs WHERE has_video=1")
        with_video = cur.fetchone()["v"]
        db.close()
        return jsonify({"total_songs":total_songs,"mood_dist":mood_dist,
                        "sessions":sessions,"total_plays":plays,"total_users":users,
                        "with_audio":with_audio,"with_video":with_video})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, port=5000)