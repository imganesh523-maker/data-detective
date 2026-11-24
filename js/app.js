/* Data Detective - game engine (no framework, no tracking). Built by Ganesh Kumar. */
const GAME_URL = "https://imganesh523-maker.github.io/data-detective/";
const STORE_KEY = "data-detective-progress-v1";
const RUN_TIMEOUT_MS = 20000;
const RANKS = [
  { min: 0, name: "Rookie" },
  { min: 2, name: "Sub-Inspector" },
  { min: 4, name: "Inspector" },
  { min: 6, name: "Chief" },
];
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad2 = (n) => String(n).padStart(2, "0");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let CASES = [];
let current = null; // { case, stepIndex }

// ====================================================================== state
const State = {
  data: { solved: {}, steps: {}, hints: {}, code: {}, passed: {}, seenStory: {}, unlockAll: false },
  load() {
    try { Object.assign(this.data, JSON.parse(localStorage.getItem(STORE_KEY) || "{}")); } catch (e) { /* ignore */ }
  },
  save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(this.data)); } catch (e) { /* private mode */ } },
  reset() { localStorage.removeItem(STORE_KEY); location.reload(); },
  solvedCount() { return CASES.filter((c) => this.data.solved[c.id]).length; },
  stepsDone(c) { return this.data.steps[c.id] || 0; },
  isUnlocked(i) { return this.data.unlockAll || i === 0 || !!this.data.solved[CASES[i - 1].id]; },
  rank(n = this.solvedCount()) { return [...RANKS].reverse().find((r) => n >= r.min).name; },
  xp() {
    let xp = 0;
    for (const c of CASES) {
      const done = this.stepsDone(c);
      for (let i = 0; i < done; i++) xp += Math.max(10, 100 - 30 * (this.data.hints[`${c.id}:${i}`] || 0));
    }
    return xp;
  },
  maxXp() { return CASES.reduce((a, c) => a + c.steps.length * 100, 0); },
};

// ====================================================================== Python lab (web worker)
const Lab = {
  worker: null, ready: null, seq: 0, pending: new Map(), timer: null, statusEl: null,
  setStatus(kind, text) {
    const el = $("#labStatus");
    el.className = "lab-status " + kind;
    $(".lab-status-text", el).textContent = text;
  },
  boot() {
    if (this.ready) return this.ready;
    this.setStatus("booting", "Booting Python…");
    this.worker = new Worker(new URL("./worker.js", import.meta.url));
    this.ready = new Promise((resolve, reject) => {
      this.worker.onmessage = (ev) => {
        const m = ev.data;
        if (m.type === "status") { this.setStatus("booting", m.text); Console.bootText(m.text); }
        else if (m.type === "ready") { this.setStatus("ready", `Python ready · Pyodide ${m.version}`); resolve(); }
        else if (m.type === "running") { this.setStatus("running", "Running your code…"); this.armTimeout(m.id); }
        else if (m.type === "prepared") { this.setStatus("ready", "Python ready"); this.settle(m.id, null); }
        else if (m.type === "result") { clearTimeout(this.timer); this.setStatus("ready", "Python ready"); this.settle(m.id, m.result); }
        else if (m.type === "fatal") {
          clearTimeout(this.timer);
          if (m.id === undefined || !this.pending.has(m.id)) {
            this.setStatus("error", "Python failed to load");
            this.ready = null; this.worker.terminate();
            reject(new Error(m.error));
          } else { this.setStatus("ready", "Python ready"); this.settle(m.id, null, new Error(m.error)); }
        }
      };
      this.worker.onerror = (e) => { this.setStatus("error", "Python failed to load"); this.ready = null; reject(new Error(e.message || "worker error")); };
    });
    this.worker.postMessage({ type: "boot", runtimeUrl: new URL("./runtime.py", import.meta.url).href });
    return this.ready;
  },
  settle(id, result, err) {
    const p = this.pending.get(id);
    if (!p) return;
    this.pending.delete(id);
    err ? p.reject(err) : p.resolve(result);
  },
  armTimeout(id) {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      const p = this.pending.get(id);
      this.worker.terminate();
      this.ready = null; this.pending.clear();
      this.setStatus("error", "Lab restarted");
      if (p) p.reject(Object.assign(new Error("timeout"), { timeout: true }));
    }, RUN_TIMEOUT_MS);
  },
  async send(type, payload) {
    await this.boot();
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ type, id, ...payload });
    });
  },
  allFiles() {
    return CASES.flatMap((c) => c.files).map((name) => ({ name, url: new URL("../data/" + name, import.meta.url).href }));
  },
  prepare(pkgs) { return this.send("prepare", { packages: pkgs, files: this.allFiles() }); },
  run(code, prelude, check, pkgs) { return this.send("run", { code, prelude, check, packages: pkgs, files: this.allFiles() }); },
};

