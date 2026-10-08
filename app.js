let latest = null;
let rubricChart = null;

const $ = id => document.getElementById(id);
const fileInput = $("audioFile");
const fileName = $("fileName");
const dropzone = $("dropzone");

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "Drop audio here or click to browse";
});

["dragenter","dragover"].forEach(e => dropzone.addEventListener(e, ev => {
  ev.preventDefault();
  dropzone.style.borderColor = "#6ee7f5";
}));
["dragleave","drop"].forEach(e => dropzone.addEventListener(e, ev => {
  ev.preventDefault();
  dropzone.style.borderColor = "";
}));
dropzone.addEventListener("drop", ev => {
  if (ev.dataTransfer.files.length) {
    fileInput.files = ev.dataTransfer.files;
    fileName.textContent = fileInput.files[0].name;
  }
});

$("demoBtn").addEventListener("click", async () => {
  setMessage("Loading demo analysis...");
  const res = await fetch("/api/demo");
  const data = await res.json();
  render(data);
  setMessage("Demo loaded. Upload your own speech when ready.");
});

$("analyzeBtn").addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return setMessage("Please choose an audio file first.");

  const fd = new FormData();
  fd.append("audio", file);
  fd.append("transcript", $("transcript").value);

  $("progress").classList.remove("hidden");
  setMessage("Analyzing audio. Please wait...");
  $("analyzeBtn").disabled = true;

  try {
    const res = await fetch("/api/analyze", {method:"POST", body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Analysis failed");
    render(data);
    setMessage(data.warning || "Analysis complete.");
  } catch (err) {
    setMessage(err.message);
  } finally {
    $("progress").classList.add("hidden");
    $("analyzeBtn").disabled = false;
  }
});

function fmtTime(seconds) {
  seconds = Number(seconds || 0);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2,"0");
  return `${m}:${s}`;
}

function scoreText(score) {
  if (score >= 90) return ["Excellent delivery", "Your speech is highly polished. Focus on consistency."];
  if (score >= 80) return ["Strong delivery", "A few targeted improvements can make this presentation sharper."];
  if (score >= 70) return ["Good foundation", "You have a solid base. Work on the highlighted issues."];
  if (score >= 60) return ["Needs practice", "Focus on one or two high-impact areas per rehearsal."];
  return ["Needs attention", "Use the timeline and recommendations to structure your next practice."];
}

function render(data) {
  latest = data;
  $("results").classList.remove("hidden");
  $("modeBadge").textContent = data.mode === "demo" ? "DEMO ANALYSIS" : "LIVE ANALYSIS";

  const score = data.score.overall;
  $("overall").textContent = score;
  $("attemptScore").textContent = score;
  $("duration").textContent = `${data.audio.duration}s`;
  $("wpm").textContent = data.score.wpm ? `${data.score.wpm}` : "—";
  $("fillers").textContent = data.score.filler_total;
  const [label, desc] = scoreText(score);
  $("scoreLabel").textContent = label;
  $("scoreDescription").textContent = desc;

  const ring = $("scoreRing");
  ring.style.background = `conic-gradient(#6ee7f5 ${score}%, #1a2b43 0)`;

  const rec = $("recommendations");
  rec.innerHTML = "";
  data.recommendations.forEach((x, i) => {
    rec.innerHTML += `<div class="rec"><b>${i+1}</b>${escapeHtml(x)}</div>`;
  });

  renderChart(data.score.rubric);
  renderTimeline(data.flaws || []);
  $("transcriptView").textContent = data.transcript?.text || "No transcript available. Paste a transcript or enable Faster-Whisper.";
  $("language").textContent = data.transcript?.language || "—";

  document.querySelector("#results").scrollIntoView({behavior:"smooth", block:"start"});
}

function renderChart(rubric) {
  const ctx = $("rubricChart").getContext("2d");
  if (rubricChart) rubricChart.destroy();
  rubricChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: Object.keys(rubric),
      datasets: [{data: Object.values(rubric), borderRadius: 8}]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {legend:{display:false}},
      scales: {
        y: {min:0,max:100,grid:{color:"#20314c"},ticks:{color:"#8da0ba"}},
        x: {grid:{display:false},ticks:{color:"#8da0ba"}}
      }
    }
  });
  ctx.canvas.parentElement.style.height = "245px";
}

function renderTimeline(flaws) {
  $("flawCount").textContent = `${flaws.length} issue${flaws.length === 1 ? "" : "s"}`;
  const box = $("timeline");
  if (!flaws.length) {
    box.innerHTML = `<div class="empty">No major temporal flaws detected. Great control.</div>`;
    return;
  }
  box.innerHTML = flaws.map(f => `
    <div class="flaw">
      <div class="time">${fmtTime(f.time)}${f.end ? "–"+fmtTime(f.end) : ""}</div>
      <div><strong>${escapeHtml(f.type)}</strong><p>${escapeHtml(f.message)}</p></div>
      <span class="severity ${f.severity}">${f.severity}</span>
    </div>`).join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[c]));
}

function setMessage(msg) {
  $("message").textContent = msg || "";
}

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    const section = btn.dataset.section;
    const target = {
      dashboard: "results",
      timeline: "timelinePanel",
      transcript: "transcriptPanel",
      improve: "timelinePanel"
    }[section];
    if (target) $(target).scrollIntoView({behavior:"smooth", block:"center"});
  });
});
