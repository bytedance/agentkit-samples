"use strict";
const cleanup = {entries: [], selected: new Set(), results: new Map(), warnings: [], busy: false, scanned: false, stop: false, pending: []};
function cleanupVisible() {
  const query = $("cleanup-search").value.trim().toLowerCase();
  return cleanup.entries.filter(e => `${state.boot.catalog[e.kind].label} ${e.id} ${e.row.Name || e.row.title || ""} ${e.row.Status || e.row.status || ""}`.toLowerCase().includes(query));
}
function renderCleanup() {
  $("cleanup-summary").textContent = `共 ${cleanup.entries.length} 项 · 已选 ${cleanup.selected.size} 项`;
  $("cleanup-review").disabled = cleanup.busy || !cleanup.scanned || !cleanup.selected.size;
  $("cleanup-scan").disabled = cleanup.busy;
  $("cleanup-select").disabled = $("cleanup-clear").disabled = cleanup.busy || !cleanup.scanned;
  $("cleanup-stop").hidden = !cleanup.busy;
  $("cleanup-warnings").hidden = !cleanup.warnings.length;
  $("cleanup-warnings").textContent = cleanup.warnings.join("\n");
  const fragment = document.createDocumentFragment();
  for (const entry of cleanupVisible()) {
    const tr = node("tr"), cell = node("td"), checkbox = node("input");
    checkbox.type = "checkbox";
    checkbox.setAttribute("aria-label", `选择 ${entry.id}`);
    checkbox.checked = cleanup.selected.has(entry.key);
    checkbox.disabled = cleanup.busy || !cleanup.scanned || Boolean(entry.blocked);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) cleanup.selected.add(entry.key); else cleanup.selected.delete(entry.key);
      renderCleanup();
    });
    cell.append(checkbox);
    const identity = node("td");
    identity.append(node("strong", entry.row.Name || entry.row.title || entry.id), node("small", `${state.boot.catalog[entry.kind].label} · ${entry.id}`));
    const related = node("td");
    related.append(node("span", entry.row.Status || entry.row.status || "—"), node("small", entry.row.EnvironmentId || entry.row.environment_id || entry.row.Target?.EnvironmentId || entry.row.SessionStoreId || ""));
    const result = cleanup.results.get(entry.key);
    const outcome = node("td", result ? `${result.status}：${result.message}` : entry.blocked || "待选择");
    tr.append(cell, identity, related, node("td", entry.action === "archive" ? "归档（保留历史）" : "删除"), outcome);
    fragment.append(tr);
  }
  $("cleanup-rows").replaceChildren(fragment);
}
$("cleanup-scan").addEventListener("click", async () => {
  if (cleanup.busy) return;
  cleanup.busy = true; cleanup.stop = false; cleanup.scanned = false;
  cleanup.selected.clear(); cleanup.results.clear(); cleanup.entries = []; cleanup.warnings = [];
  renderCleanup();
  $("cleanup-stop").hidden = true;
  try {
    const boot = await refreshBootstrap();
    if (boot.config_refresh_error) throw new Error(boot.config_refresh_error);
    const result = await HarnessCleanup.scan(api, boot, message => { $("cleanup-progress").textContent = message; });
    cleanup.entries = result.entries; cleanup.warnings = result.warnings; cleanup.scanned = true;
    $("cleanup-progress").textContent = `扫描完成 · ${new Date().toLocaleTimeString()}。请选择本次需要清理的资源。`;
  } catch (error) {
    $("cleanup-progress").textContent = `扫描未完成，已禁止执行：${error.message}`;
  } finally { cleanup.busy = false; renderCleanup(); }
});
$("cleanup-search").addEventListener("input", renderCleanup);
$("cleanup-select").addEventListener("click", () => {
  for (const e of cleanupVisible()) if (!e.blocked) cleanup.selected.add(e.key);
  renderCleanup();
});
$("cleanup-clear").addEventListener("click", () => { cleanup.selected.clear(); renderCleanup(); });
$("cleanup-review").addEventListener("click", () => {
  try {
    cleanup.pending = HarnessCleanup.plan(cleanup.entries, cleanup.selected);
    $("cleanup-preview").textContent = cleanup.pending.map((e, i) => `${i + 1}. ${e.action === "archive" ? "归档" : "删除"} ${state.boot.catalog[e.kind].label} · ${e.row.Name || e.row.title || ""}\n   ${e.id}`).join("\n");
    $("cleanup-phrase").textContent = `输入“清理 ${cleanup.pending.length} 项”确认`;
    $("cleanup-confirm-input").value = "";
    $("cleanup-confirm-error").textContent = "";
    $("cleanup-confirm").showModal();
  } catch (error) { $("cleanup-progress").textContent = error.message; }
});
$("cleanup-stop").addEventListener("click", () => {
  cleanup.stop = true;
  $("cleanup-progress").textContent = "已请求停止；正在进行的云端操作不会撤销。";
});
$("cleanup-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (cleanup.busy || !cleanup.scanned) return;
  const reason = $("cleanup-reason").value.trim();
  if ($("cleanup-confirm-input").value !== `清理 ${cleanup.pending.length} 项`) {
    $("cleanup-confirm-error").textContent = "确认文字不匹配"; return;
  }
  if (!reason || new TextEncoder().encode(reason).length > 1024) {
    $("cleanup-confirm-error").textContent = "请填写 1–1024 UTF-8 字节的清理原因"; return;
  }
  $("cleanup-confirm").close();
  cleanup.busy = true; cleanup.stop = false;
  for (const e of cleanup.pending) cleanup.results.set(e.key, {status: "等待执行", message: ""});
  renderCleanup();
  try {
    const result = await HarnessCleanup.run(api, cleanup.pending, reason, (entry, status, message) => {
      cleanup.results.set(entry.key, {status, message});
      $("cleanup-progress").textContent = `${entry.id} · ${status}`;
      renderCleanup();
    }, () => cleanup.stop);
    for (const e of cleanup.pending) {
      const result = cleanup.results.get(e.key);
      if (result.status === "等待执行") cleanup.results.set(e.key, {status: "未执行", message: "批次已停止"});
    }
    $("cleanup-progress").textContent = `${result.failed ? "遇到失败，已暂停" : result.stopped ? "已停止" : "本次清理完成"} · 已确认完成 ${result.completed}/${cleanup.pending.length} 项。再次清理前请重新扫描。`;
    state.cache = {}; quick.loaded = false;
  } catch (error) { $("cleanup-progress").textContent = `执行中断：${error.message}。请重新扫描核查。`; }
  finally { cleanup.busy = false; cleanup.scanned = false; renderCleanup(); }
});
window.addEventListener("beforeunload", event => {
  if (cleanup.busy) { event.preventDefault(); event.returnValue = ""; }
});
