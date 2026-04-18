from flask import (Flask, render_template, jsonify, request,
                   session, redirect, url_for, send_from_directory)
from flask_cors import CORS
from werkzeug.utils import secure_filename
import mysql.connector
import bcrypt
import random
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "moodwave_secret_key_2026")
app.config["SESSION_COOKIE_SAMESITE"]    = "Lax"
app.config["SESSION_COOKIE_SECURE"]      = False
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7
app.config["MAX_CONTENT_LENGTH"]         = 300 * 1024 * 1024
CORS(app)

# ── Cloudinary config ──────────────────────────────────────────────────────────
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME",""),
    api_key    = os.getenv("CLOUDINARY_API_KEY",""),
    api_secret = os.getenv("CLOUDINARY_API_SECRET",""),
    secure     = True
)

USE_CLOUDINARY = bool(os.getenv("CLOUDINARY_CLOUD_NAME"))

# ── Local upload folders (fallback if no Cloudinary) ──────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_AUDIO = os.path.join(BASE_DIR,"static","uploads","audio")
UPLOAD_VIDEO = os.path.join(BASE_DIR,"static","uploads","video")
UPLOAD_PHOTO = os.path.join(BASE_DIR,"static","uploads","photos")
os.makedirs(UPLOAD_AUDIO, exist_ok=True)
os.makedirs(UPLOAD_VIDEO, exist_ok=True)
os.makedirs(UPLOAD_PHOTO, exist_ok=True)

ALLOWED_AUDIO = {"mp3","wav","ogg","flac","aac","m4a"}
ALLOWED_VIDEO = {"mp4","webm","mkv","avi","mov"}
ALLOWED_IMAGE = {"jpg","jpeg","png","webp","gif"}

def allowed_ext(fn, exts): return "." in fn and fn.rsplit(".",1)[1].lower() in exts

# ── DB ─────────────────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host     = os.getenv("MYSQLHOST",     os.getenv("DB_HOST",     "localhost")),
        port     = int(os.getenv("MYSQLPORT", os.getenv("DB_PORT",     "3306"))),
        user     = os.getenv("MYSQLUSER",     os.getenv("DB_USER",     "root")),
        password = os.getenv("MYSQLPASSWORD", os.getenv("DB_PASSWORD", "root123")),
        database = os.getenv("MYSQLDATABASE", os.getenv("DB_NAME",     "music_mood_db")),
    )

def analyze_mood(song, history):
    mood = song["mood"]
    if len(history) >= 2:
        freq = {}
        for h in history[:6]:
            freq[h["mood"]] = freq.get(h["mood"],0)+1
        dominant = sorted(freq.items(), key=lambda x:x[1], reverse=True)[0][0]
        if freq[dominant]/len(history[:6]) > 0.5:
            mood = dominant
    return mood, round(random.uniform(0.72,0.95),2)

# ── Cloudinary / local upload helper ──────────────────────────────────────────
def upload_file(file_obj, resource_type, folder):
    """Upload to Cloudinary if configured, else save locally."""
    if USE_CLOUDINARY:
        result = cloudinary.uploader.upload(
            file_obj,
            resource_type = resource_type,
            folder        = f"moodwave/{folder}",
            public_id     = f"{folder}_{random.randint(100000,999999)}",
            overwrite     = True
        )
        return result.get("secure_url",""), result.get("public_id","")
    else:
        safe  = secure_filename(file_obj.filename)
        base, ext = os.path.splitext(safe)
        unique = f"{base}_{random.randint(10000,99999)}{ext}"
        if folder == "audio":
            path = os.path.join(UPLOAD_AUDIO, unique)
            url  = "/uploads/audio/" + unique
        elif folder == "video":
            path = os.path.join(UPLOAD_VIDEO, unique)
            url  = "/uploads/video/" + unique
        else:
            path = os.path.join(UPLOAD_PHOTO, unique)
            url  = "/uploads/photos/" + unique
        file_obj.save(path)
        return url, unique

