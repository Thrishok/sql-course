/* SQL Learning IDE — frontend logic */
const $ = (s) => document.querySelector(s);
const api = (p, opts) => fetch(p, opts).then((r) => r.json());
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

let editor, current = null, curriculum = null;
const done = JSON.parse(localStorage.getItem("sql_done") || "{}");

/* ---- editor ---- */
function initEditor() {
  editor = CodeMirror.fromTextArea($("#editor"), {
    mode: "text/x-mysql",
    theme: "material-darker",
    lineNumbers: true,
    matchBrackets: true,
    smartIndent: true,
    extraKeys: {
      "Ctrl-Enter": runQuery,
      "Cmd-Enter": runQuery,
      "Ctrl-Space": "autocomplete",
      "Shift-Ctrl-Enter": checkAnswer,
    },
  });
}

/* ---- boot ---- */
async function boot() {
  initEditor();
  const health = await api("/api/health").catch(() => ({}));
  $("#engine-badge").textContent = "engine: " + (health.db_backend || "?");
  const mb = $("#model-badge");
  if (health.llm_enabled) { mb.textContent = "qwen: " + health.model; mb.className = "badge on"; }
  else { mb.textContent = "qwen: offline"; mb.className = "badge off"; }

  curriculum = await api("/api/curriculum");
  $("#dataset-name").textContent = "— " + curriculum.dataset.title;
  buildTree();
  const first = curriculum.modules[0]?.lessons[0];
  if (first) loadLesson(first.id);

  $("#btn-run").onclick = runQuery;
  $("#btn-explain").onclick = explainQuery;
  $("#btn-check").onclick = checkAnswer;
  $("#btn-reset").onclick = () => current && editor.setValue(current.lesson.exercise.starter_sql || "");
  document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));
}

/* ---- sidebar tree ---- */
function buildTree() {
  const tree = $("#course-tree");
  tree.innerHTML = "";
  let n = 0;
  curriculum.modules.forEach((m) => {
    const mt = document.createElement("div");
    mt.className = "module-title";
    mt.textContent = m.title;
    tree.appendChild(mt);
    m.lessons.forEach((l) => {
      n++;
      const el = document.createElement("div");
      el.className = "lesson-item" + (done[l.id] ? " done" : "");
      el.dataset.id = l.id;
      el.innerHTML = `<span class="tick">✓</span><span class="lnum">${String(n).padStart(2, "0")}</span><span>${esc(l.title)}</span>`;
      el.onclick = () => loadLesson(l.id);
      tree.appendChild(el);
    });
  });
}
function markActive(id) {
  document.querySelectorAll(".lesson-item").forEach((e) => e.classList.toggle("active", e.dataset.id === id));
}

/* ---- lesson ---- */
async function loadLesson(id) {
  markActive(id);
  $("#lesson-scroll").innerHTML = `<div class="pad muted"><span class="spin"></span> Loading lesson…</div>`;
  const data = await api("/api/lessons/" + id);
  current = data;
  editor.setValue(data.lesson.exercise.starter_sql || "");
  $("#task-prompt").textContent = data.lesson.exercise.prompt;
  renderLesson(data);
  ["results", "explain", "feedback"].forEach((t) => {
    $("#panel-" + t).innerHTML = `<div class="muted pad">${t === "results" ? "Run a query to see results." : t === "explain" ? "Press <b>Explain</b> to see the query plan." : "Press <b>Check answer</b> for Qwen's feedback."}</div>`;
  });
  $("#output-meta").textContent = "";
  switchTab("results");
}

function renderLesson(data) {
  const c = data.content, l = data.lesson;
  const badge = c.generated_by === "qwen" ? "" : ` <span class="badge off" style="font-size:10px">offline</span>`;
  let html = `<div class="lesson-kicker">${esc(l.module_title)}</div>
    <div class="lesson-h1">${esc(l.title)}${badge}</div>
    <div class="lesson-obj">${esc(c.summary || l.objective)}</div>
    <div class="lesson-body">${marked.parse(c.explanation_md || "")}</div>`;

  if (c.syntax) html += `<div class="card"><div class="card-label">Syntax</div><pre class="code">${esc(c.syntax)}</pre></div>`;
  if (c.example && c.example.sql) {
    html += `<div class="card"><div class="card-label">Example</div><pre class="code">${esc(c.example.sql)}</pre>
      <div class="muted" style="font-size:12.5px">${esc(c.example.explains || "")}</div>
      <button class="example-run" data-sql="${esc(c.example.sql)}">↳ Try this example</button></div>`;
  }
  if (c.key_points?.length) html += `<div class="card"><div class="card-label">Key points</div><ul class="keypoints">${c.key_points.map((k) => `<li>${esc(k)}</li>`).join("")}</ul></div>`;
  if (c.hint) html += `<div class="hint-box"><div class="card-label">Hint</div>${esc(c.hint)}</div>`;

  html += `<button class="regen-btn" id="regen">↻ Regenerate with Qwen</button>`;
  html += renderSchema();
  $("#lesson-scroll").innerHTML = html;

  $("#lesson-scroll").querySelectorAll(".example-run").forEach((b) => (b.onclick = () => { editor.setValue(b.dataset.sql); runQuery(); }));
  $("#regen").onclick = async (e) => {
    e.target.innerHTML = `<span class="spin"></span> Generating…`;
    const r = await api("/api/lessons/" + l.id + "/generate", { method: "POST" });
    current.content = r.content; renderLesson(current);
  };
  document.querySelectorAll(".schema-table-head").forEach((h) => (h.onclick = () => h.nextElementSibling.toggleAttribute("hidden")));
}

