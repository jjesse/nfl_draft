const NFL_TEAMS = [
  "Arizona Cardinals",
  "Atlanta Falcons",
  "Baltimore Ravens",
  "Buffalo Bills",
  "Carolina Panthers",
  "Chicago Bears",
  "Cincinnati Bengals",
  "Cleveland Browns",
  "Dallas Cowboys",
  "Denver Broncos",
  "Detroit Lions",
  "Green Bay Packers",
  "Houston Texans",
  "Indianapolis Colts",
  "Jacksonville Jaguars",
  "Kansas City Chiefs",
  "Las Vegas Raiders",
  "Los Angeles Chargers",
  "Los Angeles Rams",
  "Miami Dolphins",
  "Minnesota Vikings",
  "New England Patriots",
  "New Orleans Saints",
  "New York Giants",
  "New York Jets",
  "Philadelphia Eagles",
  "Pittsburgh Steelers",
  "San Francisco 49ers",
  "Seattle Seahawks",
  "Tampa Bay Buccaneers",
  "Tennessee Titans",
  "Washington Commanders",
];

const YEAR = 2026;
const ROUNDS = 7;
const RANDOM_SEED = 2026;

// ---------------------------------------------------------------------------
// Browser-side fallback simulation (used only when draft_data.json is unavailable)
// ---------------------------------------------------------------------------

function mulberry32(seed) {
  let a = seed >>> 0;
  return function random() {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleWithSeed(items, seed) {
  const rng = mulberry32(seed);
  const shuffled = items.slice();
  for (let i = shuffled.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

function defaultProspects(totalPlayers) {
  return Array.from(
    { length: totalPlayers },
    (_, index) => `Prospect ${String(index + 1).padStart(3, "0")}`,
  );
}

function simulateDraftLocally() {
  const totalPicks = NFL_TEAMS.length * ROUNDS;
  const randomizedProspects = shuffleWithSeed(defaultProspects(totalPicks), RANDOM_SEED);
  const picks = [];

  let overallPick = 1;
  for (let roundNumber = 1; roundNumber <= ROUNDS; roundNumber += 1) {
    NFL_TEAMS.forEach((team, index) => {
      picks.push({
        overall_pick: overallPick,
        round_number: roundNumber,
        round_pick: index + 1,
        team,
        player: randomizedProspects[overallPick - 1],
      });
      overallPick += 1;
    });
  }

  return { picks, source: "browser-simulation (fallback)" };
}

// ---------------------------------------------------------------------------
// UI rendering
// ---------------------------------------------------------------------------

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderTable(container, headers, rows) {
  const thead = `<thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("")}</tbody>`;
  container.innerHTML = `<table>${thead}${tbody}</table>`;
}

function setSourceBanner(source, generatedAt) {
  const banner = document.getElementById("source-banner");
  if (!banner) return;
  let label;
  if (source === "nfl_data_py") {
    label = "Real picks (nfl_data_py)";
  } else if (source && source.includes("needs-based")) {
    label = `Need-based simulation (${source})`;
  } else {
    label = `Simulated draft (${source})`;
  }
  const dateStr = generatedAt ? ` · updated ${new Date(generatedAt).toLocaleString()}` : "";
  banner.textContent = `Data source: ${label}${dateStr}`;
  banner.classList.remove("hidden");
}

function initUI(picks, source, generatedAt) {
  setSourceBanner(source, generatedAt);

  const roundSelect = document.getElementById("round-select");
  const teamSelect = document.getElementById("team-select");
  const roundResults = document.getElementById("round-results");
  const teamResults = document.getElementById("team-results");

  const roundTab = document.getElementById("round-tab");
  const teamTab = document.getElementById("team-tab");
  const roundView = document.getElementById("round-view");
  const teamView = document.getElementById("team-view");

  for (let round = 1; round <= ROUNDS; round += 1) {
    roundSelect.insertAdjacentHTML("beforeend", `<option value="${round}">Round ${round}</option>`);
  }

  NFL_TEAMS.forEach((team) => {
    teamSelect.insertAdjacentHTML("beforeend", `<option value="${team}">${team}</option>`);
  });

  function playerCell(pick) {
    const name = escapeHtml(pick.player || "");
    const url = pick.bio_url || "";
    return url
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${name}</a>`
      : name;
  }

  function showRound(roundNumber) {
    const rows = picks
      .filter((pick) => pick.round_number === Number(roundNumber))
      .map((pick) => [
        pick.overall_pick,
        `Round ${pick.round_number} Pick ${pick.round_pick}`,
        pick.team,
        playerCell(pick),
        pick.position || "",
        pick.college || "",
      ]);
    renderTable(roundResults, ["Overall", "Slot", "Team", "Player", "Pos", "College"], rows);
  }

  function showTeam(team) {
    const rows = picks
      .filter((pick) => pick.team === team)
      .map((pick) => [
        pick.overall_pick,
        `Round ${pick.round_number} Pick ${pick.round_pick}`,
        playerCell(pick),
        pick.position || "",
        pick.college || "",
      ]);
    renderTable(teamResults, ["Overall", "Pick", "Player", "Pos", "College"], rows);
  }

  roundSelect.addEventListener("change", () => showRound(roundSelect.value));
  teamSelect.addEventListener("change", () => showTeam(teamSelect.value));

  roundTab.addEventListener("click", () => {
    roundTab.classList.add("active");
    teamTab.classList.remove("active");
    roundView.classList.remove("hidden");
    teamView.classList.add("hidden");
  });

  teamTab.addEventListener("click", () => {
    teamTab.classList.add("active");
    roundTab.classList.remove("active");
    teamView.classList.remove("hidden");
    roundView.classList.add("hidden");
  });

  showRound(1);
  showTeam(NFL_TEAMS[0]);
}

// ---------------------------------------------------------------------------
// Bootstrap: fetch JSON data, fall back to browser simulation on error
// ---------------------------------------------------------------------------

async function init() {
  let picks;
  let source;
  let generatedAt;

  try {
    const response = await fetch("./draft_data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    picks = data.picks;
    source = data.source;
    generatedAt = data.generated_at;
  } catch (err) {
    console.warn("Failed to load draft_data.json, falling back to browser simulation:", err);
    const fallback = simulateDraftLocally();
    picks = fallback.picks;
    source = fallback.source;
    generatedAt = null;
  }

  initUI(picks, source, generatedAt);
}

init();