// ====================================================================== console
const Console = {
  body: () => $("#consoleBody"),
  clear() { this.body().innerHTML = ""; },
  bootText(text) {
    let b = $(".booting", this.body());
    if (!b) {
      b = document.createElement("div"); b.className = "booting";
      b.innerHTML = `<span class="bt"></span><div class="boot-bar"></div>`;
      this.body().appendChild(b);
    }
    $(".bt", b).textContent = "🔌 " + text;
  },
  dropBoot() { $$(".booting", this.body()).forEach((b) => b.remove()); },
  sep(label) {
    const d = document.createElement("div"); d.className = "run-sep"; d.textContent = label;
    this.body().appendChild(d);
  },
  render(res, target = this.body()) {
    const frag = document.createDocumentFragment();
    if (res.output) { const pre = document.createElement("pre"); pre.className = "out"; pre.textContent = res.output; frag.appendChild(pre); }
    if (res.error) frag.appendChild(errorBox(res.error));
    if (res.display) {
      if (res.display.kind === "html") {
        const w = document.createElement("div"); w.className = "tablewrap"; w.innerHTML = res.display.html; frag.appendChild(w);
        if (res.display.note) { const n = document.createElement("div"); n.className = "note"; n.textContent = res.display.note; frag.appendChild(n); }
      } else { const pre = document.createElement("pre"); pre.className = "out"; pre.textContent = res.display.text; frag.appendChild(pre); }
    }
    for (const f of res.figures || []) {
      const img = new Image(); img.className = "fig"; img.alt = "Chart produced by your code"; img.src = "data:image/png;base64," + f; frag.appendChild(img);
    }
    if (!res.output && !res.error && !res.display && !(res.figures || []).length) {
      const p = document.createElement("pre"); p.className = "out muted"; p.textContent = "(ran fine - nothing was printed)"; frag.appendChild(p);
    }
    target.appendChild(frag);
    target.scrollTop = target.scrollHeight;
  },
};

function errorBox(e) {
  const d = document.createElement("div"); d.className = "err";
  d.innerHTML = `<span class="t"></span><span class="tip"></span>`;
  $(".t", d).textContent = e.title;
  $(".tip", d).textContent = e.tip;
  return d;
}

// ====================================================================== editor
const Editor = {
  view: null, CM: null, fallback: null, onChange: null,
  async init() {
    const host = $("#editor");
    try {
      const CM = await import("../vendor/codemirror.bundle.js");
      this.CM = CM;
      const runKeys = CM.Prec.highest(CM.keymap.of([
        { key: "Mod-Enter", run: () => { runCurrent(); return true; } },
        { key: "Shift-Enter", run: () => { runCurrent(); return true; } },
      ]));
      this.extensions = [
        CM.basicSetup, CM.python(), CM.oneDark, runKeys, CM.keymap.of([CM.indentWithTab]),
        CM.EditorView.theme({ "&": { backgroundColor: "#0b0d11" }, ".cm-gutters": { backgroundColor: "#0b0d11", borderRight: "1px solid #1f242c" } }),
        CM.EditorView.updateListener.of((u) => { if (u.docChanged && this.onChange) this.onChange(this.get()); }),
        CM.EditorView.contentAttributes.of({ "aria-label": "Python code editor. Press Escape then Tab to leave the editor." }),
      ];
      this.view = new CM.EditorView({ parent: host, state: CM.EditorState.create({ doc: "", extensions: this.extensions }) });
    } catch (e) {
      console.warn("CodeMirror failed, using textarea", e);
      const ta = document.createElement("textarea");
      ta.className = "fallback"; ta.spellcheck = false; ta.setAttribute("aria-label", "Python code editor");
      ta.addEventListener("keydown", (ev) => {
        if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") { ev.preventDefault(); runCurrent(); }
        if (ev.key === "Tab") { ev.preventDefault(); const s = ta.selectionStart; ta.setRangeText("    ", s, ta.selectionEnd, "end"); }
      });
      ta.addEventListener("input", () => this.onChange && this.onChange(ta.value));
      host.appendChild(ta); this.fallback = ta;
    }
  },
  get() { return this.view ? this.view.state.doc.toString() : this.fallback.value; },
  set(code, keepHistory = false) {
    if (this.view) {
      if (keepHistory) this.view.dispatch({ changes: { from: 0, to: this.view.state.doc.length, insert: code } });
      else this.view.setState(this.CM.EditorState.create({ doc: code, extensions: this.extensions }));
    } else this.fallback.value = code;
  },
  focus() { this.view ? this.view.focus() : this.fallback.focus(); },
};