function renderSchema() {
  const d = curriculum.dataset;
  let h = `<div class="schema"><div class="card-label">${esc(d.title)} · schema</div>`;
  d.tables.forEach((t) => {
    h += `<div class="schema-table"><div class="schema-table-head"><span>${esc(t.name)}</span><span class="muted">${t.columns.length} cols</span></div>
      <div class="schema-cols">${t.columns.map(esc).join("<br>")}</div></div>`;
  });
  return h + `</div>`;
}

/* ---- tabs ---- */
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + name));
}

/* ---- run / explain ---- */
function renderGrid(res) {
  if (res.error) return `<div class="msg-error">${esc(res.error)}</div>`;
  if (!res.columns.length) return `<div class="msg-ok">Statement ran. No rows returned.</div>`;
  let h = `<table class="grid"><thead><tr>${res.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>`;
  h += res.rows.map((r) => `<tr>${r.map((v) => v == null ? `<td class="null">NULL</td>` : `<td>${esc(v)}</td>`).join("")}</tr>`).join("");
  return h + `</tbody></table>`;
}

async function runQuery() {
  switchTab("results");
  $("#panel-results").innerHTML = `<div class="pad muted"><span class="spin"></span> Running…</div>`;
  const res = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sql: editor.getValue() }) });
  $("#panel-results").innerHTML = renderGrid(res);
  $("#output-meta").textContent = res.error ? "error" : `${res.row_count} row${res.row_count === 1 ? "" : "s"} · ${res.elapsed_ms} ms${res.truncated ? " · truncated" : ""}`;
}

async function explainQuery() {
  switchTab("explain");
  $("#panel-explain").innerHTML = `<div class="pad muted"><span class="spin"></span> Analysing…</div>`;
  const res = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sql: editor.getValue(), explain: true }) });
  $("#panel-explain").innerHTML = `<div class="pad muted" style="padding-bottom:0">How the engine will execute this query:</div>` + renderGrid(res);
}

/* ---- check ---- */
async function checkAnswer() {
  if (!current) return;
  switchTab("feedback");
  $("#panel-feedback").innerHTML = `<div class="pad muted"><span class="spin"></span> Checking with Qwen…</div>`;
  const res = await api("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lesson_id: current.lesson.id, sql: editor.getValue() }) });
  const f = res.feedback;
  const label = { correct: "Correct", incorrect: "Not quite", error: "Query error" }[f.verdict] || "Reviewed";

  if (res.correct) { done[current.lesson.id] = true; localStorage.setItem("sql_done", JSON.stringify(done));
    document.querySelector(`.lesson-item[data-id="${current.lesson.id}"]`)?.classList.add("done"); }

  let h = `<div class="verdict ${f.verdict}"><span class="dot"></span>${label}${f.reviewed_by === "offline" ? ' <span class="badge off" style="font-size:10px">offline</span>' : ""}</div>`;
  h += `<div class="feedback-body">${marked.parse(f.feedback_md || "")}</div>`;
  if (f.suggestions?.length) h += `<ul class="sugg">${f.suggestions.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
  if (f.corrected_sql) h += `<div class="corrected"><div class="card-label">Suggested query</div><pre class="code">${esc(f.corrected_sql)}</pre><button class="insert-fix" data-sql="${esc(f.corrected_sql)}">↳ Load into editor</button></div>`;
  $("#panel-feedback").innerHTML = h;
  $("#panel-feedback").querySelector(".insert-fix")?.addEventListener("click", (e) => editor.setValue(e.target.dataset.sql));
  $("#output-meta").textContent = res.correct ? "passed ✓" : "";
}

boot();
