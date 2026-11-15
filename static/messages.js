// messages.js: simulated incoming text messages for the live demo.
//
//   Ctrl+J (or J)  → text from an unknown number pretending to be Alice (the scammer)
//   Ctrl+K (or K)  → text from the real Alice (saved contact)
//   Ctrl+N (or N)  → clear all messages
//   Click a banner → open it large, with a Copy address button. Esc closes.
//
// Plain J/K/N only fire when you're not typing in a field. Ctrl+ versions work anywhere.
// These messages are simulated, like the wallet history; nothing here talks to a server.

(function () {
  const cfg = window.DEMO_MSGS || {};
  const stack = document.getElementById("msg-stack");
  const overlay = document.getElementById("msg-overlay");

  const MESSAGES = {
    j: {
      from: "+1 (971) 555-0182",
      known: false,
      text: "hey it's Alice! lost my phone so this is my new number 😅 also had to make a new wallet. can you send the 2 MON here instead?",
      address: cfg.attacker,
    },
    k: {
      from: "Alice",
      known: true,
      text: "got a new wallet 🎉 here's my new address, use this one from now on!",
      address: cfg.alice_new,
    },
  };

  function avatar(m) {
    return m.known
      ? `<span class="msg-avatar known">${esc(m.from[0])}</span>`
      : `<span class="msg-avatar unknown">👤</span>`;
  }

  function show(key) {
    const m = MESSAGES[key];
    if (!m || !m.address) { toast("Demo address missing in .env"); return; }
    const el = document.createElement("button");
    el.className = "msg-banner";
    el.innerHTML = `
      <div class="msg-app"><span class="msg-icon">💬</span> MESSAGES <span class="msg-time">now</span></div>
      <div class="msg-body">
        ${avatar(m)}
        <div class="msg-text">
          <div class="msg-from">${esc(m.from)}</div>
          <div class="msg-preview">${esc(m.text)} ${esc(m.address)}</div>
        </div>
      </div>`;
    el.addEventListener("click", () => open(m));
    stack.prepend(el); // newest on top, like iOS
  }

  function open(m) {
    overlay.innerHTML = `
      <div class="msg-sheet" role="dialog" aria-label="Message from ${esc(m.from)}">
        <div class="msg-sheet-head">
          ${avatar(m)}
          <div class="msg-from big">${esc(m.from)}</div>
          ${m.known ? "" : `<div class="muted small">Not in your contacts</div>`}
        </div>
        <div class="bubble">
          ${esc(m.text)}
          <div class="mono bubble-addr">${esc(m.address)}</div>
        </div>
        <div class="row-btns center">
          <button class="btn primary" data-copy="${esc(m.address)}">Copy address</button>
          <button class="btn" id="msg-close">Close</button>
        </div>
      </div>`;
    overlay.hidden = false;
  }

  function close() { overlay.hidden = true; overlay.innerHTML = ""; }

  function clearAll() { close(); stack.innerHTML = ""; }

  // Click outside the sheet, the Close button, or Copy (after copying) closes it.
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || e.target.id === "msg-close") close();
    else if (e.target.closest("[data-copy]")) setTimeout(close, 400);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !overlay.hidden) { close(); return; }
    if (e.altKey || e.shiftKey) return;
    const key = e.key.toLowerCase();
    if (!["j", "k", "n"].includes(key)) return;

    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName);
    const modifier = e.ctrlKey || e.metaKey;
    if (typing && !modifier) return; // let plain letters type normally

    e.preventDefault();
    if (key === "n") clearAll(); else show(key);
  });
})();