// ====================================================================== tiny python highlighter (briefing examples)
function highlight(code) {
  const KW = /^(import|from|as|for|in|if|elif|else|while|def|return|and|or|not|True|False|None|print|len|range|lambda|with|is)$/;
  const re = /(#[^\n]*)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)(?=\s*\()|([A-Za-z_]\w*)|([\s\S])/g;
  let out = "", m;
  while ((m = re.exec(code))) {
    if (m[1]) out += `<span class="tok-c">${esc(m[1])}</span>`;
    else if (m[2]) out += `<span class="tok-s">${esc(m[2])}</span>`;
    else if (m[3]) out += `<span class="tok-n">${m[3]}</span>`;
    else if (m[4]) out += KW.test(m[4]) ? `<span class="tok-k">${m[4]}</span>` : `<span class="tok-f">${m[4]}</span>`;
    else if (m[5]) out += KW.test(m[5]) ? `<span class="tok-k">${m[5]}</span>` : m[5];
    else out += esc(m[6]);
  }
  return out;
}

// ====================================================================== typewriter
let typeToken = 0;
async function typewrite(container, paragraphs, { speed = 16, instant = false } = {}) {
  const token = ++typeToken;
  container.innerHTML = "";
  container.classList.add("typed");
  const ps = paragraphs.map((t) => { const p = document.createElement("p"); container.appendChild(p); return [p, t]; });
  if (instant || reduceMotion) { ps.forEach(([p, t]) => (p.textContent = t)); return true; }
  const caret = document.createElement("span"); caret.className = "caret";
  for (const [p, text] of ps) {
    for (let i = 0; i <= text.length; i++) {
      if (token !== typeToken) { ps.forEach(([pp, tt]) => (pp.textContent = tt)); return false; }
      p.textContent = text.slice(0, i); p.appendChild(caret);
      await sleep(text[i - 1] === "." || text[i - 1] === "?" || text[i - 1] === "!" ? speed * 9 : speed);
    }
    await sleep(240);
  }
  caret.remove();
  return true;
}
function skipTyping() { typeToken++; }

// ====================================================================== rain
function startRain() {
  const c = $("#rain"); if (reduceMotion || !c) return;
  const ctx = c.getContext("2d");
  let drops = [];
  const resize = () => {
    c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio;
    drops = Array.from({ length: Math.min(140, Math.floor(innerWidth / 9)) }, () => ({
      x: Math.random() * c.width, y: Math.random() * c.height, l: 10 + Math.random() * 22, v: 7 + Math.random() * 9,
    }));
  };
  resize(); addEventListener("resize", resize);
  const tick = () => {
    if (!document.hidden && !$("#view-title").hidden) {
      ctx.clearRect(0, 0, c.width, c.height);
      ctx.strokeStyle = "rgba(170,190,215,.22)"; ctx.lineWidth = 1 * devicePixelRatio;
      ctx.beginPath();
      for (const d of drops) {
        ctx.moveTo(d.x, d.y); ctx.lineTo(d.x - 2, d.y + d.l * devicePixelRatio);
        d.y += d.v * devicePixelRatio; d.x -= .4;
        if (d.y > c.height) { d.y = -30; d.x = Math.random() * c.width; }
      }
      ctx.stroke();
    } else ctx.clearRect(0, 0, c.width, c.height);
    requestAnimationFrame(tick);
  };
  tick();
}

// ====================================================================== views
function showView(name) {
  for (const v of ["title", "board", "case"]) $(`#view-${v}`).hidden = v !== name;
  $("#topbar").hidden = name === "title";
  if (name === "board") renderBoard();
  if (name !== "case") skipTyping();
  window.scrollTo({ top: 0 });
  updateHud();
}

function updateHud() {
  $("#rankBadge").textContent = State.rank().toUpperCase();
  const xp = State.xp();
  $("#xpText").textContent = `${xp} XP`;
  $("#xpFill").style.width = `${Math.round((xp / State.maxXp()) * 100)}%`;
}

// ====================================================================== board
function renderBoard() {
  const grid = $("#caseGrid");
  grid.innerHTML = "";
  const rots = [-2.2, 1.6, -1.1, 2.0, -1.7, 1.2];
  CASES.forEach((c, i) => {
    const unlocked = State.isUnlocked(i);
    const solved = !!State.data.solved[c.id];
    const done = State.stepsDone(c);
    const li = document.createElement("li");
    li.className = "case-card" + (unlocked ? "" : " locked");
    li.style.setProperty("--rot", rots[i % rots.length] + "deg");
    const status = solved ? `<span class="case-stamp closed">CLOSED</span>` :
      done > 0 ? `<span class="case-stamp progress">${done}/${c.steps.length}</span>` :
      unlocked ? `<span class="case-stamp open">OPEN</span>` : "";
    li.innerHTML = `
      <span class="pin" aria-hidden="true"></span>
      <button class="folder" ${unlocked ? "" : 'aria-disabled="true"'} aria-label="Case ${c.num}: ${esc(c.title)}${solved ? " (closed)" : unlocked ? "" : " (locked)"}">
        <span class="case-num"><svg viewBox="0 0 64 64" aria-hidden="true"><use href="#i-${c.icon}"/></svg>CASE FILE #${pad2(c.num)}</span>
        <h3>${esc(c.title)}</h3>
        <p class="case-loc">${esc(c.location.split("·")[0])}</p>
        <span class="tags">${c.concepts.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</span>
        ${status}
      </button>
      ${unlocked ? "" : `<div class="lockmsg"><div><svg viewBox="0 0 64 64"><use href="#i-lock"/></svg>Close case #${pad2(c.num - 1)} to unlock</div></div>`}`;
    $("button.folder", li).addEventListener("click", () => {
      if (!unlocked) { toast(`Locked - close case #${pad2(c.num - 1)} first (or use preview mode below).`); return; }
      openCase(c.id);
    });
    grid.appendChild(li);
  });
  const n = State.solvedCount();
  $("#boardProgress").innerHTML = `<b>${n} / ${CASES.length}</b>cases closed · rank ${esc(State.rank())}`;
  $("#btnUnlockAll").textContent = State.data.unlockAll ? "Preview mode is on (all cases unlocked)" : "Preview mode: unlock all cases";
  requestAnimationFrame(drawStrings);
}

function drawStrings() {
  const svg = $("#strings"); const board = $("#board");
  if (!svg || $("#view-board").hidden) return;
  const b = board.getBoundingClientRect();
  const pins = $$(".case-card .pin", board).map((p) => { const r = p.getBoundingClientRect(); return [r.left - b.left + r.width / 2, r.top - b.top + r.height / 2]; });
  svg.setAttribute("viewBox", `0 0 ${b.width} ${b.height}`);
  let d = "";
  for (let i = 1; i < pins.length; i++) {
    const [x1, y1] = pins[i - 1], [x2, y2] = pins[i];
    const mx = (x1 + x2) / 2, my = Math.max(y1, y2) + 40;
    d += `<path d="M${x1},${y1} Q${mx},${my} ${x2},${y2}" style="animation-delay:${i * 0.12}s"/>`;
  }
  svg.innerHTML = d;
}

// ====================================================================== case view
function openCase(id, tab) {
  const c = CASES.find((x) => x.id === id);
  const done = State.stepsDone(c);
  current = { case: c, stepIndex: Math.min(done, c.steps.length - 1) };
  showView("case");
  $("#caseKicker").textContent = `Case #${pad2(c.num)} · ${c.location}`;
  $("#caseTitle").textContent = c.title;
  renderStory(); renderBriefing(); renderSteps(); renderEvidence();
  loadStepCode();
  Console.clear();
  const hint = document.createElement("p"); hint.className = "muted console-hint";
  hint.innerHTML = `Press <b>Run</b> (or <kbd>Ctrl</kbd>+<kbd>Enter</kbd>) to execute your code. Evidence files are already in the lab's folder - open them by name.`;
  Console.body().appendChild(hint);
  const startTab = tab || (State.data.seenStory[c.id] ? (done > 0 || State.data.solved[c.id] ? "steps" : "brief") : "story");
  selectTab(startTab);
  // lazily boot Python + this case's packages in the background
  Lab.prepare(c.packages).then(() => Console.dropBoot()).catch((e) => bootFailed(e));
}

function bootFailed(e) {
  Console.dropBoot();
  Console.render({ error: { title: "Couldn't start Python", tip: "The Python lab downloads from cdn.jsdelivr.net on first use. Check your internet connection (or an ad/script blocker) and press Run to try again. " + (e && e.message ? `(${e.message})` : "") } });
}

function selectTab(name) {
  for (const t of $$(".tab")) {
    const on = t.dataset.tab === name;
    t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1;
    $(`#panel-${t.dataset.tab}`).hidden = !on;
  }
  if (name === "story") playStory();
}

function renderStory() {
  const c = current.case;
  const ch = c.character;
  const initials = ch.name.replace(/^(Prof\.|Er\.|Seth|Coach)\s+/, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2);
  $("#panel-story").innerHTML = `
    <div class="dossier">
      <div class="mugshot"><span>${esc(initials)}</span><svg viewBox="0 0 300 420" aria-hidden="true"><use href="#i-detective"/></svg></div>
      <div>
        <h3>${esc(ch.name)}</h3>
        <p class="role">${esc(ch.role)}</p>
        <blockquote>"${esc(ch.quote)}"</blockquote>
        <ul>${ch.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      </div>
    </div>
    <p class="location">📍 ${esc(c.location)}</p>
    <div id="storyText" aria-live="off"></div>
    <div class="story-actions">
      <button class="btn ghost small" id="btnSkip">Skip ▸▸</button>
      <button class="btn primary" id="btnAccept">Take the case →</button>
    </div>`;
  $("#btnSkip").onclick = () => { skipTyping(); $("#btnSkip").hidden = true; };
  $("#btnAccept").onclick = () => { skipTyping(); State.data.seenStory[c.id] = true; State.save(); selectTab("brief"); };
}

async function playStory() {
  const c = current.case;
  const el = $("#storyText");
  if (!el) return;
  const seen = !!State.data.seenStory[c.id];
  $("#btnSkip").hidden = seen;
  await typewrite(el, c.story, { instant: seen });
  if ($("#btnSkip")) $("#btnSkip").hidden = true;
}

function renderBriefing() {
  const c = current.case, b = c.briefing;
  $("#panel-brief").innerHTML = `
    <div class="brief-card">
      <p class="kicker">New skills for this case</p>
      <h3>${esc(b.title)}</h3>
      <ul>${b.points.map((p) => `<li>${p}</li>`).join("")}</ul>
      <div class="example">
        <div class="example-bar"><span>example.py - try it, it's real Python</span><button class="btn run small" id="btnExample">▶ Run example</button></div>
        <pre><code>${highlight(b.example)}</code></pre>
        <div class="example-out" id="exampleOut" hidden></div>
      </div>
      <div class="story-actions"><button class="btn primary" id="btnToSteps">Start investigating →</button></div>
    </div>`;
  $("#btnToSteps").onclick = () => { State.data.seenStory[c.id] = true; State.save(); selectTab("steps"); };
  $("#btnExample").onclick = async () => {
    const out = $("#exampleOut"); out.hidden = false; out.innerHTML = `<p class="muted">Running… (first run boots Python - give it a few seconds)</p>`;
    $("#btnExample").disabled = true;
    try {
      const res = await Lab.run(b.example, [], null, c.packages);
      out.innerHTML = ""; Console.render(res, out);
    } catch (e) {
      out.innerHTML = ""; out.appendChild(errorBox({ title: "Lab problem", tip: e.timeout ? "That took too long - the lab restarted." : "Python couldn't start. Check your connection and try again." }));
    } finally { $("#btnExample").disabled = false; }
  };
}

function renderSteps() {
  const c = current.case, i = current.stepIndex, s = c.steps[i];
  const done = State.stepsDone(c);
  const hintLevel = State.data.hints[`${c.id}:${i}`] || 0;
  const solvedThis = i < done;
  $("#fileName").textContent = `case${c.num}_step${i + 1}.py`;
  $("#panel-steps").innerHTML = `
    <div class="stepper" role="list">${c.steps.map((st, k) => `
      <button role="listitem" class="stepdot ${k < done ? "done" : ""} ${k === i ? "current" : ""}" data-step="${k}" ${k > done ? "disabled" : ""}
        aria-label="Step ${k + 1}: ${esc(st.title)}${k < done ? " (solved)" : ""}"><span class="n">${k < done ? "✓" : k + 1}</span>${esc(st.title)}</button>`).join("")}
    </div>
    <article class="step-card">
      <p class="kicker">Clue ${i + 1} of ${c.steps.length}</p>
      <h3>${esc(s.title)}</h3>
      <div class="task">${s.task}</div>
      <div class="hints" id="hints"></div>
      <div id="feedback"></div>
    </article>`;
  $$(".stepdot", $("#panel-steps")).forEach((b) => (b.onclick = () => { if (!b.disabled) { current.stepIndex = +b.dataset.step; renderSteps(); loadStepCode(); } }));
  renderHints(hintLevel);
  if (solvedThis) showFeedback(true, "You already cracked this clue. Run it again any time, or move on.", true);
}

function renderHints(level) {
  const c = current.case, i = current.stepIndex, s = c.steps[i];
  const box = $("#hints");
  const parts = [];
  for (let k = 0; k < level && k < 2; k++) parts.push(`<div class="hint"><b class="h">Hint ${k + 1}</b>${s.hints[k]}</div>`);
  if (level >= 3) parts.push(`<div class="hint"><b class="h">Solution</b>Here's one way to do it. Read it, then type or load it and press Run.<pre><code>${highlight(s.solution)}</code></pre><button class="btn small" id="btnLoadSol">Load into editor</button></div>`);
  const labels = ["Hint 1", "Hint 2", "Show solution"];
  const btn = level < 3 ? `<div class="hint-buttons"><button class="btn ghost small" id="btnHint">💡 ${labels[level]}${level === 2 ? " (costs XP)" : ""}</button><span class="muted" style="font-size:13px;align-self:center">${level === 0 ? "Stuck? Hints cost a little XP." : ""}</span></div>` : "";
  box.innerHTML = parts.join("") + btn;
  if ($("#btnHint")) $("#btnHint").onclick = () => {
    const key = `${c.id}:${i}`;
    State.data.hints[key] = Math.min(3, (State.data.hints[key] || 0) + 1); State.save();
    renderHints(State.data.hints[key]);
  };
  if ($("#btnLoadSol")) $("#btnLoadSol").onclick = () => { Editor.set(s.solution, true); Editor.focus(); };
}

function showFeedback(pass, message, quiet = false) {
  const c = current.case, i = current.stepIndex;
  const last = i === c.steps.length - 1;
  const fb = $("#feedback");
  fb.innerHTML = `<div class="feedback ${pass ? "pass" : "fail"}" role="status">
    <span class="fb-title">${pass ? (quiet ? "Solved" : "Clue found!") : "Not quite, detective"}</span>
    <span class="fb-msg"></span>
    ${pass ? `<div><button class="btn primary" id="btnNextStep">${last ? (State.data.solved[c.id] ? "Case summary →" : "Close the case →") : "Next clue →"}</button></div>` : ""}
  </div>`;
  $(".fb-msg", fb).textContent = message;
  if (pass) $("#btnNextStep").onclick = () => {
    if (last) showClosed(c, false);
    else { current.stepIndex = i + 1; renderSteps(); loadStepCode(); Editor.focus(); }
  };
}

function codeKey() { return `${current.case.id}:${current.stepIndex}`; }
let saveTimer = null;
function loadStepCode() {
  const s = current.case.steps[current.stepIndex];
  Editor.set(State.data.code[codeKey()] ?? s.starter);
  Editor.onChange = (code) => { clearTimeout(saveTimer); const k = codeKey(); saveTimer = setTimeout(() => { State.data.code[k] = code; State.save(); }, 400); };
}

function prelude() {
  const c = current.case;
  const out = [];
  for (let k = 0; k < current.stepIndex; k++) out.push(State.data.passed[`${c.id}:${k}`] || c.steps[k].solution);
  return out;
}

let running = false;
async function runCurrent() {
  if (!current || running || $("#view-case").hidden) return;
  const c = current.case, i = current.stepIndex, s = c.steps[i];
  const code = Editor.get();
  State.data.code[codeKey()] = code; State.save();
  running = true; $("#btnRun").disabled = true;
  $(".console-hint", Console.body())?.remove();
  Console.sep(`▶ run · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`);
  try {
    const res = await Lab.run(code, prelude(), s.check, c.packages);
    Console.dropBoot();
    Console.render(res);
    if (matchMedia("(max-width: 900px)").matches) $("#console").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
    const ck = res.check;
    if (ck && ck.passed) {
      State.data.passed[codeKey()] = code;
      const before = State.stepsDone(c);
      if (i + 1 > before) State.data.steps[c.id] = i + 1;
      State.save(); updateHud();
      renderSteps();
      showFeedback(true, ck.message);
      selectTab("steps");
      if (i === c.steps.length - 1 && !State.data.solved[c.id]) setTimeout(() => showClosed(c, true), 1100);
    } else if (ck) {
      showFeedback(false, res.error ? "Your code hit an error - the console explains it in plain English. Fix it and run again." : ck.message);
    }
  } catch (e) {
    Console.dropBoot();
    if (e.timeout) Console.render({ error: { title: "Stopped: your code ran for over 20 seconds", tip: "That usually means a loop that never ends (e.g. a while loop whose condition never becomes False). I restarted the Python lab - fix the loop and run again." } });
    else bootFailed(e);
  } finally {
    running = false; $("#btnRun").disabled = false;
  }
}

async function renderEvidence() {
  const c = current.case;
  const panel = $("#panel-evidence");
  panel.innerHTML = `<p class="muted">These files sit in the lab's working folder. Open them in code by name, e.g. <code>pd.read_csv("${c.files[0]}")</code>.</p>` +
    c.files.map((f) => `<section class="evidence-file"><header><b>📁 ${esc(f)}</b><a class="btn ghost small" href="data/${esc(f)}" download>Download</a></header><div class="tablewrap" data-file="${esc(f)}"><p class="muted" style="padding:10px 14px">Loading preview…</p></div></section>`).join("");
  for (const f of c.files) {
    try {
      const text = await (await fetch("data/" + f)).text();
      const rows = parseCSV(text);
      const head = rows[0], body = rows.slice(1, 9);
      const el = panel.querySelector(`[data-file="${CSS.escape(f)}"]`);
      if (!el) continue;
      el.innerHTML = `<table class="df"><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${body.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table><p class="muted" style="padding:0 14px 10px;font-size:13px">First ${body.length} of ${rows.length - 1} rows</p>`;
    } catch (e) { /* offline preview is optional */ }
  }
}

function parseCSV(text) {
  const rows = []; let row = [], val = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"') { if (text[i + 1] === '"') { val += '"'; i++; } else q = false; } else val += ch; }
    else if (ch === '"') q = true;
    else if (ch === ",") { row.push(val); val = ""; }
    else if (ch === "\n") { row.push(val); rows.push(row); row = []; val = ""; }
    else if (ch !== "\r") val += ch;
  }
  if (val || row.length) { row.push(val); rows.push(row); }
  return rows;
}

