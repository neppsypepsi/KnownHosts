// dashboard.js: Send/Check panel. Calls POST /api/check and renders the verdict.

const form = document.getElementById("check-form");
const input = document.getElementById("address");
const select = document.getElementById("contact");
const result = document.getElementById("result");
const checkBtn = document.getElementById("check-btn");

document.getElementById("btn-send").addEventListener("click", () => {
  document.getElementById("send-card").scrollIntoView({ behavior: "smooth", block: "center" });
  input.focus();
});
document.getElementById("btn-receive").addEventListener("click", () => {
  const box = document.getElementById("receive-box");
  box.hidden = !box.hidden;
});

// Clear the old result as soon as the user edits the input, so a stale green never lingers.
input.addEventListener("input", () => { result.innerHTML = ""; });
select.addEventListener("change", () => { result.innerHTML = ""; });

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function fmtUnix(secs) {
  return new Date(secs * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// Two full addresses, one above the other, mismatched characters in red.
function diffBlock(diff, contactName) {
  const line = (key) => diff.map(d =>
    d.match ? esc(d[key]) : `<span class="bad">${esc(d[key])}</span>`).join("");
  return `
    <div class="diff">
      <div class="diff-label">${esc(contactName)} (trusted)</div>
      <div class="mono diff-line">${line("a")}</div>
      <div class="diff-label">Pasted address</div>
      <div class="mono diff-line">${line("b")}</div>
    </div>`;
}

const SSH_WARNING =
`@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@  WARNING: RECIPIENT IDENTIFICATION HAS CHANGED!  @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@`;

function render(r) {
  const c = r.contact;
  switch (r.verdict) {
    case "trusted":
      return `
        <div class="verdict ok">
          <div class="v-title">🟢 Trusted contact: ${esc(c.name)}</div>
          <p>This exact address is in your known hosts.
          ${c.first_trusted_at ? `First trusted ${fmtDate(c.first_trusted_at)}.` : ""}</p>
          <div class="mono addr-full">${esc(r.address)}</div>
        </div>`;

    case "rotation_verified":
      return `
        <div class="verdict ok">
          <div class="v-title">✅ Verified on Monad</div>
          <p>${esc(c.name)} approved this address from their known wallet
          (${fmtUnix(r.rotation.rotated_at)}). The approval is on-chain and only
          ${esc(c.name)}'s old key could have written it.</p>
          <div class="kv"><span>Old</span><span class="mono">${esc(c.address)}</span></div>
          <div class="kv"><span>New</span><span class="mono">${esc(r.rotation.new_address)}</span></div>
          <div class="row-btns">
            ${r.rotation.explorer_url ? `<a class="btn" href="${esc(r.rotation.explorer_url)}" target="_blank" rel="noopener">View registry on explorer ↗</a>` : ""}
            <button class="btn primary" id="update-contact" data-id="${esc(c.id)}">Update ${esc(c.name)}'s address</button>
          </div>
        </div>`;

    case "identity_changed":
      return `
        <div class="verdict danger">
          <pre class="ssh">${SSH_WARNING}</pre>
          <p class="v-big">This address was not approved by ${esc(c.name)}'s known wallet.</p>
          <p>If ${esc(c.name)} really changed wallets, they can approve the new address
          on-chain from their old wallet. Until then, <strong>do not send</strong>.</p>
          ${r.diff ? diffBlock(r.diff, c.name) : `
            <div class="kv"><span>Known</span><span class="mono">${esc(c.address)}</span></div>
            <div class="kv"><span>Pasted</span><span class="mono">${esc(r.address)}</span></div>`}
        </div>`;

    case "lookalike":
      return `
        <div class="verdict danger">
          <div class="v-title">🔴 Address poisoning detected</div>
          <p class="v-big">This address imitates <strong>${esc(c.name)}</strong>.</p>
          <p>The first and last characters match, so a wallet shows both as
          <span class="mono">${esc(c.address.slice(0, 6))}…${esc(c.address.slice(-4))}</span>.
          The middle is different. <strong>Do not send.</strong></p>
          ${diffBlock(r.diff, c.name)}
        </div>`;

    case "new":
      return `
        <div class="verdict warn">
          <div class="v-title">🟡 First time paying this address</div>
          <p>KnownHosts has never seen this address. If you verified it with the
          recipient another way, trust it to add it to your contacts.</p>
          <div class="mono addr-full">${esc(r.address)}</div>
          <form id="tofu-form" class="tofu">
            <input id="tofu-name" placeholder="Name, e.g. Sam" maxlength="60" required>
            <button class="btn primary" type="submit">Trust it</button>
          </form>
        </div>`;
  }
  return `<div class="verdict warn">${esc(r.message || "Unknown result")}</div>`;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const address = input.value.trim();
  checkBtn.disabled = true;
  checkBtn.textContent = "Checking…";
  result.innerHTML = "";
  try {
    const { ok, data } = await postJSON("/api/check", { address, contact_id: select.value });
    result.innerHTML = ok
      ? render(data)
      : `<div class="verdict warn"><div class="v-title">⚠️ ${esc(data.error || "Check failed")}</div></div>`;
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (_) {
    result.innerHTML = `<div class="verdict warn"><div class="v-title">⚠️ Network error. Do not send yet.</div></div>`;
  } finally {
    checkBtn.disabled = false;
    checkBtn.textContent = "⛨ Check with KnownHosts";
  }
});

// Buttons inside the result panel (rendered dynamically, so use delegation).
result.addEventListener("click", async (e) => {
  const btn = e.target.closest("#update-contact");
  if (!btn) return;
  btn.disabled = true;
  const { ok, data } = await postJSON(`/api/contacts/${btn.dataset.id}/address`);
  if (ok) {
    toast(`${data.name} updated to the verified address`);
    btn.textContent = "✓ Contact updated";
  } else {
    toast(data.error || "Update failed");
    btn.disabled = false;
  }
});

result.addEventListener("submit", async (e) => {
  if (e.target.id !== "tofu-form") return;
  e.preventDefault();
  const name = document.getElementById("tofu-name").value.trim();
  const { ok, data } = await postJSON("/api/contacts", { address: input.value.trim(), name });
  if (ok) {
    // Add to the Paying dropdown so it's usable immediately.
    select.add(new Option(data.name, data.id));
    result.innerHTML = `
      <div class="verdict ok">
        <div class="v-title">🟢 ${esc(data.name)} added to your known hosts</div>
        <p>Next time, KnownHosts will warn you if anything imitates this address.</p>
      </div>`;
  } else {
    toast(data.error || "Could not add contact");
  }
});
