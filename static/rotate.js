// rotate.js: "Alice's wallet". All signing happens in MetaMask; the server never sees a key.

let cfg, contract, me;
const $ = (id) => document.getElementById(id);
const CHAIN_HEX = "0x279f"; // 10143

function txBox(html, cls = "warn") {
  $("tx").innerHTML = `<div class="verdict ${cls}">${html}</div>`;
}

// Turn ethers/MetaMask errors into a short readable message.
function errMsg(e) {
  if (e?.code === "ACTION_REJECTED" || e?.code === 4001) return "You rejected the request in MetaMask.";
  return e?.reason || e?.shortMessage || e?.message || "Transaction failed.";
}

async function ensureMonad() {
  try {
    await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  } catch (e) {
    if (e.code !== 4902) throw e; // 4902 = chain not added to MetaMask yet
    await ethereum.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_HEX, chainName: "Monad Testnet",
        nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
        rpcUrls: ["https://testnet-rpc.monad.xyz"],
        blockExplorerUrls: [cfg.explorer],
      }],
    });
  }
}

async function refreshState() {
  const to = await contract.rotatedTo(me);
  if (to === ethers.ZeroAddress) {
    $("state").textContent = "no approved new address";
  } else {
    const at = Number(await contract.rotatedAt(me));
    $("state").textContent = `${to} (since ${new Date(at * 1000).toLocaleString()})`;
  }
}

async function connect() {
  if (!window.ethereum) { toast("MetaMask not found"); return; }
  try {
    await ethereum.request({ method: "eth_requestAccounts" });
    await ensureMonad();
    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    me = await signer.getAddress();
    contract = new ethers.Contract(cfg.registryAddress, cfg.abi, signer);

    $("me").textContent = me;
    $("wrong-account").hidden = !cfg.aliceOld || me.toLowerCase() === cfg.aliceOld.toLowerCase();
    $("connected").hidden = false;
    $("connect").textContent = "✓ Connected";
    await refreshState();
  } catch (e) {
    toast(errMsg(e));
  }
}

async function send(label, fn) {
  const buttons = [$("rotate"), $("revoke")];
  buttons.forEach(b => b.disabled = true);
  try {
    txBox(`<div class="v-title">⏳ Confirm in MetaMask…</div>`);
    const tx = await fn();
    const link = `${cfg.explorer}/tx/${tx.hash}`;
    txBox(`<div class="v-title">⏳ ${label}: pending on Monad…</div>
           <a class="mono small" href="${link}" target="_blank" rel="noopener">${tx.hash}</a>`);
    await tx.wait();
    txBox(`<div class="v-title">✅ ${label}: confirmed</div>
           <div class="row-btns"><a class="btn" href="${link}" target="_blank" rel="noopener">View transaction ↗</a></div>
           <div class="mono small muted">${tx.hash}</div>`, "ok");
    await refreshState();
  } catch (e) {
    txBox(`<div class="v-title">⚠️ ${esc(errMsg(e))}</div>`, "danger");
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

$("rotate").addEventListener("click", () => {
  const addr = $("new-addr").value.trim();
  if (!ethers.isAddress(addr)) { toast("Not a valid address"); return; }
  send("Approval", () => contract.rotate(addr));
});
$("revoke").addEventListener("click", () => send("Revoke", () => contract.revoke()));
$("connect").addEventListener("click", connect);

// Reconnect automatically when the user switches accounts in MetaMask.
if (window.ethereum) ethereum.on?.("accountsChanged", () => { if (contract) connect(); });

(async () => {
  cfg = await (await fetch("/api/config")).json();
  $("new-addr").value = cfg.aliceNew || "";
  if (!cfg.registryAddress || !cfg.abi.length) {
    $("not-deployed").hidden = false;
    $("connect").disabled = true;
    return;
  }
  $("registry-link").innerHTML =
    `Registry: <a class="mono" href="${cfg.explorer}/address/${cfg.registryAddress}" target="_blank" rel="noopener">${cfg.registryAddress}</a>`;
})();
