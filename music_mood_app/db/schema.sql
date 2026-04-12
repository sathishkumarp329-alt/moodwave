
CREATE DATABASE music_mood_db;
USE music_mood_db;

CREATE TABLE songs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200),
  artist VARCHAR(200),
  mood VARCHAR(50),
  tempo FLOAT,
  energy FLOAT,
  valence FLOAT,
  danceability FLOAT,
  genre VARCHAR(100),
  audio_url VARCHAR(500),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE listening_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(100),
  song_id INT,
  played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (song_id) REFERENCES songs(id)
);

-- Insert sample songs
INSERT INTO songs (title, artist, mood, tempo, energy, valence, danceability, genre) VALUES
('Happy', 'Pharrell Williams', 'happy', 160.0, 0.84, 0.96, 0.83, 'pop'),
('Someone Like You', 'Adele', 'sad', 67.5, 0.26, 0.08, 0.28, 'soul'),
('Eye of the Tiger', 'Survivor', 'energetic', 109.0, 0.93, 0.56, 0.63, 'rock'),
('Weightless', 'Marconi Union', 'calm', 60.0, 0.13, 0.14, 0.26, 'ambient'),
('Bohemian Rhapsody', 'Queen', 'energetic', 144.0, 0.71, 0.51, 0.40, 'rock'),
('Shape of You', 'Ed Sheeran', 'happy', 96.0, 0.65, 0.93, 0.82, 'pop'),
('Hurt', 'Johnny Cash', 'sad', 80.0, 0.19, 0.05, 0.25, 'country'),
('Blinding Lights', 'The Weeknd', 'energetic', 171.0, 0.73, 0.83, 0.51, 'pop'),
('Clair de Lune', 'Debussy', 'calm', 68.0, 0.09, 0.42, 0.19, 'classical'),
('Uptown Funk', 'Bruno Mars', 'happy', 115.0, 0.85, 0.90, 0.90, 'funk');