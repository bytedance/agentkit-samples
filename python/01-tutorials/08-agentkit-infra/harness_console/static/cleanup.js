"use strict";
// Shared by the page and offline tests. Mutations reuse the console's authenticated APIs.
const HarnessCleanup = (() => {
  const order = ["sessions", "templates", "stores", "resources", "keys", "environments", "harnesses", "endpoints"];
  const status = row => String(row.Status || row.status || "").toLowerCase();
  const environment = row => row.EnvironmentId || row.environment_id || row.Target?.EnvironmentId || "";
  async function all(api, kind, filters = {}, context = {}) {
    const rows = [], seen = new Set();
    let cursor = "";
    for (let i = 0; i < 500; i++) {
      const page = await api("list", {kind, filters, context, cursor});
      if (!Array.isArray(page.items)) throw new Error(`${kind} 列表格式不正确`);
      rows.push(...page.items);
      cursor = page.next_cursor;
      if (!cursor) return rows;
      if (seen.has(cursor)) throw new Error(`${kind} 分页游标循环`);
      seen.add(cursor);
    }
    throw new Error(`${kind} 超过 500 页，扫描未完成`);
  }
  async function scan(api, boot, progress = () => {}) {
    const inventory = {}, entries = [], warnings = [], unknown = new Set();
    for (const kind of order.filter(k => k !== "sessions")) {
      progress(`扫描 ${boot.catalog[kind].label}…`);
      inventory[kind] = await all(api, kind,
        ["harnesses", "environments"].includes(kind) ? {IncludeArchived: true} : {});
    }
    const local = new Set(boot.local_keys.map(k => k.id));
    const endpoints = new Set(inventory.endpoints.map(e => e.EndpointId));
    const envs = new Set([
      ...inventory.environments.filter(e => status(e) !== "deleted").map(environment),
      ...inventory.keys.map(environment),
    ].filter(Boolean));
    inventory.sessions = [];
    for (const env of envs) {
      progress(`扫描 ${env} 的 Sessions…`);
      const candidates = inventory.keys.filter(k => environment(k) === env && local.has(k.ApiKeyId) && endpoints.has(k.EndpointId));
      let failure = "缺少本地持有明文、且绑定有效 Endpoint 的 API Key";
      let found = false;
      for (const key of candidates) {
        const context = {key_id: key.ApiKeyId, endpoint_id: key.EndpointId};
        try {
          const sessions = await all(api, "sessions", {include_archived: true}, context);
          for (const row of sessions) inventory.sessions.push({...row, environment_id: row.environment_id || env, _cleanupContext: context});
          found = true;
          break;
        } catch (error) { failure = error.message; }
      }
      if (!found) {
        unknown.add(env);
        warnings.push(`${env}：Session 未扫描（${failure}）。请先导入可用密钥再扫描。`);
      }
    }
    const seen = new Set();
    for (const kind of order) for (const row of inventory[kind]) {
      const id = row[boot.catalog[kind].id];
      if (!id) throw new Error(`${kind} 返回了缺少 ID 的资源，扫描已停止`);
      const key = `${kind}:${kind === "sessions" ? environment(row) + ":" : ""}${id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      let blocked = "";
      if (status(row) === "deleted") blocked = "已删除";
      else if (kind === "harnesses" && status(row) === "archived") blocked = "已归档，当前接口不支持永久删除";
      else if (kind !== "harnesses" && !boot.catalog[kind].delete) blocked = "未配置删除接口";
      else if (unknown.size && (
        ["templates", "stores", "harnesses", "endpoints"].includes(kind) ||
        unknown.has(environment(row)) ||
        (kind === "resources" && !environment(row))
      )) blocked = "存在未扫描的 Session，补齐环境密钥后再清理";
      entries.push({key, kind, id, row, context: row._cleanupContext || {}, blocked,
        action: kind === "harnesses" ? "archive" : "delete"});
    }
    return {entries, warnings};
  }
  function plan(entries, selected) {
    const chosen = entries.filter(e => selected.has(e.key));
    if (!chosen.length) throw new Error("请先勾选资源");
    for (const entry of chosen) {
      if (entry.blocked) throw new Error(`${entry.id}：${entry.blocked}`);
      const dependents = entries.filter(other => {
        if (other === entry || selected.has(other.key) || status(other.row) === "deleted") return false;
        const row = other.row;
        if (entry.kind === "environments") return ["sessions", "resources", "keys"].includes(other.kind) && environment(row) === entry.id;
        if (entry.kind === "resources") return other.kind === "sessions" && environment(row) === environment(entry.row);
        if (entry.kind === "templates") return other.kind === "sessions" && row.runtime_template_id === entry.id;
        if (entry.kind === "stores") return other.kind === "templates" && row.SessionStoreId === entry.id;
        if (entry.kind === "harnesses") return other.kind === "sessions" && (row.agent?.id || row.agent_id) === entry.id;
        if (entry.kind === "endpoints") return other.kind === "keys" && row.EndpointId === entry.id;
        if (entry.kind === "keys") return other.kind === "sessions" && other.context.key_id === entry.id;
        return false;
      });
      if (dependents.length) throw new Error(`${entry.id} 仍被未勾选资源引用：${dependents.map(e => e.id).join("、")}`);
    }
    return chosen.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  }
  async function run(api, entries, reason, update, stopped = () => false, options = {}) {
    const sleep = options.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
    const attempts = options.attempts || 120;
    for (const [index, entry] of entries.entries()) {
      if (stopped()) return {stopped: true, completed: index};
      const body = {kind: entry.kind, id: entry.id, context: entry.context};
      try {
        update(entry, "执行中", "正在检查当前状态");
        let current;
        try { current = await api("get", body); }
        catch (error) { if (error.status !== 404) throw error; }
        const done = value => !value || status(value) === "deleted" || (entry.action === "archive" && status(value) === "archived");
        if (!done(current)) {
          // Do not replay an in-flight deletion. Poll it instead.
          if (status(current) !== "deleting") {
            try { await api(entry.action, {...body, reason, token: crypto.randomUUID()}); }
            catch (error) { if (error.status !== 404) throw error; }
          }
          update(entry, "等待确认", "请求已受理，等待服务端完成");
          let completed = false;
          for (let n = 0; n < attempts; n++) {
            if (stopped()) return {stopped: true, completed: index};
            try { current = await api("get", body); }
            catch (error) { if (error.status !== 404) throw error; current = null; }
            if (done(current)) { completed = true; break; }
            if (["failed", "deletefailed", "error"].includes(status(current))) throw new Error(`服务端状态：${current.Status || current.status}`);
            await sleep(2000);
          }
          if (!completed) throw new Error("等待完成超时；操作可能仍在执行，请重新扫描后检查");
        }
        update(entry, "完成", entry.action === "archive" ? "已归档，历史版本保留" : "已确认删除");
      } catch (error) {
        update(entry, "失败 / 待核查", error.message);
        return {failed: true, completed: index};
      }
    }
    return {completed: entries.length};
  }
  return {scan, plan, run};
})();
if (typeof module !== "undefined") module.exports = HarnessCleanup;
