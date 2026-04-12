const SESSION_ID = "user_" + Math.random().toString(36).substr(2, 9);

const MOOD_COLORS = {
  happy:    "bg-yellow-500",
  sad:      "bg-blue-700",
  energetic:"bg-red-600",
  calm:     "bg-teal-600"
};

async function loadSongs() {
  const res   = await fetch("/api/songs");
  const songs = await res.json();
  const grid  = document.getElementById("song-grid");
  grid.innerHTML = "";
  songs.forEach(song => {
    const card = document.createElement("div");
    card.className =
      "bg-gray-800 hover:bg-purple-900 rounded-xl p-4 cursor-pointer transition-all duration-200 border border-gray-700 hover:border-purple-500";
    card.innerHTML = `
      <div class="text-2xl mb-2">🎵</div>
      <p class="font-semibold text-white truncate">${song.title}</p>
      <p class="text-sm text-gray-400 truncate">${song.artist}</p>
      <span class="inline-block mt-2 text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">${song.genre}</span>
    `;
    card.addEventListener("click", () => analyzeSong(song.id));
    grid.appendChild(card);
  });
}

async function analyzeSong(songId) {
  // Show loading state
  const banner = document.getElementById("mood-banner");
  banner.className = "rounded-2xl p-6 mb-8 text-center bg-gray-800 animate-pulse";
  document.getElementById("mood-label").textContent = "Analyzing...";
  banner.classList.remove("hidden");
  document.getElementById("recs-section").classList.add("hidden");

  const res    = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body:   JSON.stringify({ song_id: songId, session_id: SESSION_ID })
  });
  const data   = await res.json();

  // Update mood banner
  const mood      = data.mood || "unknown";
  const colorCls  = MOOD_COLORS[mood] || "bg-gray-700";
  banner.className = `rounded-2xl p-6 mb-8 text-center ${colorCls} transition-all duration-500`;
  banner.classList.remove("animate-pulse");
  document.getElementById("mood-label").textContent = mood;
  document.getElementById("confidence-label").textContent =
    `Confidence: ${(data.confidence * 100).toFixed(0)}%  ·  History mood blended`;

  // Render recommendations
  const recs     = data.recommendations || [];
  const recsGrid = document.getElementById("recs-grid");
  recsGrid.innerHTML = "";
  recs.forEach(song => {
    const card = document.createElement("div");
    card.className =
      "bg-gray-800 hover:bg-purple-900 rounded-xl p-4 cursor-pointer transition-all border border-gray-700 hover:border-purple-500";
    card.innerHTML = `
      <div class="text-2xl mb-2">🎶</div>
      <p class="font-semibold text-white truncate">${song.title}</p>
      <p class="text-sm text-gray-400 truncate">${song.artist}</p>
      <span class="inline-block mt-2 text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">${song.mood}</span>
    `;
    card.addEventListener("click", () => analyzeSong(song.id));
    recsGrid.appendChild(card);
  });

  document.getElementById("recs-section").classList.remove("hidden");
}

loadSongs();