CREATE DATABASE IF NOT EXISTS music_mood_db;
USE music_mood_db;

CREATE TABLE IF NOT EXISTS users (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(150),
  email      VARCHAR(150) UNIQUE NOT NULL,
  password   VARCHAR(255) DEFAULT '',
  google_id  VARCHAR(150) DEFAULT '',
  avatar     VARCHAR(500) DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS songs (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  title          VARCHAR(200)  NOT NULL,
  artist         VARCHAR(200)  NOT NULL,
  mood           VARCHAR(50)   NOT NULL,
  genre          VARCHAR(100)  DEFAULT 'Unknown',
  tempo          FLOAT         DEFAULT 120,
  energy         FLOAT         DEFAULT 0.5,
  valence        FLOAT         DEFAULT 0.5,
  danceability   FLOAT         DEFAULT 0.5,
  audio_filename VARCHAR(300)  DEFAULT '',
  video_filename VARCHAR(300)  DEFAULT '',
  audio_url      VARCHAR(500)  DEFAULT '',
  video_url      VARCHAR(500)  DEFAULT '',
  has_audio      TINYINT(1)    DEFAULT 0,
  has_video      TINYINT(1)    DEFAULT 0,
  file_size_mb   FLOAT         DEFAULT 0,
  duration_sec   INT           DEFAULT 0,
  created_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listening_history (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(100) NOT NULL,
  song_id    INT          NOT NULL,
  played_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
);

INSERT IGNORE INTO songs
  (id,title,artist,mood,genre,tempo,energy,valence,danceability,has_audio,has_video)
VALUES
  (1,'Happy','Pharrell Williams','happy','Pop',160,0.84,0.96,0.83,0,0),
  (2,'Someone Like You','Adele','sad','Soul',67,0.26,0.08,0.28,0,0),
  (3,'Eye of the Tiger','Survivor','energetic','Rock',109,0.93,0.56,0.63,0,0),
  (4,'Weightless','Marconi Union','calm','Ambient',60,0.13,0.14,0.26,0,0),
  (5,'Bohemian Rhapsody','Queen','energetic','Rock',144,0.71,0.51,0.40,0,0),
  (6,'Shape of You','Ed Sheeran','happy','Pop',96,0.65,0.93,0.82,0,0),
  (7,'Hurt','Johnny Cash','sad','Country',80,0.19,0.05,0.25,0,0),
  (8,'Blinding Lights','The Weeknd','energetic','Pop',171,0.73,0.83,0.51,0,0),
  (9,'Clair de Lune','Debussy','calm','Classical',68,0.09,0.42,0.19,0,0),
  (10,'Uptown Funk','Bruno Mars','happy','Funk',115,0.85,0.90,0.90,0,0),
  (11,'Perfect','Ed Sheeran','romantic','Pop',95,0.45,0.75,0.56,0,0),
  (12,'A Thousand Years','Christina Perri','romantic','Pop',89,0.37,0.62,0.41,0,0);