// ====================================================================== case closed
let lastShare = null;
function showClosed(c, fresh) {
  const beforeRank = State.rank();
  if (fresh) { State.data.solved[c.id] = true; State.save(); updateHud(); }
  const rank = State.rank();
  const allDone = State.solvedCount() === CASES.length;
  $("#closedKicker").textContent = `Case #${pad2(c.num)} · ${c.location.split("·")[0].trim()}`;
  $("#closedTitle").textContent = c.title;
  const promo = $("#promo");
  if (fresh && rank !== beforeRank) {
    promo.hidden = false;
    promo.innerHTML = `Promotion! You are now <b>${esc(rank.toUpperCase())}</b>${rank === "Chief" ? " - the city's top data detective." : "."}`;
  } else if (allDone) {
    promo.hidden = false; promo.innerHTML = `All ${CASES.length} cases closed. Rank: <b>${esc(rank.toUpperCase())}</b>`;
  } else promo.hidden = true;
  const idx = CASES.indexOf(c);
  const next = CASES[idx + 1];
  const nb = $("#btnNextCase");
  nb.textContent = next ? `Next case: ${next.title} →` : "Back to the board";
  nb.onclick = () => { hide("closed"); next ? openCase(next.id) : showView("board"); };
  lastShare = allDone && c.num === CASES.length
    ? { mode: "final", title: "All 6 cases closed", rank, caseNum: c.num, concepts: ["python", "pandas", "groupby", "merge", "datetime", "numpy"] }
    : { mode: "case", title: c.title, rank, caseNum: c.num, concepts: c.concepts, location: c.location.split("·")[0].trim() };
  drawCard($("#shareCanvas"), lastShare);
  show("closed");
  typewrite($("#closedStory"), c.closing, { speed: 12, instant: !fresh });
}

