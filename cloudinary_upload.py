# ── ADD THESE IMPORTS at the top of app.py after existing imports ──────────────
import cloudinary
import cloudinary.uploader

# ── ADD THIS CONFIG after app = Flask(__name__) ───────────────────────────────
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure     = True
)

# ── REPLACE your entire /api/songs/upload route with this ─────────────────────
@app.route("/api/songs/upload", methods=["POST"])
def upload_song():
    try:
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
            return jsonify({"ok":False,"error":"Title, artist and mood are required."}),400

        audio_url_final = manual_url
        video_url_final = ""
        has_audio       = 1 if manual_url else 0
        has_video       = 0
        audio_public_id = ""
        video_public_id = ""

        # ── Upload audio to Cloudinary ──
        af = request.files.get("audio_file")
        if af and af.filename:
            if not allowed_audio(af.filename):
                return jsonify({"ok":False,"error":"Invalid audio format. Use MP3, WAV, OGG, FLAC, AAC or M4A."}),400
            result = cloudinary.uploader.upload(
                af,
                resource_type = "video",   # Cloudinary uses "video" for audio too
                folder        = "moodwave/audio",
                public_id     = f"audio_{random.randint(100000,999999)}",
                overwrite     = True
            )
            audio_url_final = result.get("secure_url","")
            audio_public_id = result.get("public_id","")
            has_audio       = 1

        # ── Upload video to Cloudinary ──
        vf = request.files.get("video_file")
        if vf and vf.filename:
            if not allowed_video(vf.filename):
                return jsonify({"ok":False,"error":"Invalid video format. Use MP4, WebM, MKV, AVI or MOV."}),400
            result = cloudinary.uploader.upload(
                vf,
                resource_type = "video",
                folder        = "moodwave/video",
                public_id     = f"video_{random.randint(100000,999999)}",
                overwrite     = True
            )
            video_url_final = result.get("secure_url","")
            video_public_id = result.get("public_id","")
            has_video       = 1

        # ── Save to MySQL ──
        db  = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO songs
               (title,artist,mood,genre,tempo,energy,valence,danceability,
                audio_filename,video_filename,audio_url,video_url,
                has_audio,has_video)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (title,artist,mood,genre,tempo,energy,valence,danceability,
             audio_public_id, video_public_id,
             audio_url_final, video_url_final,
             has_audio, has_video)
        )
        db.commit()
        new_id = cur.lastrowid
        db.close()

        return jsonify({
            "ok":        True,
            "id":        new_id,
            "has_audio": bool(has_audio),
            "has_video": bool(has_video),
            "audio_url": audio_url_final,
            "video_url": video_url_final,
        })

    except Exception as e:
        return jsonify({"ok":False,"error":"Upload failed: "+str(e)}),500


# ── REPLACE delete_song route with this (also deletes from Cloudinary) ─────────
@app.route("/api/songs/<int:sid>", methods=["DELETE"])
def delete_song(sid):
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM songs WHERE id=%s",(sid,))
        s = cur.fetchone()
        if s:
            # Delete from Cloudinary if public_id stored
            if s.get("audio_filename") and s["audio_filename"].startswith("moodwave/"):
                try: cloudinary.uploader.destroy(s["audio_filename"], resource_type="video")
                except: pass
            if s.get("video_filename") and s["video_filename"].startswith("moodwave/"):
                try: cloudinary.uploader.destroy(s["video_filename"], resource_type="video")
                except: pass
            cur.execute("DELETE FROM listening_history WHERE song_id=%s",(sid,))
            cur.execute("DELETE FROM songs WHERE id=%s",(sid,))
            db.commit()
        db.close()
        return jsonify({"ok":True})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),500