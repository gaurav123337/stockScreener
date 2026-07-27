/* stockScreener SPA — vanilla JS, hash-routed, PWA installable. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const view = $("#view");
  const toast = (msg, ms = 2600) => {
    const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), ms);
  };
  const api = async (path, opts) => {
    const r = await fetch(path, opts);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  };
  // HTML-escape using char codes only (no entity literals, so editors can't mangle it)
  const ESCMAP = {
    38: String.fromCharCode(38, 97, 109, 112, 59),      // & -> &
    60: String.fromCharCode(38, 108, 116, 59),          // < -> <
    62: String.fromCharCode(38, 103, 116, 59),          // > -> >
    34: String.fromCharCode(38, 113, 117, 111, 116, 59) // " -> "
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ESCMAP[c.charCodeAt(0)]);


  const fmt = (n, d = 2) => (n === null || n === undefined || n === "" || isNaN(n)) ? "-" : (+n).toFixed(d);
  const pct = (n) => (n === null || n === undefined) ? "-" : (n * 100).toFixed(0) + "%";

  // ---------- PWA install ----------
  let deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); deferredPrompt = e;
    $("#installBtn").classList.remove("hidden");
  });
  $("#installBtn").addEventListener("click", async () => {
    if (deferredPrompt) { deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt = null; }
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
    // When a new service worker takes over, reload once to get fresh code.
    let refreshing = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (refreshing) return; refreshing = true; location.reload();
    });
    navigator.serviceWorker.addEventListener("message", (e) => {
      if (e.data && e.data.type === "SW_UPDATED" && !refreshing) { refreshing = true; location.reload(); }
    });
  }

  // ---------- router ----------
  const tabs = ["recommend", "scan", "train", "brokers", "settings", "guide"];
  const go = (t) => { location.hash = "#/" + t; };
  window.addEventListener("hashchange", render);
  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => go(b.dataset.tab)));

  function activeTab() {
    const h = location.hash.replace("#/", "");
    return tabs.includes(h) ? h : "recommend";
  }
  function setActive() {
    document.querySelectorAll(".tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.tab === activeTab()));
  }

  // ---------- shared renderers ----------
  const recCard = (r) => {
    if (r.error) return `<div class="card"><div class="sym">${esc(r.symbol)}</div><div class="meta">Error: ${esc(r.error)}</div></div>`;
    const cls = r.action.toLowerCase();
    const rr = r.rr ? `R:R ${fmt(r.rr, 2)}` : "";
    const levels = (r.action === "BUY" || r.action === "SELL") ? `
      <div class="grid3">
        <div class="kv"><div class="k">Entry</div><div class="v">₹${fmt(r.entry)}</div></div>
        <div class="kv"><div class="k">Target</div><div class="v">₹${fmt(r.target)}</div></div>
        <div class="kv"><div class="k">Stop-loss</div><div class="v">₹${fmt(r.stop_loss)}</div></div>
      </div>` : "";
    return `
    <div class="card ${cls}">
      <div class="card-head">
        <div><div class="sym">${esc(r.symbol.replace(".NS", ""))}</div>
        <div class="name">${esc(r.name)} ${r.sector ? "· " + esc(r.sector) : ""}</div></div>
        <div class="badge ${r.action}">${r.action}</div>
      </div>
      <div class="score">Score ${r.score > 0 ? "+" : ""}${fmt(r.score, 0)} ${rr ? " · " + rr : ""}</div>
      <div class="price-line">LTP <b>₹${fmt(r.price)}</b></div>
      ${levels}
      <div class="meta">RSI ${fmt(r.rsi, 1)} · SMA50 ${fmt(r.sma50, 1)} · SMA200 ${fmt(r.sma200, 1)} · PE ${fmt(r.pe, 1)} · PEG ${fmt(r.peg, 2)} · ROE ${pct(r.roe)}</div>
      <ul class="reasons">${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    </div>`;
  };

  // ---------- Recommend ----------
  const Recommend = () => {
    view.innerHTML = `
      <div class="section"><div class="h">Recommend</div>
        <div class="sub">Buy/Sell/Hold with entry, target, stop-loss and reasons.</div></div>
      <div class="row">
        <input id="recSym" type="text" placeholder="Symbols e.g. RELIANCE TCS SBIN" autocomplete="off" />
      </div>
      <div style="height:10px"></div>
      <button id="recGo" class="btn">Get Recommendation</button>
      <div style="height:14px"></div>
      <div id="recOut"></div>`;
    const run = async () => {
      const raw = $("#recSym").value.trim();
      if (!raw) return toast("Enter at least one symbol");
      const syms = raw.split(/[\s,]+/).filter(Boolean);
      $("#recGo").disabled = true;
      $("#recOut").innerHTML = `<div class="center"><span class="spinner"></span> Analysing…</div>`;
      try {
        const cards = await Promise.all(syms.map((s) =>
          api("/api/recommend/" + encodeURIComponent(s)).catch((e) => ({ symbol: s, error: e.message }))));
        $("#recOut").innerHTML = cards.map(recCard).join("");
      } catch (e) { $("#recOut").innerHTML = ""; toast(e.message); }
      $("#recGo").disabled = false;
    };
    $("#recGo").addEventListener("click", run);
    $("#recSym").addEventListener("keydown", (e) => e.key === "Enter" && run());
  };

  // ---------- Scan ----------
  let FILTERS = null;
  const Scan = async () => {
    if (!FILTERS) { try { FILTERS = await api("/api/filters"); } catch (e) { FILTERS = { predefined: [] }; } }
    view.innerHTML = `
      <div class="section"><div class="h">Scan</div>
        <div class="sub">Screen Nifty 50 (or your list) with a filter, ranked by score.</div></div>
      <div class="ac-wrap">
        <input id="scanSearch" type="text" placeholder="🔍 Find a stock by name or symbol (e.g. Tata, HDFC, M&M)…" autocomplete="off" />
        <div id="scanAc" class="ac-list hidden"></div>
      </div>
      <div style="height:8px"></div>
      <input id="scanSyms" type="text" placeholder="Symbols (blank = Nifty 50) e.g. RELIANCE TCS" />
      <div class="chip-row" id="filterChips">
        <button class="chip active" data-f="">All</button>
        ${FILTERS.predefined.map((f) => `<button class="chip" data-f="${esc(f.name)}" title="${esc(f.desc)}">${esc(f.name)}</button>`).join("")}
      </div>
      <input id="scanWhere" type="text" placeholder='Custom filter e.g. rsi < 35 and roe > 0.15 (overrides chips)' />
      <div style="height:10px"></div>
      <div class="row">
        <input id="scanTop" type="text" placeholder="Top N (optional)" inputmode="numeric" style="flex:0 0 120px" />
        <button id="scanGo" class="btn">Run Scan</button>
      </div>
      <div style="height:14px"></div>
      <div id="scanOut"></div>`;
    let chosen = "";
    $("#filterChips").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      chosen = b.dataset.f;
      document.querySelectorAll("#filterChips .chip").forEach((c) => c.classList.toggle("active", c === b));
    });

    // --- stock search autocomplete ---
    const sInput = $("#scanSearch"), sList = $("#scanAc");
    let deb;
    const hideAc = () => sList.classList.add("hidden");
    const addSym = (sym) => {
      const cur = $("#scanSyms").value.trim();
      const toks = cur ? cur.split(/[\s,]+/).filter(Boolean) : [];
      if (!toks.map((t) => t.toUpperCase()).includes(sym.toUpperCase())) toks.push(sym);
      $("#scanSyms").value = toks.join(" ");
      sInput.value = ""; hideAc(); $("#scanSyms").focus();
    };
    sInput.addEventListener("input", () => {
      const q = sInput.value.trim();
      clearTimeout(deb);
      if (q.length < 2) { hideAc(); return; }
      deb = setTimeout(async () => {
        try {
          const r = await api("/api/search?q=" + encodeURIComponent(q));
          const res = r.results || [];
          if (!res.length) { sList.innerHTML = `<div class="ac-empty">No matches for "${esc(q)}"</div>`; sList.classList.remove("hidden"); return; }
          sList.innerHTML = res.map((x) => `
            <div class="ac-item" data-sym="${esc(x.symbol)}">
              <div><div class="ac-sym">${esc(x.symbol.replace(".NS","").replace(".BO",""))}</div>
              <div class="ac-name">${esc(x.name)}</div></div>
              <span class="ac-ex">${esc(x.exchange)}</span>
            </div>`).join("");
          sList.classList.remove("hidden");
          sList.querySelectorAll(".ac-item").forEach((it) =>
            it.addEventListener("click", () => addSym(it.dataset.sym)));
        } catch (e) { /* ignore */ }
      }, 220);
    });
    sInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); const f = sList.querySelector(".ac-item"); if (f) addSym(f.dataset.sym); }
      if (e.key === "Escape") hideAc();
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".ac-wrap")) hideAc(); });

    $("#scanGo").addEventListener("click", async () => {
      const syms = $("#scanSyms").value.trim().split(/[\s,]+/).filter(Boolean);
      const where = $("#scanWhere").value.trim() || null;
      const top = parseInt($("#scanTop").value) || null;
      $("#scanGo").disabled = true;
      $("#scanOut").innerHTML = `<div class="center"><span class="spinner"></span> Scanning… (live data, may take a bit)</div>`;
      try {
        const body = { symbols: syms.length ? syms : null, filter: where ? null : (chosen || null), where, top };
        const res = await api("/api/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (!res.results.length) { $("#scanOut").innerHTML = `<div class="center">No matches.</div>`; }
        else {
          $("#scanOut").innerHTML = `<div class="tblwrap"><table class="tbl">
            <thead><tr><th>Symbol</th><th>Action</th><th>Score</th><th>Price</th><th>Target</th><th>Stop</th><th>R:R</th><th>RSI</th><th>PE</th><th>ROE</th></tr></thead>
            <tbody>${res.results.map((r, i) => `
              <tr class="rowbtn" data-i="${i}">
                <td><span class="caret">▸</span> ${esc(r.symbol.replace(".NS", ""))}</td>
                <td class="t${r.action}">${r.action}</td>
                <td>${r.score > 0 ? "+" : ""}${fmt(r.score, 0)}</td>
                <td>${fmt(r.price, 1)}</td><td>${fmt(r.target, 1)}</td><td>${fmt(r.stop_loss, 1)}</td>
                <td>${r.rr ? fmt(r.rr, 2) : "-"}</td><td>${fmt(r.rsi, 0)}</td><td>${fmt(r.pe, 1)}</td><td>${pct(r.roe)}</td>
              </tr>
              <tr class="detail hidden" data-d="${i}"><td colspan="10">
                ${(r.reasons && r.reasons.length)
                  ? `<ul class="reasons">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
                  : `<div class="mini">No specific reasons — mixed/neutral signals.</div>`}
              </td></tr>`).join("")}</tbody></table></div>
            <div class="mini" style="margin-top:8px">${res.count} matched · ${res.failed.length} failed to fetch. Tap a row for reasons.</div>`;
          $("#scanOut").querySelectorAll("tr.rowbtn").forEach((tr) =>
            tr.addEventListener("click", () => {
              const d = $("#scanOut").querySelector(`tr.detail[data-d="${tr.dataset.i}"]`);
              if (d) { d.classList.toggle("hidden"); tr.classList.toggle("open"); }
            }));
        }

      } catch (e) { $("#scanOut").innerHTML = ""; toast(e.message); }
      $("#scanGo").disabled = false;
    });
  };

  // ---------- Train ----------
  const Train = () => {
    view.innerHTML = `
      <div class="section"><div class="h">Train</div>
        <div class="sub">Keep the screener updated — upload PDFs, notes/blogs, video transcripts, or paste a URL. It extracts market rules into its knowledge base.</div></div>

      <div class="card">
        <div class="sym" style="margin-bottom:8px">Upload a file</div>
        <div class="mini" style="margin-bottom:8px">PDF, .md, .txt, or video transcript (.txt/.srt/.vtt). For a video, upload its subtitle/transcript file.</div>
        <input id="trainFile" type="file" accept=".pdf,.md,.txt,.srt,.vtt" />
        <div style="height:10px"></div>
        <button id="trainFileGo" class="btn">Upload & Learn</button>
      </div>

      <div class="card">
        <div class="sym" style="margin-bottom:8px">Add a URL</div>
        <div class="mini" style="margin-bottom:8px">Blog post / article / research note (public link).</div>
        <input id="trainUrl" type="text" placeholder="https://example.com/article" inputmode="url" />
        <div style="height:10px"></div>
        <button id="trainUrlGo" class="btn secondary">Fetch & Learn</button>
      </div>

      <div class="card">
        <div class="sym" style="margin-bottom:8px">Knowledge base</div>
        <div class="mini" style="margin-bottom:8px">What the screener has learned so far (rules it follows).</div>
        <button id="kbGo" class="btn ghost">View knowledge base</button>
        <div id="kbOut" style="margin-top:10px"></div>
      </div>`;
    $("#trainFileGo").addEventListener("click", async () => {
      const f = $("#trainFile").files[0];
      if (!f) return toast("Choose a file first");
      const fd = new FormData(); fd.append("file", f);
      $("#trainFileGo").disabled = true; toast("Learning from " + f.name + "…");
      try { const r = await api("/api/learn/file", { method: "POST", body: fd });
        toast(r.ok === false ? (r.error || "failed") : `Learned ${r.rules_added} rules from ${r.saved_as}`);
      } catch (e) { toast(e.message); }
      $("#trainFileGo").disabled = false;
    });
    $("#trainUrlGo").addEventListener("click", async () => {
      const u = $("#trainUrl").value.trim(); if (!u) return toast("Paste a URL");
      $("#trainUrlGo").disabled = true; toast("Fetching & learning…");
      try { const r = await api("/api/learn/url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: u }) });
        toast(r.ok === false ? (r.error || "failed") : `Learned ${r.rules_added} rules`);
      } catch (e) { toast(e.message); }
      $("#trainUrlGo").disabled = false;
    });
    $("#kbGo").addEventListener("click", async () => {
      $("#kbOut").innerHTML = `<div class="center"><span class="spinner"></span></div>`;
      try { const r = await api("/api/knowledge");
        $("#kbOut").innerHTML = `<div class="card" style="white-space:pre-wrap;font-size:12px;max-height:320px;overflow:auto">${esc(r.content || "Empty")}</div>`;
      } catch (e) { $("#kbOut").innerHTML = ""; toast(e.message); }
    });
  };

  // ---------- Brokers ----------
  const Brokers = async () => {
    view.innerHTML = `<div class="center"><span class="spinner"></span> Loading…</div>`;
    let inst = {}, status = {};
    try { [inst, status] = await Promise.all([api("/api/brokers/instructions"), api("/api/brokers/status")]); }
    catch (e) { toast(e.message); }
    const block = (key) => {
      const b = inst[key] || { name: key, steps: [], fields: [] };
      const st = status[key] || {};
      const conn = st.connected;
      return `
      <div class="card">
        <div class="card-head"><div class="sym">${esc(b.name)}</div>
          <div class="badge ${conn ? "BUY" : "HOLD"}">${conn ? "Connected" : "Not connected"}</div></div>
        <div class="meta">Library: <code class="inline">${esc(b.library)}</code> ${st.library_installed ? "(installed)" : "(run in terminal)"}</div>
        <ol class="guide mini">${b.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        <div style="height:8px"></div>
        ${b.fields.map((f) => `<input id="${key}_${f}" type="text" placeholder="${esc(f)}" style="margin-bottom:8px" />`).join("")}
        <div class="row">
          <button class="btn" data-connect="${key}">Save & Connect</button>
          <button class="btn secondary" data-disconnect="${key}">Disconnect</button>
        </div>
      </div>`;
    };
    view.innerHTML = `
      <div class="section"><div class="h">Broker APIs</div>
        <div class="sub">Optional — connect Zerodha or Angel One for live LTP and your holdings. Works fine without them (uses free data).</div></div>
      ${block("zerodha")}
      ${block("angelone")}
      <div class="card"><div class="sym" style="margin-bottom:8px">My holdings / positions</div>
        <button id="holdGo" class="btn secondary">Fetch from connected broker</button>
        <div id="holdOut" style="margin-top:10px"></div></div>`;
    view.querySelectorAll("[data-connect]").forEach((btn) => btn.addEventListener("click", async () => {
      const key = btn.dataset.connect;
      const creds = {}; (inst[key].fields || []).forEach((f) => { creds[f] = $("#" + key + "_" + f).value.trim(); });
      if (!Object.values(creds).some(Boolean)) return toast("Enter credentials first");
      try { await api("/api/brokers/connect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ broker: key, credentials: creds }) });
        toast("Saved. Re-open Brokers tab to see status."); } catch (e) { toast(e.message); }
    }));
    view.querySelectorAll("[data-disconnect]").forEach((btn) => btn.addEventListener("click", async () => {
      try { await api("/api/brokers/disconnect/" + btn.dataset.disconnect, { method: "POST" }); toast("Disconnected"); Brokers(); } catch (e) { toast(e.message); }
    }));
    $("#holdGo").addEventListener("click", async () => {
      $("#holdOut").innerHTML = `<div class="center"><span class="spinner"></span></div>`;
      try { const r = await api("/api/brokers/holdings");
        $("#holdOut").innerHTML = `<div class="card" style="white-space:pre-wrap;font-size:12px;max-height:300px;overflow:auto">${esc(JSON.stringify(r, null, 2))}</div>`;
      } catch (e) { $("#holdOut").innerHTML = ""; toast(e.message); }
    });
  };

  // ---------- Settings ----------
  const SETMETA = [
    ["scoring", "Scoring & Signals", "How aggressively stocks are scored. Higher weights = that factor matters more."],
    ["risk", "Risk & Trade Levels", "Stop-loss / target calculation."],
    ["data", "Data Fetching", "History window and reliability for market data."],
    ["knowledge", "Knowledge Base", "How training documents are ingested."],
    ["verification", "Verification", "How prediction accuracy is measured."],
  ];
  const LABEL = {
    buy_threshold: "BUY score threshold", sell_threshold: "SELL score threshold",
    trend_weight_sma50: "Weight: above 50-DMA", trend_weight_sma200: "Weight: above 200-DMA",
    trend_weight_cross: "Weight: golden/death cross", momentum_weight_rsi: "Weight: RSI momentum",
    momentum_weight_macd: "Weight: MACD", momentum_weight_crossover: "Weight: MACD crossover",
    volume_weight: "Weight: volume surge", fundamental_peg_weight: "Weight: PEG valuation",
    fundamental_roe_weight: "Weight: ROE quality", fundamental_debt_weight: "Weight: low debt",
    atr_multiplier: "ATR stop-loss multiplier", risk_reward_target: "Target risk:reward",
    sma50_stop_discount: "50-DMA stop discount", default_period: "History period",
    default_interval: "Candle interval", retry_attempts: "Retry attempts",
    retry_pause_seconds: "Retry pause (sec)", max_workers: "Parallel fetch workers",
    max_rules_per_doc: "Max rules / document", min_rule_length: "Min rule length",
    max_rule_length: "Max rule length", allowed_extensions: "Allowed file types",
    horizon_days: "Verify after (days)", default_universe: "Default scan universe (symbols)",
  };
  const lbl = (k) => LABEL[k] || k.replace(/_/g, " ");

  const Settings = async () => {
    view.innerHTML = `<div class="center"><span class="spinner"></span> Loading settings…</div>`;
    let cur = {}, defs = {};
    try { [cur, defs] = await Promise.all([api("/api/settings"), api("/api/settings/defaults")]); }
    catch (e) { view.innerHTML = ""; return toast(e.message); }

    const numField = (sec, key, val) => `
      <div class="setrow">
        <div class="setlab">${esc(lbl(key))}<span class="setdef">default ${esc(defs[sec][key])}</span></div>
        <input class="setnum" type="number" step="any" data-sec="${sec}" data-key="${key}" value="${esc(val)}" />
      </div>`;
    const txtField = (sec, key, val) => `
      <div class="setrow">
        <div class="setlab">${esc(lbl(key))}<span class="setdef">default ${esc(defs[sec][key])}</span></div>
        <input class="setnum" type="text" data-sec="${sec}" data-key="${key}" value="${esc(val)}" />
      </div>`;

    const sectionHtml = (sec, title, sub) => {
      const body = Object.entries(cur[sec]).map(([k, v]) => {
        if (Array.isArray(v)) return ""; // handled separately
        return (typeof v === "number") ? numField(sec, k, v) : txtField(sec, k, v);
      }).join("");
      return `<div class="card"><div class="sym" style="margin-bottom:2px">${esc(title)}</div>
        <div class="mini" style="margin-bottom:10px">${esc(sub)}</div>${body}</div>`;
    };

    view.innerHTML = `
      <div class="section"><div class="h">Settings</div>
        <div class="sub">Tune how the screener behaves. Changes apply immediately and are saved. Use Reset to restore factory defaults.</div></div>
      ${SETMETA.map(([s, t, d]) => sectionHtml(s, t, d)).join("")}
      <div class="card">
        <div class="sym" style="margin-bottom:2px">${esc(lbl("default_universe"))}</div>
        <div class="mini" style="margin-bottom:8px">Stocks scanned when the Scan symbol box is left empty. Separate with spaces or commas.</div>
        <textarea id="setUniverse" rows="4">${esc(cur.default_universe.join(" "))}</textarea>
        <div class="mini" style="margin-top:6px">Default: ${defs.default_universe.length} Nifty-50 stocks</div>
      </div>
      <div class="row">
        <button id="setSave" class="btn">Save changes</button>
        <button id="setReset" class="btn secondary">Reset to default</button>
      </div>
      <div style="height:14px"></div>`;

    const collect = () => {
      const patch = {};
      view.querySelectorAll("input[data-sec]").forEach((inp) => {
        const sec = inp.dataset.sec, key = inp.dataset.key;
        let v = inp.value;
        if (inp.type === "number") { v = v === "" ? null : +v; if (v === null || isNaN(v)) return; }
        else if (key === "allowed_extensions") { v = v.split(/[\s,]+/).filter(Boolean); }
        (patch[sec] = patch[sec] || {})[key] = v;
      });
      const uni = $("#setUniverse").value.trim().split(/[\s,]+/).filter(Boolean).map((s) => s.toUpperCase());
      patch.default_universe = uni;
      return patch;
    };

    $("#setSave").addEventListener("click", async () => {
      $("#setSave").disabled = true;
      try { await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patch: collect() }) });
        toast("Settings saved"); Settings(); }
      catch (e) { toast(e.message); $("#setSave").disabled = false; }
    });
    $("#setReset").addEventListener("click", async () => {
      if (!confirm("Reset all settings to factory defaults?")) return;
      try { await api("/api/settings/reset", { method: "POST" }); toast("Reset to defaults"); Settings(); }
      catch (e) { toast(e.message); }
    });
  };

  // ---------- Guide ----------
  const Guide = () => {
    view.innerHTML = `
      <div class="section"><div class="h">Guide</div>
        <div class="sub">How to get the most out of the platform.</div></div>
      <div class="card"><div class="sym" style="margin-bottom:6px">What each signal means</div>
        <ol class="guide mini">
          <li><b>BUY</b> — uptrend + momentum + reasonable valuation. Enter near the shown entry, target and stop-loss. Risk:Reward shown.</li>
          <li><b>SELL</b> — downtrend / weakening momentum. Exit or avoid.</li>
          <li><b>HOLD</b> — mixed signals. Wait for confirmation.</li>
          <li>Always use the <b>stop-loss</b> and risk only 1-2% of capital per trade.</li>
        </ol></div>
      <div class="card"><div class="sym" style="margin-bottom:6px">Scanning & filters</div>
        <ol class="guide mini">
          <li>Use <b>Scan</b> → pick a pre-defined filter (e.g. <code class="inline">momentum</code>, <code class="inline">oversold</code>).</li>
          <li>Or type a custom filter like <code class="inline">rsi < 35 and roe > 0.15</code>.</li>
          <li>Fields: <code class="inline">score price rsi pe peg roe debt_to_equity sma50 sma200 above_sma50 above_sma200 golden_cross near_52w_high near_52w_low</code>.</li>
        </ol></div>
      <div class="card"><div class="sym" style="margin-bottom:6px">Keep it updated (Train)</div>
        <ol class="guide mini">
          <li>Drop research PDFs, notes, or video transcripts in <b>Train</b> to add their rules to the knowledge base.</li>
          <li>Paste URLs of good blogs/articles to ingest them.</li>
          <li>The screener logs every call and scores its own hit-rate after 30 days (see <code class="inline">data/predictions.csv</code> or CLI <code class="inline">python main.py verify</code>).</li>
        </ol></div>
      <div class="card"><div class="sym" style="margin-bottom:6px">Broker APIs</div>
        <ol class="guide mini">
          <li>Open <b>Brokers</b> → follow the steps for Zerodha Kite or Angel One SmartAPI.</li>
          <li>Connecting gives live LTP and pulls your holdings/positions.</li>
          <li>Zerodha tokens expire daily — re-login each morning.</li>
        </ol></div>
      <div class="card"><div class="sym" style="margin-bottom:6px">Install on mobile</div>
        <ol class="guide mini">
          <li>On Android (Chrome) tap <b>Install</b> at the top, or menu → Add to Home screen.</li>
          <li>On iPhone (Safari) tap Share → Add to Home Screen.</li>
          <li>Make sure your phone is on the same network as this server, or host it online (HTTPS) for install anywhere.</li>
        </ol></div>
      <div class="mini center" style="margin-top:14px">Educational tool — not SEBI-registered investment advice.</div>`;
  };

  // ---------- render ----------
  const views = { recommend: Recommend, scan: Scan, train: Train, brokers: Brokers, settings: Settings, guide: Guide };
  async function render() {
    setActive();
    view.scrollTo && window.scrollTo(0, 0);
    await views[activeTab()]();
  }
  if (!location.hash) location.hash = "#/recommend";
  render();
})();