function caption() {
  const s = lastShare || { title: "Data Detective", rank: State.rank() };
  const what = s.mode === "final" ? "closed all 6 cases" : `just closed "${s.title}"`;
  return `I ${what} in Data Detective and made rank ${s.rank}. It's a noir story game where you solve crimes in Mumbai by writing real Python & Pandas in the browser. Try it free: ${GAME_URL}`;
}

// ====================================================================== share card (1200 x 627)
function wrapText(ctx, text, maxW) {
  const words = text.split(" "); const lines = []; let line = "";
  for (const w of words) { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t; }
  if (line) lines.push(line);
  return lines;
}
function roundRect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

async function drawCard(canvas, o) {
  await Promise.all(["40px 'Bebas Neue'", "20px 'Special Elite'", "20px 'IBM Plex Sans'", "600 20px 'IBM Plex Sans'", "20px 'JetBrains Mono'"].map((f) => document.fonts.load(f).catch(() => {})));
  const W = 1200, H = 627, ctx = canvas.getContext("2d");
  canvas.width = W; canvas.height = H;
  // background
  const bg = ctx.createLinearGradient(0, 0, W, H); bg.addColorStop(0, "#0c0e12"); bg.addColorStop(1, "#151017");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(980, 60, 10, 980, 60, 560); glow.addColorStop(0, "rgba(242,177,52,.28)"); glow.addColorStop(1, "rgba(242,177,52,0)");
  ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(255,255,255,.035)"; ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  // rain streaks
  ctx.strokeStyle = "rgba(170,190,215,.10)";
  for (let i = 0; i < 70; i++) { const x = (i * 97) % W, y = (i * 53) % H; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 4, y + 26); ctx.stroke(); }

  // folder
  ctx.save(); ctx.translate(70, 92); ctx.rotate(-0.025);
  ctx.shadowColor = "rgba(0,0,0,.6)"; ctx.shadowBlur = 40; ctx.shadowOffsetY = 18;
  ctx.fillStyle = "#e6d7b3"; roundRect(ctx, 20, -26, 250, 40, 10); ctx.fill();
  const pg = ctx.createLinearGradient(0, 0, 0, 450); pg.addColorStop(0, "#f0e4c8"); pg.addColorStop(1, "#d9c79c");
  ctx.fillStyle = pg; roundRect(ctx, 0, 0, 640, 465, 12); ctx.fill();
  ctx.shadowColor = "transparent";
  // pin
  const pin = ctx.createRadialGradient(316, -2, 2, 320, 2, 14); pin.addColorStop(0, "#ff8d9c"); pin.addColorStop(1, "#a3192d");
  ctx.fillStyle = pin; ctx.beginPath(); ctx.arc(320, 4, 13, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "#6b5a3d"; ctx.font = "22px 'Special Elite'";
  const topLine = o.mode === "og" ? "BUREAU OF DATA CRIMES · MUMBAI" : o.mode === "final" ? "FINAL REPORT · ALL CASES" : `CASE FILE #${pad2(o.caseNum)}`;
  ctx.fillText(topLine, 36, 58);
  ctx.fillStyle = "#1f190f"; ctx.font = "84px 'Bebas Neue'";
  const lines = wrapText(ctx, o.title.toUpperCase(), 570).slice(0, 3);
  lines.forEach((l, k) => ctx.fillText(l, 34, 140 + k * 78));
  let y = 140 + lines.length * 78 - 10;
  if (o.location) { ctx.font = "22px 'Special Elite'"; ctx.fillStyle = "#5d4f37"; ctx.fillText(o.location, 36, y); y += 18; }
  // tags (kept clear of the stamp in the bottom-right corner)
  ctx.font = "19px 'JetBrains Mono'"; let tx = 36; y += 26;
  for (const t of (o.concepts || []).slice(0, 6)) {
    const w = ctx.measureText(t).width + 24;
    if (tx + w > 610) { tx = 36; y += 40; }
    if (y > 430) break;
    if (y > 345 && tx + w > 330) continue;
    ctx.fillStyle = "rgba(42,35,24,.12)"; roundRect(ctx, tx, y - 22, w, 32, 16); ctx.fill();
    ctx.strokeStyle = "rgba(42,35,24,.3)"; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = "#3a301f"; ctx.fillText(t, tx + 12, y);
    tx += w + 10;
  }
  // stamp
  ctx.save(); ctx.translate(452, 408); ctx.rotate(-0.16);
  const stampText = o.mode === "og" ? "CLASSIFIED" : "CASE CLOSED";
  ctx.font = "64px 'Bebas Neue'"; const sw = ctx.measureText(stampText).width + 40;
  ctx.strokeStyle = "rgba(176,23,44,.92)"; ctx.lineWidth = 7; roundRect(ctx, -sw / 2, -46, sw, 78, 10); ctx.stroke();
  ctx.fillStyle = "rgba(176,23,44,.92)"; ctx.textAlign = "center"; ctx.fillText(stampText, 0, 16); ctx.textAlign = "left";
  ctx.restore();
  ctx.restore();

  // right column
  const X = 770;
  ctx.fillStyle = "#ece8df"; ctx.font = "92px 'Bebas Neue'"; ctx.fillText("DATA", X, 150);
  ctx.strokeStyle = "#f2b134"; ctx.lineWidth = 2.5; ctx.strokeText("DETECTIVE", X, 232);
  ctx.fillStyle = "#c9c2b4"; ctx.font = "23px 'Special Elite'";
  wrapText(ctx, "Learn Python & Pandas by solving crimes.", 380).forEach((l, k) => ctx.fillText(l, X, 280 + k * 32));
  if (o.mode === "og") {
    ctx.font = "19px 'JetBrains Mono'"; ctx.fillStyle = "#a8e6a3";
    ["suspects = df[df.seconds < 20]", "suspects.agent_id.value_counts()"].forEach((l, k) => ctx.fillText(l, X, 372 + k * 30));
    ctx.fillStyle = "#ece8df"; ctx.font = "600 22px 'IBM Plex Sans'"; ctx.fillText("6 cases · 22 clues · free, no login", X, 460);
  } else {
    ctx.fillStyle = "#a7afba"; ctx.font = "600 20px 'IBM Plex Sans'"; ctx.fillText("RANK", X, 380);
    ctx.fillStyle = "#f2b134"; ctx.font = "70px 'Bebas Neue'"; ctx.fillText(o.rank.toUpperCase(), X, 446);
  }
  const shortUrl = GAME_URL.replace("https://", "").replace(/\/$/, "");
  let fs = 20; ctx.font = `${fs}px 'JetBrains Mono'`;
  while (ctx.measureText(shortUrl).width > W - X - 30 && fs > 11) { fs--; ctx.font = `${fs}px 'JetBrains Mono'`; }
  ctx.fillStyle = "#ece8df"; ctx.fillText(shortUrl, X, 530);
  ctx.fillStyle = "#a7afba"; ctx.font = "19px 'IBM Plex Sans'"; ctx.fillText("Built by Ganesh Kumar", X, 566);
  // red bar
  ctx.fillStyle = "#e0384f"; ctx.fillRect(0, H - 8, W, 8);
}