# ── Init DB ────────────────────────────────────────────────────────────────────
def init_db():
    try:
        db=get_db(); cur=db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150), email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) DEFAULT '', google_id VARCHAR(150) DEFAULT '',
            avatar VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS songs(
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL, artist VARCHAR(200) NOT NULL,
            mood VARCHAR(50) NOT NULL, genre VARCHAR(100) DEFAULT 'Unknown',
            tempo FLOAT DEFAULT 120, energy FLOAT DEFAULT 0.5,
            valence FLOAT DEFAULT 0.5, danceability FLOAT DEFAULT 0.5,
            audio_filename VARCHAR(300) DEFAULT '',
            video_filename VARCHAR(300) DEFAULT '',
            audio_url VARCHAR(500) DEFAULT '',
            video_url VARCHAR(500) DEFAULT '',
            cover_url VARCHAR(500) DEFAULT '',
            has_audio TINYINT(1) DEFAULT 0,
            has_video TINYINT(1) DEFAULT 0,
            file_size_mb FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reels(
            id INT AUTO_INCREMENT PRIMARY KEY,
            song_id INT, title VARCHAR(200) NOT NULL,
            artist VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            hashtags VARCHAR(500) DEFAULT '',
            video_url VARCHAR(500) DEFAULT '',
            cover_url VARCHAR(500) DEFAULT '',
            mood VARCHAR(50) DEFAULT 'happy',
            likes_count INT DEFAULT 0,
            views_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reel_likes(
            id INT AUTO_INCREMENT PRIMARY KEY,
            reel_id INT NOT NULL, session_id VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY ul(reel_id,session_id),
            FOREIGN KEY(reel_id) REFERENCES reels(id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reel_comments(
            id INT AUTO_INCREMENT PRIMARY KEY,
            reel_id INT NOT NULL, username VARCHAR(100) DEFAULT 'User',
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(reel_id) REFERENCES reels(id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS listening_history(
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(100) NOT NULL, song_id INT NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS song_stats(
            id INT AUTO_INCREMENT PRIMARY KEY,
            song_id INT NOT NULL, session_id VARCHAR(100),
            mood VARCHAR(50), played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE)""")
        db.commit(); db.close()
        print("✓ DB ready")
    except Exception as e:
        print("DB init error:", e)

# ── Serve local uploads ────────────────────────────────────────────────────────
@app.route("/uploads/audio/<path:f>")
def serve_audio(f): return send_from_directory(UPLOAD_AUDIO,f)
@app.route("/uploads/video/<path:f>")
def serve_video(f): return send_from_directory(UPLOAD_VIDEO,f)
@app.route("/uploads/photos/<path:f>")
def serve_photo(f): return send_from_directory(UPLOAD_PHOTO,f)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def root():          return render_template("home.html")
@app.route("/home")
def home():          return render_template("home.html")
@app.route("/login")
def login_page():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return render_template("login.html")
@app.route("/register")
def register_page():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return render_template("register.html")
@app.route("/auth")
def auth():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: return redirect(url_for("login_page"))
    return render_template("index.html")
@app.route("/stats")
def stats():
    if "user_id" not in session: return redirect(url_for("login_page"))
    return render_template("stats.html")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH API
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/register", methods=["POST"])
def register():
    try:
        d=request.get_json()
        fname=d.get("fname","").strip(); lname=d.get("lname","").strip()
        email=d.get("email","").strip().lower(); pw=d.get("password","")
        if not fname or not lname: return jsonify({"ok":False,"error":"Enter first and last name."}),400
        if not email or "@" not in email: return jsonify({"ok":False,"error":"Enter a valid email."}),400
        if len(pw)<6: return jsonify({"ok":False,"error":"Password min 6 characters."}),400
        hashed=bcrypt.hashpw(pw.encode(),bcrypt.gensalt())
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT id FROM users WHERE email=%s",(email,))
        if cur.fetchone(): db.close(); return jsonify({"ok":False,"error":"Email already registered."}),409
        name=fname+" "+lname
        cur.execute("INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",(name,email,hashed.decode()))
        db.commit(); uid=cur.lastrowid; db.close()
        session.permanent=True; session["user_id"]=uid; session["user_name"]=name; session["user_email"]=email
        return jsonify({"ok":True,"name":name,"redirect":"/dashboard"})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/login", methods=["POST"])
def login():
    try:
        d=request.get_json(); email=d.get("email","").strip().lower(); pw=d.get("password","")
        if not email: return jsonify({"ok":False,"error":"Enter your email."}),400
        if not pw: return jsonify({"ok":False,"error":"Enter your password."}),400
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        user=cur.fetchone(); db.close()
        if not user: return jsonify({"ok":False,"error":"No account with this email. Please register first."}),401
        if not user.get("password"): return jsonify({"ok":False,"error":"Use Google sign-in."}),401
        if not bcrypt.checkpw(pw.encode(),user["password"].encode()):
            return jsonify({"ok":False,"error":"Incorrect password."}),401
        session.permanent=True; session["user_id"]=user["id"]; session["user_name"]=user["name"]
        session["user_email"]=user["email"]; session["avatar"]=user.get("avatar","")
        return jsonify({"ok":True,"name":user["name"],"redirect":"/dashboard"})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/logout", methods=["POST"])
def logout(): session.clear(); return jsonify({"ok":True,"redirect":"/home"})

@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    email=request.get_json().get("email","").strip().lower()
    if not email or "@" not in email: return jsonify({"ok":False,"error":"Enter valid email."}),400
    return jsonify({"ok":True})

@app.route("/api/me")
def me():
    if "user_id" in session:
        return jsonify({"logged_in":True,"user_id":session["user_id"],
                        "name":session.get("user_name",""),"email":session.get("user_email",""),
                        "avatar":session.get("avatar","")})
    return jsonify({"logged_in":False})

# ══════════════════════════════════════════════════════════════════════════════
#  SONGS API
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/songs")
def get_songs():
    try:
        mood=request.args.get("mood"); db=get_db(); cur=db.cursor(dictionary=True)
        if mood and mood!="all": cur.execute("SELECT * FROM songs WHERE mood=%s ORDER BY id",(mood,))
        else: cur.execute("SELECT * FROM songs ORDER BY id")
        songs=cur.fetchall(); db.close()
        for s in songs:
            if s.get("has_audio") and s.get("audio_filename") and not s.get("audio_url"):
                s["audio_url"]="/uploads/audio/"+s["audio_filename"]
            if s.get("has_video") and s.get("video_filename") and not s.get("video_url"):
                s["video_url"]="/uploads/video/"+s["video_filename"]
        return jsonify(songs)
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/api/songs/<int:sid>")
def get_song(sid):
    try:
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(sid,))
        s=cur.fetchone(); db.close()
        if not s: return jsonify({"error":"Not found"}),404
        return jsonify(s)
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/api/songs/upload", methods=["POST"])
def upload_song():
    try:
        title=request.form.get("title","").strip()
        artist=request.form.get("artist","").strip()
        mood=request.form.get("mood","").strip()
        if not title or not artist or not mood:
            return jsonify({"ok":False,"error":"Title, artist and mood are required."}),400

        genre=request.form.get("genre","Unknown")
        tempo=float(request.form.get("tempo",120))
        energy=float(request.form.get("energy",0.5))
        valence=float(request.form.get("valence",0.5))
        danceability=float(request.form.get("danceability",0.5))
        manual_url=request.form.get("audio_url","").strip()

        audio_url=""; video_url=""; cover_url=""
        audio_fn=""; video_fn=""; has_audio=0; has_video=0; fsz=0.0

        # ── Cover photo ──
        pf=request.files.get("cover_photo")
        if pf and pf.filename:
            if not allowed_ext(pf.filename, ALLOWED_IMAGE):
                return jsonify({"ok":False,"error":"Invalid image format."}),400
            cover_url, _ = upload_file(pf, "image", "photos")

        # ── Audio ──
        af=request.files.get("audio_file")
        if af and af.filename:
            if not allowed_ext(af.filename, ALLOWED_AUDIO):
                return jsonify({"ok":False,"error":"Invalid audio format."}),400
            audio_url, audio_fn = upload_file(af, "video", "audio")
            has_audio=1
        elif manual_url:
            audio_url=manual_url; has_audio=1

        # ── Video ──
        vf=request.files.get("video_file")
        if vf and vf.filename:
            if not allowed_ext(vf.filename, ALLOWED_VIDEO):
                return jsonify({"ok":False,"error":"Invalid video format."}),400
            video_url, video_fn = upload_file(vf, "video", "video")
            has_video=1

        db=get_db(); cur=db.cursor()
        cur.execute("""INSERT INTO songs
            (title,artist,mood,genre,tempo,energy,valence,danceability,
             audio_filename,video_filename,audio_url,video_url,cover_url,
             has_audio,has_video,file_size_mb)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (title,artist,mood,genre,tempo,energy,valence,danceability,
             audio_fn,video_fn,audio_url,video_url,cover_url,has_audio,has_video,fsz))
        db.commit(); new_id=cur.lastrowid; db.close()
        return jsonify({"ok":True,"id":new_id,"has_audio":bool(has_audio),
                        "has_video":bool(has_video),"cover_url":cover_url})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/songs/<int:sid>", methods=["DELETE"])
def delete_song(sid):
    try:
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(sid,))
        s=cur.fetchone()
        if s:
            # Delete Cloudinary assets if public_id stored
            for fn_key, rtype in [("audio_filename","video"),("video_filename","video")]:
                fn=s.get(fn_key,"")
                if fn and (fn.startswith("moodwave/") or "moodwave" in fn):
                    try: cloudinary.uploader.destroy(fn, resource_type=rtype)
                    except: pass
                elif fn and not fn.startswith("moodwave/"):
                    # Local file
                    for folder in [UPLOAD_AUDIO, UPLOAD_VIDEO, UPLOAD_PHOTO]:
                        p=os.path.join(folder,fn)
                        if os.path.exists(p): os.remove(p)
            cur.execute("DELETE FROM listening_history WHERE song_id=%s",(sid,))
            cur.execute("DELETE FROM song_stats WHERE song_id=%s",(sid,))
            cur.execute("DELETE FROM songs WHERE id=%s",(sid,))
            db.commit()
        db.close(); return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

# ══════════════════════════════════════════════════════════════════════════════
#  REELS API
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/reels")
def get_reels():
    try:
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM reels ORDER BY created_at DESC")
        reels=cur.fetchall(); db.close()
        for r in reels:
            if r.get("created_at"): r["created_at"]=str(r["created_at"])
        return jsonify(reels)
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/api/reels/upload", methods=["POST"])
def upload_reel():
    try:
        title=request.form.get("title","").strip()
        artist=request.form.get("artist","").strip()
        description=request.form.get("description","").strip()
        hashtags=request.form.get("hashtags","").strip()
        mood=request.form.get("mood","happy").strip()
        song_id=request.form.get("song_id")

        if not title or not artist:
            return jsonify({"ok":False,"error":"Title and artist required."}),400

        video_url=""; cover_url=""

        vf=request.files.get("video_file")
        if vf and vf.filename:
            if not allowed_ext(vf.filename, ALLOWED_VIDEO):
                return jsonify({"ok":False,"error":"Invalid video format."}),400
            video_url, _ = upload_file(vf, "video", "video")

        pf=request.files.get("cover_photo")
        if pf and pf.filename:
            cover_url, _ = upload_file(pf, "image", "photos")

        db=get_db(); cur=db.cursor()
        cur.execute("""INSERT INTO reels
            (song_id,title,artist,description,hashtags,video_url,cover_url,mood)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (song_id if song_id else None,title,artist,description,hashtags,video_url,cover_url,mood))
        db.commit(); new_id=cur.lastrowid; db.close()
        return jsonify({"ok":True,"id":new_id,"video_url":video_url,"cover_url":cover_url})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/reels/<int:rid>/like", methods=["POST"])
def like_reel(rid):
    try:
        session_id=request.get_json().get("session_id","default")
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT id FROM reel_likes WHERE reel_id=%s AND session_id=%s",(rid,session_id))
        existing=cur.fetchone()
        if existing:
            cur.execute("DELETE FROM reel_likes WHERE reel_id=%s AND session_id=%s",(rid,session_id))
            cur.execute("UPDATE reels SET likes_count=GREATEST(0,likes_count-1) WHERE id=%s",(rid,))
            liked=False
        else:
            cur.execute("INSERT INTO reel_likes(reel_id,session_id) VALUES(%s,%s)",(rid,session_id))
            cur.execute("UPDATE reels SET likes_count=likes_count+1 WHERE id=%s",(rid,))
            liked=True
        db.commit()
        cur.execute("SELECT likes_count FROM reels WHERE id=%s",(rid,))
        count=cur.fetchone()["likes_count"]
        db.close()
        return jsonify({"ok":True,"liked":liked,"likes_count":count})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/reels/<int:rid>/comments", methods=["GET"])
def get_reel_comments(rid):
    try:
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM reel_comments WHERE reel_id=%s ORDER BY created_at DESC",(rid,))
        comments=cur.fetchall(); db.close()
        for c in comments:
            if c.get("created_at"): c["created_at"]=str(c["created_at"])
        return jsonify(comments)
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/api/reels/<int:rid>/comments", methods=["POST"])
def post_reel_comment(rid):
    try:
        d=request.get_json()
        username=d.get("username","User"); comment=d.get("comment","").strip()
        if not comment: return jsonify({"ok":False,"error":"Comment cannot be empty."}),400
        db=get_db(); cur=db.cursor()
        cur.execute("INSERT INTO reel_comments(reel_id,username,comment) VALUES(%s,%s,%s)",(rid,username,comment))
        cur.execute("UPDATE reels SET views_count=views_count+1 WHERE id=%s",(rid,))
        db.commit(); db.close()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/reels/<int:rid>", methods=["DELETE"])
def delete_reel(rid):
    try:
        db=get_db(); cur=db.cursor()
        cur.execute("DELETE FROM reel_comments WHERE reel_id=%s",(rid,))
        cur.execute("DELETE FROM reel_likes WHERE reel_id=%s",(rid,))
        cur.execute("DELETE FROM reels WHERE id=%s",(rid,))
        db.commit(); db.close()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

# ══════════════════════════════════════════════════════════════════════════════
#  MOOD ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/analyze", methods=["POST"])
def analyze_route():
    try:
        d=request.get_json(); song_id=d.get("song_id"); session_id=d.get("session_id","default")
        if not song_id: return jsonify({"error":"song_id required"}),400
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(song_id,))
        song=cur.fetchone()
        if not song: db.close(); return jsonify({"error":"Not found"}),404
        cur.execute("""SELECT s.* FROM listening_history lh JOIN songs s ON lh.song_id=s.id
            WHERE lh.session_id=%s ORDER BY lh.played_at DESC LIMIT 10""",(session_id,))
        history=cur.fetchall()
        cur.execute("INSERT INTO listening_history(session_id,song_id) VALUES(%s,%s)",(session_id,song_id))
        db.commit()
        final_mood,conf=analyze_mood(song,history)
        # Save to stats
        cur.execute("INSERT INTO song_stats(song_id,session_id,mood) VALUES(%s,%s,%s)",(song_id,session_id,final_mood))
        db.commit()
        cur.execute("SELECT * FROM songs WHERE mood=%s AND id!=%s ORDER BY energy DESC LIMIT 6",(final_mood,song_id))
        recs=cur.fetchall()
        if len(recs)<3:
            cur.execute("SELECT * FROM songs WHERE id!=%s ORDER BY RAND() LIMIT 6",(song_id,))
            recs=cur.fetchall()
        db.close()
        return jsonify({"mood":final_mood,"predicted_mood":song["mood"],"confidence":conf,
                        "song":song,"recommendations":recs,"history_count":len(history)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/api/history")
def get_history():
    try:
        sid=request.args.get("session_id","default")
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("""SELECT s.*,lh.played_at FROM listening_history lh
            JOIN songs s ON lh.song_id=s.id
            WHERE lh.session_id=%s ORDER BY lh.played_at DESC LIMIT 20""",(sid,))
        rows=cur.fetchall(); db.close()
        for r in rows:
            if r.get("played_at"): r["played_at"]=str(r["played_at"])
        return jsonify(rows)
    except Exception as e: return jsonify({"error":str(e)}),500

# ══════════════════════════════════════════════════════════════════════════════
#  STATISTICS API
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/stats/overview")
def stats_overview():
    try:
        db=get_db(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS total FROM songs")
        total_songs=cur.fetchone()["total"]
        cur.execute("SELECT mood,COUNT(*) AS c FROM songs GROUP BY mood ORDER BY c DESC")
        mood_dist=cur.fetchall()
        cur.execute("SELECT COUNT(*) AS total FROM reels")
        total_reels=cur.fetchone()["total"]
        cur.execute("SELECT COUNT(DISTINCT session_id) AS s FROM listening_history")
        sessions=cur.fetchone()["s"]
        cur.execute("SELECT COUNT(*) AS p FROM listening_history")
        total_plays=cur.fetchone()["p"]
        cur.execute("SELECT COUNT(*) AS u FROM users")
        total_users=cur.fetchone()["u"]
        cur.execute("SELECT COUNT(*) AS a FROM songs WHERE has_audio=1")
        with_audio=cur.fetchone()["a"]
        cur.execute("SELECT COUNT(*) AS v FROM songs WHERE has_video=1")
        with_video=cur.fetchone()["v"]
        # Top 5 played songs
        cur.execute("""SELECT s.title,s.artist,s.mood,s.cover_url,COUNT(*) AS plays
            FROM song_stats ss JOIN songs s ON ss.song_id=s.id
            GROUP BY ss.song_id ORDER BY plays DESC LIMIT 5""")
        top_songs=cur.fetchall()
        # Plays per day last 7 days
        cur.execute("""SELECT DATE(played_at) AS day, COUNT(*) AS plays
            FROM listening_history
            WHERE played_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(played_at) ORDER BY day ASC""")
        daily_plays=cur.fetchall()
        for r in daily_plays:
            if r.get("day"): r["day"]=str(r["day"])
        # Top reels
        cur.execute("SELECT title,artist,likes_count,views_count FROM reels ORDER BY likes_count DESC LIMIT 5")
        top_reels=cur.fetchall()
        db.close()
        return jsonify({
            "total_songs":total_songs,"mood_dist":mood_dist,
            "total_reels":total_reels,"sessions":sessions,
            "total_plays":total_plays,"total_users":total_users,
            "with_audio":with_audio,"with_video":with_video,
            "top_songs":top_songs,"daily_plays":daily_plays,
            "top_reels":top_reels
        })
    except Exception as e: return jsonify({"error":str(e)}),500

# ══════════════════════════════════════════════════════════════════════════════
init_db()
if __name__ == "__main__":
    port=int(os.getenv("PORT",5000))
    app.run(debug=False,host="0.0.0.0",port=port)