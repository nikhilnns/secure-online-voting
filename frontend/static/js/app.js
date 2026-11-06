/* SecureVote single-page client. No inline scripts (strict CSP); all user
   data is HTML-escaped before rendering to prevent XSS. */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const state = { token: null, user: null, elections: [] };

  // ---------- helpers ----------
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function store(key, value) {
    try {
      if (value === null) sessionStorage.removeItem(key);
      else sessionStorage.setItem(key, value);
    } catch (e) { /* storage unavailable: keep in memory only */ }
  }
  function load(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }

  let toastTimer = null;
  function toast(message, kind) {
    const el = $("#toast");
    el.textContent = message;
    el.className = "toast " + (kind || "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3500);
  }

  async function api(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (state.token) headers.Authorization = "Bearer " + state.token;
    const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    if (res.status === 401 && state.token) { logout(); }
    if (!res.ok) throw new Error(data.error || ("Request failed (" + res.status + ")"));
    return data;
  }

  function formData(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function fmtDate(iso) {
    if (!iso) return "-";
    return iso.replace("T", " ").slice(0, 19);
  }

  function openModal(html) {
    $("#modal-body").innerHTML = html;
    $("#modal").classList.remove("hidden");
  }
  function closeModal() { $("#modal").classList.add("hidden"); }

  // ---------- session ----------
  function setSession(token, user) {
    state.token = token; state.user = user;
    store("sv_token", token); store("sv_user", JSON.stringify(user));
    route();
  }
  function logout() {
    state.token = null; state.user = null;
    store("sv_token", null); store("sv_user", null);
    route();
  }

  function route() {
    $$(".view").forEach((v) => v.classList.add("hidden"));
    if (!state.user) {
      $("#userbox").classList.add("hidden");
      $("#auth-view").classList.remove("hidden");
      return;
    }
    $("#userbox").classList.remove("hidden");
    $("#user-name").textContent = state.user.full_name;
    $("#user-role").textContent = state.user.role;
    if (state.user.role === "admin") {
      $("#admin-view").classList.remove("hidden");
      loadAdmin();
    } else {
      $("#voter-view").classList.remove("hidden");
      loadVoter();
    }
  }

  // ---------- auth ----------
  $$(".auth-card .tab").forEach((tab) => tab.addEventListener("click", () => {
    $$(".auth-card .tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $("#login-form").classList.toggle("hidden", tab.dataset.tab !== "login");
    $("#register-form").classList.toggle("hidden", tab.dataset.tab !== "register");
  }));

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await api("POST", "/api/auth/login", formData(e.target));
      e.target.reset();
      setSession(data.token, data.user);
      toast("Welcome, " + data.user.full_name, "success");
    } catch (err) { toast(err.message, "error"); }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await api("POST", "/api/auth/register", formData(e.target));
      e.target.reset();
      toast(data.message, "success");
      $$(".auth-card .tab")[0].click();
    } catch (err) { toast(err.message, "error"); }
  });

  $("#logout-btn").addEventListener("click", logout);
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

  // ---------- voter ----------
  async function loadVoter() {
    try {
      const me = await api("GET", "/api/auth/me");
      state.user = me.user; store("sv_user", JSON.stringify(me.user));
      const banner = $("#voter-banner");
      if (me.user.status !== "approved") {
        banner.textContent = "Your registration is " + me.user.status +
          ". You can vote once an administrator approves your account.";
        banner.classList.remove("hidden");
      } else { banner.classList.add("hidden"); }
      const data = await api("GET", "/api/elections");
      state.elections = data.elections;
      renderVoterElections();
    } catch (err) { toast(err.message, "error"); }
  }

  function renderVoterElections() {
    const list = state.elections;
    const approved = state.user.status === "approved";
    $("#voter-elections").innerHTML = list.length ? list.map((el) => {
      let action = "";
      if (el.status === "open" && el.has_voted) action = '<span class="pill approved">&#10003; You voted</span>';
      else if (el.status === "open") action = '<button class="btn btn-primary" data-action="vote" data-id="' + el.id + '"' + (approved ? "" : " disabled") + ">Cast vote</button>";
      else action = '<button class="btn btn-light" data-action="results" data-id="' + el.id + '">View results</button>';
      return '<div class="card election-card"><div class="row-between"><h3>' + esc(el.title) +
        '</h3><span class="pill ' + el.status + '">' + el.status + "</span></div><p>" + esc(el.description) +
        "</p><p>" + el.candidates.length + " candidates</p><div>" + action + "</div></div>";
    }).join("") : '<div class="card">No elections are available yet.</div>';
    $("#verify-election").innerHTML = list.map((el) =>
      '<option value="' + el.id + '">' + esc(el.title) + "</option>").join("");
  }

  $("#voter-elections").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.action === "vote") showBallot(id);
    if (btn.dataset.action === "results") showResults(id);
  });

  function showBallot(id) {
    const el = state.elections.find((x) => x.id === id);
    openModal("<h3>" + esc(el.title) + '</h3><p class="hint">Select exactly one candidate. Your choice is stored anonymously and cannot be changed.</p>' +
      '<form id="ballot-form" class="form">' + el.candidates.map((c) =>
        '<label class="candidate-option"><input type="radio" name="candidate_id" value="' + c.id + '" required><div><b>' +
        esc(c.name) + "</b><small>" + esc(c.affiliation) + "</small><small>" + esc(c.manifesto) + "</small></div></label>").join("") +
      '<button class="btn btn-primary" type="submit">Submit ballot</button></form>');
    $("#ballot-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const candidateId = Number(formData(e.target).candidate_id);
      const name = el.candidates.find((c) => c.id === candidateId).name;
      if (!window.confirm("Confirm your vote for " + name + "? This cannot be undone.")) return;
      try {
        const res = await api("POST", "/api/votes", { election_id: id, candidate_id: candidateId });
        openModal('<h3>&#9989; Vote recorded</h3><p>Save this receipt code. It is shown only once and lets you verify your ballot is in the ledger (it does not reveal your choice).</p><div class="receipt">' +
          esc(res.receipt) + "</div>");
        loadVoter();
      } catch (err) { toast(err.message, "error"); }
    });
  }

  async function showResults(id) {
    try {
      const r = await api("GET", "/api/elections/" + id + "/results");
      const max = Math.max(1, ...r.results.map((x) => x.votes));
      openModal("<h3>" + esc(r.election.title) + "</h3><p>Total votes: <b>" + r.total_votes + "</b> &middot; Turnout: <b>" + r.turnout +
        "%</b> &middot; Status: <span class=\"pill " + r.election.status + "\">" + r.election.status + "</span></p>" +
        r.results.map((row) => '<div class="bar-row' + (r.winners.includes(row.name) ? " winner" : "") + '"><span>' + esc(row.name) +
          '</span><div class="bar"><span data-w="' + (row.votes * 100 / max) + '"></span></div><span>' + row.votes + " (" + row.percentage + "%)</span></div>").join("") +
        '<p class="result-ok">' + (r.winners.length ? (r.is_tie ? "Tie between: " : "Winner: ") + esc(r.winners.join(", ")) : "No votes cast") + "</p>");
      // Set widths through the CSSOM (inline style attributes are blocked by the CSP).
      $$("#modal-body .bar > span").forEach((s) => { s.style.width = s.dataset.w + "%"; });
    } catch (err) { toast(err.message, "error"); }
  }

  $("#verify-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = formData(e.target);
    try {
      const r = await api("POST", "/api/votes/verify", { election_id: Number(f.election_id), receipt: f.receipt });
      $("#verify-result").innerHTML = r.found
        ? '<p class="result-ok">&#10003; ' + esc(r.message) + " (ballot #" + r.sequence + ')</p><p class="mono">Ballot hash: ' + esc(r.ballot_hash) + "</p>"
        : '<p class="result-bad">&#10007; ' + esc(r.message) + "</p>";
    } catch (err) { toast(err.message, "error"); }
  });

  // ---------- admin ----------
  $$(".admin-tabs .tab").forEach((tab) => tab.addEventListener("click", () => {
    $$(".admin-tabs .tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $$(".admin-panel").forEach((p) => p.classList.add("hidden"));
    $("#admin-" + tab.dataset.adminTab).classList.remove("hidden");
    if (tab.dataset.adminTab === "voters") loadVoters();
    if (tab.dataset.adminTab === "audit") loadAudit();
  }));

  async function loadAdmin() {
    try {
      const s = await api("GET", "/api/admin/stats");
      const items = [["Total voters", s.total_voters], ["Approved", s.approved_voters], ["Pending", s.pending_voters],
        ["Elections", s.elections], ["Open now", s.open_elections], ["Ballots cast", s.ballots_cast]];
      $("#stats").innerHTML = items.map((i) => '<div class="stat"><b>' + i[1] + "</b><span>" + i[0] + "</span></div>").join("");
      const data = await api("GET", "/api/elections");
      state.elections = data.elections;
      renderAdminElections();
    } catch (err) { toast(err.message, "error"); }
  }

  function renderAdminElections() {
    $("#admin-election-list").innerHTML = state.elections.map((el) => {
      const id = el.id;
      let actions = "";
      if (el.status === "draft") {
        actions += '<button class="btn btn-light btn-sm" data-action="add-cand" data-id="' + id + '">+ Candidate</button>' +
          '<button class="btn btn-ok btn-sm" data-action="open" data-id="' + id + '">Open voting</button>' +
          '<button class="btn btn-bad btn-sm" data-action="delete" data-id="' + id + '">Delete</button>';
      } else {
        if (el.status === "open") actions += '<button class="btn btn-bad btn-sm" data-action="close" data-id="' + id + '">Close voting</button>';
        actions += '<button class="btn btn-light btn-sm" data-action="results" data-id="' + id + '">Results</button>' +
          '<button class="btn btn-light btn-sm" data-action="verify" data-id="' + id + '">Verify integrity</button>';
      }
      const cands = el.candidates.map((c) => "<li><b>" + esc(c.name) + "</b> &middot; " + esc(c.affiliation) +
        (el.status === "draft" ? ' <button class="btn btn-light btn-sm" data-action="rm-cand" data-id="' + id + '" data-cid="' + c.id + '">remove</button>' : "") + "</li>").join("");
      return '<div class="card"><div class="row-between"><h3>#' + id + " " + esc(el.title) + '</h3><span class="pill ' + el.status + '">' + el.status +
        "</span></div><p class=\"hint\">" + esc(el.description) + '</p><ul class="cand-list">' + (cands || "<li>No candidates yet</li>") +
        '</ul><div class="actions">' + actions + "</div></div>";
    }).join("") || '<div class="card">No elections yet. Create one above.</div>';
  }

  $("#election-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("POST", "/api/elections", formData(e.target));
      e.target.reset(); toast("Draft election created", "success"); loadAdmin();
    } catch (err) { toast(err.message, "error"); }
  });

  $("#admin-election-list").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    try {
      switch (btn.dataset.action) {
        case "open":
        case "close":
          if (!window.confirm((btn.dataset.action === "open" ? "Open" : "Close") + " this election? This cannot be reversed.")) return;
          await api("PATCH", "/api/elections/" + id + "/status", { status: btn.dataset.action === "open" ? "open" : "closed" });
          toast("Election updated", "success"); loadAdmin(); break;
        case "delete":
          if (!window.confirm("Delete this draft election?")) return;
          await api("DELETE", "/api/elections/" + id); loadAdmin(); break;
        case "rm-cand":
          await api("DELETE", "/api/elections/" + id + "/candidates/" + btn.dataset.cid); loadAdmin(); break;
        case "add-cand": showCandidateForm(id); break;
        case "results": showResults(id); break;
        case "verify": showIntegrity(id); break;
        default: break;
      }
    } catch (err) { toast(err.message, "error"); }
  });

  function showCandidateForm(id) {
    openModal('<h3>Add candidate</h3><form id="cand-form" class="form"><label>Name<input name="name" required maxlength="120"></label>' +
      '<label>Affiliation<input name="affiliation" maxlength="120" placeholder="Independent"></label>' +
      '<label>Manifesto<textarea name="manifesto" maxlength="500" rows="3"></textarea></label>' +
      '<button class="btn btn-primary" type="submit">Add</button></form>');
    $("#cand-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("POST", "/api/elections/" + id + "/candidates", formData(e.target));
        closeModal(); toast("Candidate added", "success"); loadAdmin();
      } catch (err) { toast(err.message, "error"); }
    });
  }

  async function showIntegrity(id) {
    try {
      const r = await api("GET", "/api/admin/elections/" + id + "/verify");
      openModal("<h3>Ledger integrity report</h3>" +
        '<table class="table"><tr><th>Ballots in ledger</th><td>' + r.ballots + "</td></tr><tr><th>Participation records</th><td>" + r.vote_records +
        "</td></tr><tr><th>Counts match</th><td>" + (r.counts_match ? "Yes" : "NO") + "</td></tr><tr><th>Hash chain</th><td>" +
        (r.chain_valid ? "Valid" : "BROKEN at ballot #" + r.broken_at + " (" + esc(r.reason) + ")") + '</td></tr><tr><th>Head hash</th><td class="mono">' +
        esc(r.head_hash || "-") + "</td></tr></table>" + (r.valid ? '<p class="result-ok">&#10003; No tampering detected.</p>' : '<p class="result-bad">&#9888; Integrity check FAILED.</p>'));
    } catch (err) { toast(err.message, "error"); }
  }

  async function loadVoters() {
    try {
      const status = $("#voter-filter").value;
      const data = await api("GET", "/api/admin/voters" + (status ? "?status=" + status : ""));
      $("#voter-rows").innerHTML = data.voters.map((v) => "<tr><td>" + esc(v.full_name) + "</td><td>" + esc(v.voter_id) + "</td><td>" + esc(v.email) +
        '</td><td><span class="pill ' + v.status + '">' + v.status + '</span></td><td class="actions">' +
        (v.status !== "approved" ? '<button class="btn btn-ok btn-sm" data-vid="' + v.id + '" data-decision="approved">Approve</button>' : "") +
        (v.status !== "rejected" ? '<button class="btn btn-bad btn-sm" data-vid="' + v.id + '" data-decision="rejected">Reject</button>' : "") +
        "</td></tr>").join("") || '<tr><td colspan="5">No voters in this list.</td></tr>';
    } catch (err) { toast(err.message, "error"); }
  }
  $("#voter-filter").addEventListener("change", loadVoters);
  $("#voter-rows").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-vid]");
    if (!btn) return;
    try {
      await api("PATCH", "/api/admin/voters/" + btn.dataset.vid, { status: btn.dataset.decision });
      toast("Voter " + btn.dataset.decision, "success"); loadVoters(); loadAdmin();
    } catch (err) { toast(err.message, "error"); }
  });

  async function loadAudit() {
    try {
      const data = await api("GET", "/api/admin/audit-logs?limit=100");
      $("#audit-rows").innerHTML = data.logs.map((l) => "<tr><td>" + l.id + "</td><td>" + fmtDate(l.created_at) + "</td><td>" + (l.actor_id || "-") +
        "</td><td><b>" + esc(l.action) + "</b></td><td>" + esc(l.details) + "</td><td>" + esc(l.ip_address) + "</td></tr>").join("");
    } catch (err) { toast(err.message, "error"); }
  }

  // ---------- boot ----------
  state.token = load("sv_token");
  try { state.user = JSON.parse(load("sv_user") || "null"); } catch (e) { state.user = null; }
  if (!state.token) state.user = null;
  route();
})();