function downloadCard() {
  const a = document.createElement("a");
  const name = lastShare && lastShare.mode === "case" ? `data-detective-case-${lastShare.caseNum}-closed.png` : "data-detective-chief.png";
  a.download = name;
  a.href = $("#shareCanvas").toDataURL("image/png");
  document.body.appendChild(a); a.click(); a.remove();
}

// ====================================================================== overlays & toasts
let lastFocus = null;
function show(id) { lastFocus = document.activeElement; $("#" + id).hidden = false; setTimeout(() => ($("#" + id).querySelector("button, a") || {}).focus?.(), 50); }
function hide(id) { $("#" + id).hidden = true; skipTyping(); lastFocus?.focus?.(); }
let toastTimer;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 2600); }

// ====================================================================== wiring
function wire() {
  document.addEventListener("click", (e) => {
    const nav = e.target.closest("[data-nav]");
    if (nav) { $$(".overlay").forEach((o) => (o.hidden = true)); showView(nav.dataset.nav); }
    const op = e.target.closest("[data-open]"); if (op) show(op.dataset.open);
    const cl = e.target.closest("[data-close]"); if (cl) hide(cl.dataset.close);
    const tab = e.target.closest(".tab"); if (tab) selectTab(tab.dataset.tab);
  });
  $(".tabs").addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const tabs = $$(".tab"); const i = tabs.findIndex((t) => t.getAttribute("aria-selected") === "true");
    const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; selectTab(n.dataset.tab); n.focus();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$(".overlay").forEach((o) => { if (!o.hidden) hide(o.id); });
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !$("#view-case").hidden) { e.preventDefault(); runCurrent(); }
  });
  $$(".overlay").forEach((o) => o.addEventListener("click", (e) => { if (e.target === o) hide(o.id); }));
  $("#btnStart").onclick = () => {
    const firstOpen = CASES.find((c, i) => State.isUnlocked(i) && !State.data.solved[c.id]);
    firstOpen ? openCase(firstOpen.id) : showView("board");
  };
  $("#btnRun").onclick = runCurrent;
  $("#btnClear").onclick = () => Console.clear();
  $("#btnResetCode").onclick = () => { Editor.set(current.case.steps[current.stepIndex].starter, true); toast("Code reset to the starter (Ctrl+Z undoes it)."); };
  $("#btnUnlockAll").onclick = () => { State.data.unlockAll = !State.data.unlockAll; State.save(); renderBoard(); };
  $("#btnReset").onclick = () => { if (confirm("Erase all progress, code and XP on this device?")) State.reset(); };
  $("#btnDownload").onclick = downloadCard;
  $("#btnLinkedIn").onclick = () => window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(GAME_URL)}`, "_blank", "noopener,width=640,height=720");
  $("#btnCopyCaption").onclick = async () => { try { await navigator.clipboard.writeText(caption()); toast("Caption copied - paste it into your post."); } catch { prompt("Copy this caption:", caption()); } };
  addEventListener("resize", () => requestAnimationFrame(drawStrings));
}

async function main() {
  State.load();
  wire();
  startRain();
  const [data] = await Promise.all([fetch(new URL("../data/cases.json", import.meta.url)).then((r) => r.json()), Editor.init()]);
  CASES = data.cases;
  updateHud();
  const any = State.solvedCount() > 0 || Object.keys(State.data.steps).length > 0;
  $("#btnStart").textContent = any ? "Continue investigation" : "Start investigating";
  // deep links: #board, #case=railway, #og (renders the static preview card for tooling)
  const h = location.hash;
  if (h === "#board") showView("board");
  else if (h.startsWith("#case=") && CASES.some((c) => c.id === h.slice(6))) openCase(h.slice(6));
  else showView("title");
  typewrite($("#tagline"), ["The city runs on data. So does crime. Learn Python & Pandas by cracking six cases."], { speed: 28 });
  // hooks for automated tests & tooling
  window.DD = {
    cases: () => CASES, state: State, openCase, setCode: (c) => Editor.set(c), getCode: () => Editor.get(), run: runCurrent,
    selectTab, drawCard: (o) => drawCard($("#shareCanvas"), o), showClosed: (id) => showClosed(CASES.find((c) => c.id === id), false),
    current: () => current && { id: current.case.id, step: current.stepIndex },
  };
  document.documentElement.dataset.ready = "1";
}
main();
