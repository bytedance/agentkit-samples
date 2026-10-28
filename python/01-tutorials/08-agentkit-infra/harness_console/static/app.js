"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  boot: null,
  view: "quickstart",
  rows: [],
  cursor: "",
  filters: {},
  version: 0,
  cache: {},
  sessions: [],
  sessionCursor: "",
  selected: null,
  watch: 0,
  after: 0,
  turn: null,
  seen: new Set(),
  requestBusy: false,
};
const icons = {
  endpoints: "◈",
  harnesses: "⌘",
  templates: "▤",
  stores: "▥",
  environments: "⬡",
  keys: "⚿",
  resources: "▧",
  sessions: "▣",
  chat: "↗",
};
const descriptions = {
  endpoints: "管理账号的数据面访问入口。",
  harnesses: "定义 Harness 的模型、系统提示词与工具能力。",
  templates: "管理模型执行模板、会话存储绑定与计算资源。",
  stores: "管理 SERVERLESS_PG 会话存储；就绪后可绑定新 RuntimeTemplate。",
  environments: "管理 Sandbox 环境及其配置。",
  keys: "管理环境访问密钥与 Endpoint 绑定。",
  resources: "查看与管理环境的 Tool 和 Runtime 资源组。",
  sessions: "查看、创建和清理所选环境中的会话。",
  chat: "选择一个 Session，与 Harness 开始对话。",
};
const pretty = (obj) => JSON.stringify(obj, null, 2);
const statusFilters = {
  harnesses: { field: "Status", values: ["Active", "Archived"] },
  templates: {
    field: "Status",
    values: ["Building", "Ready", "Updating", "Failed", "Deleting"],
  },
  sessions: {
    field: "statuses",
    values: ["idle", "running", "rescheduling", "terminated"],
  },
};
function syncStatusFilter() {
  const spec = statusFilters[state.view];
  const select = $("status-filter");
  select.hidden = !spec;
  select.replaceChildren();
  if (!spec) return;
  for (const value of ["", ...spec.values]) {
    const option = node("option", value || "全部状态");
    option.value = value;
    select.append(option);
  }
  const value = state.filters[spec.field] || "";
  if (value && !spec.values.includes(value)) {
    const option = node("option", "自定义：" + value);
    option.value = value;
    select.append(option);
  }
  select.value = value;
}
const clone = (obj) => JSON.parse(JSON.stringify(obj));
const context = () => ({
  endpoint_id: $("endpoint-select").value,
  key_id: $("key-select").value,
});
const ready = () => Boolean(context().endpoint_id && context().key_id);
let toastTimer;
function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").className = error ? "error" : "";
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 7000);
}
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
let bootstrapRefresh = null;
async function refreshBootstrap() {
  if (!bootstrapRefresh) {
    bootstrapRefresh = (async () => {
      const response = await fetch("/api/bootstrap");
      if (!response.ok)
        throw new Error("无法读取本地配置，请确认 server 已启动");
      const boot = await response.json();
      state.boot = boot;
      return boot;
    })().finally(() => {
      bootstrapRefresh = null;
    });
  }
  return bootstrapRefresh;
}
async function api(path, body, retried = false) {
  const res = await fetch("/api/" + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Console-Token": state.boot.csrf,
    },
    body: JSON.stringify(body),
  });
  let payload;
  try {
    payload = await res.json();
  } catch {
    throw new Error("服务器返回了无法解析的响应，请检查服务是否仍在运行。");
  }
  // Only retry an explicit local rejection before dispatch; never retry an ambiguous cloud mutation.
  if (
    res.status === 403 &&
    payload.code === "ConsoleTokenExpired" &&
    !retried
  ) {
    await refreshBootstrap();
    return api(path, body, true);
  }
  if (!res.ok) {
    const error = new Error(payload.error || `请求失败 (${res.status})`);
    error.status = res.status;
    error.code = payload.code;
    throw error;
  }
  return payload;
}
async function busy(button, fn) {
  if (button.disabled) return;
  const oldChildren = [...button.childNodes];
  button.disabled = true;
  button.textContent = "处理中…";
  try {
    return await fn();
  } finally {
    button.disabled = false;
    if (button.textContent === "处理中…") button.replaceChildren(...oldChildren);
  }
}
function action(button, fn) {
  button.addEventListener("click", () =>
    busy(button, fn).catch((e) => toast(e.message, true)),
  );
}
function resourceId(item, kind = state.view) {
  return item[state.boot.catalog[kind].id] || "";
}
function statusBadge(status) {
  const lower = String(status || "").toLowerCase();
  const cls = /fail|error/.test(lower)
    ? "failed"
    : /pending|creat|delet|running|build|install/.test(lower)
      ? "pending"
      : /archiv|terminat|deleted/.test(lower)
        ? "neutral"
        : "";
  return node("span", status || "—", "badge " + cls);
}
function detail(title, value) {
  $("detail-title").textContent = title;
  $("detail-body").textContent = pretty(value);
  $("detail").showModal();
}
function notice(message, error = false) {
  $("resource-notice").textContent = message;
  $("resource-notice").className = "notice" + (error ? " error" : "");
  $("resource-notice").hidden = !message;
}
function renderNav() {
  const nav = $("nav");
  nav.replaceChildren();
  const views = ["quickstart", "harnesses", "sessions", "chat", "environments", "resources", "stores", "templates", "endpoints", "keys", "cleanup"];
  const groups = {quickstart: "Harness 平台", environments: "资源", endpoints: "连接与访问", cleanup: "维护"};
  for (const kind of views) {
    if (groups[kind]) nav.append(node("div", groups[kind], "nav-label"));
    const button = node("button");
    button.dataset.view = kind;
    button.append(
      node("span", kind === "cleanup" ? "♲" : kind === "quickstart" ? "♧" : icons[kind], "nav-icon"),
      node(
        "span",
        kind === "cleanup" ? "一键清理" : kind === "quickstart" ? "快速开始" : kind === "chat" ? "Session 聊天" : state.boot.catalog[kind].label,
      ),
    );
    button.addEventListener("click", () =>
      switchView(kind).catch((e) => toast(e.message, true)),
    );
    nav.append(button);
  }
}
async function switchView(kind) {
  if (cleanup.busy && kind !== "cleanup") throw new Error("清理操作进行中，请先停止再切换页面");
  $("cleanup-panel").hidden = kind !== "cleanup";
  document.querySelector(".heading-actions").hidden = kind === "cleanup";
  state.view = kind;
  document.body.classList.toggle("quickstart-view", kind === "quickstart");
  $("quickstart-panel").hidden = kind !== "quickstart";
  document.querySelector(".page-heading").hidden = kind === "quickstart";
  state.version++;
  state.rows = [];
  state.cursor = "";
  $("rows").replaceChildren();
  $("empty").hidden = true;
  $("count").textContent = "—";
  $("list-status").textContent = "等待查询…";
  state.filters =
    kind === "harnesses"
      ? { IncludeArchived: true }
      : kind === "sessions"
        ? { include_archived: true }
        : {};
  $("filters").value = pretty(state.filters);
  $("search").value = "";
  $("filter-count").textContent = Object.keys(state.filters).length || "";
  $("filter-panel").hidden = true;
  syncStatusFilter();
  state.watch++;
  state.turn = null;
  state.selected = null;
  state.requestBusy = false;
  updateComposer();
  if (kind === "cleanup") {
    document.querySelectorAll("#nav button").forEach(n => n.classList.toggle("active", n.dataset.view === kind));
    $("crumb").textContent = $("title").textContent = "一键清理资源";
    $("subtitle").textContent = "扫描当前账号与地域的资源，确认范围后按依赖顺序清理。";
    $("resource-panel").hidden = $("chat-panel").hidden = $("data-context").hidden = true;
    renderCleanup();
    return;
  }
  if (kind === "quickstart") {
    document.querySelectorAll("#nav button").forEach(n => n.classList.toggle("active", n.dataset.view === kind));
    $("crumb").textContent = "快速开始";
    $("resource-panel").hidden = true;
    $("chat-panel").hidden = true;
    $("data-context").hidden = true;
    renderQuickstart();
    return;
  }
  const chat = kind === "chat";
  document
    .querySelectorAll("#nav button")
    .forEach((n) => n.classList.toggle("active", n.dataset.view === kind));
  const label = chat ? "Session 聊天" : state.boot.catalog[kind].label;
  $("title").textContent = label;
  $("crumb").textContent = label;
  $("subtitle").textContent = descriptions[kind];
  $("create").textContent = chat ? "＋ 创建 Session" : "＋ 创建 " + label;
  $("resource-panel").hidden = chat;
  $("chat-panel").hidden = !chat;
  $("data-context").hidden = !(chat || kind === "sessions");
  $("type-label").textContent = label;
  $("scope-label").textContent =
    kind === "sessions" ? "所选 API Key 绑定环境" : "当前账号 / 当前地域";
  $("plane-label").textContent =
    kind === "sessions" ? "数据面 · REST" : "控制面 · TOP";
  if (!chat)
    $("filter-hint").textContent =
      "可用字段：" + (state.boot.catalog[kind].filters.join(", ") || "无");
  notice(
    kind === "endpoints"
      ? state.boot.endpoint_delete_note
      : kind === "stores"
        ? "创建后请刷新至 Ready。删除前应先清理引用它的 RuntimeTemplate；不会自动级联删除。"
      : kind === "harnesses"
        ? "默认包含已归档 Harness，可用状态筛选切换。归档后记录和历史版本保留，但不能创建新 Session；当前后端不提供永久删除接口。"
        : "",
  );
  if (chat || kind === "sessions") {
    try {
      await loadContext();
      if (ready()) {
        if (chat) await loadSessions();
        else await loadList();
      } else if (!chat) {
        renderRows();
        $("empty").hidden = true;
        $("count").textContent = "—";
        $("list-status").textContent =
          "尚未查询：请先选择 Endpoint 和可用的环境 API Key";
        notice(
          "请选择 Endpoint 和已在本地保存明文的环境 API Key，再连接数据面。",
        );
      }
    } catch (e) {
      $("context-note").textContent = "连接信息加载失败：" + e.message;
      if (!chat) {
        notice(e.message, true);
        $("list-status").textContent = "尚未查询：连接信息加载失败";
      }
      toast(e.message, true);
    }
  } else await loadList();
}
async function loadList(append = false) {
  const version = state.version,
    kind = state.view;
  if (kind === "chat") return loadSessions();
  if (kind === "sessions" && !ready())
    throw new Error("请先选择 Endpoint 和 API Key");
  $("list-status").textContent = "正在查询…";
  const cursor = append ? state.cursor : "";
  try {
    const data = await api("list", {
      kind,
      filters: state.filters,
      cursor,
      context: context(),
    });
    if (version !== state.version) return;
    if (!append) state.rows = [];
    const seen = new Set(state.rows.map((i) => resourceId(i, kind)));
    for (const item of data.items)
      if (!seen.has(resourceId(item, kind))) {
        state.rows.push(item);
        seen.add(resourceId(item, kind));
      }
    state.cursor = data.next_cursor;
    state.cache[kind] = state.rows;
    renderRows();
    $("list-status").textContent =
      `已加载 ${state.rows.length} 个资源 · ${state.cursor ? "还有更多资源" : "已到最后一页"}`;
  } catch (e) {
    if (version !== state.version) return;
    notice(e.message, true);
    $("list-status").textContent = "查询失败";
    throw e;
  }
}
function renderRows() {
  const tbody = $("rows");
  tbody.replaceChildren();
  const search = $("search").value.toLowerCase();
  const items = state.rows.filter((item) =>
    JSON.stringify(item).toLowerCase().includes(search),
  );
  $("count").textContent = state.rows.length;
  $("empty").hidden = items.length > 0;
  const filtered = search || state.filters[statusFilters[state.view]?.field];
  $("empty").querySelector("h3").textContent = filtered
    ? "没有符合条件的资源"
    : "当前查询范围内没有资源";
  $("empty").querySelector("p").textContent = filtered
    ? "请调整状态、搜索条件或其他筛选。"
    : "可以刷新列表，或创建一个新资源。";
  $("load-more").hidden = !state.cursor;
  $("load-all").hidden = !state.cursor;
  for (const item of items) {
    const kind = state.view,
      id = resourceId(item, kind),
      tr = node("tr"),
      name = node("td");
    name.append(
      node("strong", item.Name || item.title || item.Domain || id),
      node("small", id),
    );
    tr.append(name);
    const status = node("td");
    status.append(statusBadge(item.Status || item.status));
    tr.append(status);
    const relation = kind === "stores"
      ? [item.ProviderType, item.ProjectName].filter(Boolean).join(" · ") || "—"
      : item.EnvironmentId ||
      item.environment_id ||
      item.EndpointId ||
      item.AgentLoop ||
      item.SessionStoreId ||
      item.ProviderType ||
      item.RoleName ||
      item.BaseUrl ||
      item.runtime_template_id ||
      item.Description ||
      "—";
    tr.append(node("td", relation, "cell-info"));
    const date = item.CreatedAt || item.CreateTime || item.created_at;
    tr.append(
      node(
        "td",
        date ? new Date(date).toLocaleString("zh-CN", { hour12: false }) : "—",
        "cell-info",
      ),
    );
    const actions = node("td"),
      wrap = node("div", undefined, "row-actions"),
      get = node("button", "详情");
    action(get, async () =>
      detail(id, await api("get", { kind, id, context: context() })),
    );
    wrap.append(get);
    if (kind === "sessions") {
      const chat = node("button", "聊天");
      action(chat, async () => {
        await switchView("chat");
        await selectSession(item);
      });
      wrap.append(chat);
    }
    if (state.boot.catalog[kind].archive) {
      const archive = node("button", "归档");
      archive.disabled = item.Status === "Archived";
      archive.title = archive.disabled ? "该 Harness 已归档" : "";
      archive.addEventListener("click", () =>
        confirmDelete(kind, item, "archive"),
      );
      wrap.append(archive);
    }
    const del = node("button", "删除", "delete-link");
    del.disabled = !state.boot.catalog[kind].delete;
    del.title = del.disabled
      ? state.boot.catalog[kind].delete_unavailable_reason ||
        "需配置控制面 REST 网关才能删除 Endpoint"
      : "";
    del.addEventListener("click", () => confirmDelete(kind, item));
    wrap.append(del);
    actions.append(wrap);
    tr.append(actions);
    tbody.append(tr);
  }
}
async function fetchAll(kind) {
  let items = [],
    cursor = "",
    seen = new Set();
  for (let i = 0; i < 500; i++) {
    const page = await api("list", { kind, cursor });
    items.push(...page.items);
    cursor = page.next_cursor;
    if (!cursor) {
      state.cache[kind] = items;
      return items;
    }
    if (seen.has(cursor)) throw new Error("分页游标循环，查询已停止");
    seen.add(cursor);
  }
  throw new Error("数据超过 500 页，请使用资源页筛选");
}
function setOptions(select, items, idFn, labelFn, placeholder, current) {
  select.replaceChildren(node("option", placeholder));
  select.firstChild.value = "";
  for (const item of items) {
    const option = node("option", labelFn(item));
    option.value = idFn(item);
    select.append(option);
  }
  if (current && [...select.options].some((o) => o.value === current))
    select.value = current;
}
async function loadContext() {
  const old = context();
  $("context-note").textContent = "正在读取本地凭据和 Endpoint 绑定…";
  const boot = await refreshBootstrap();
  if (boot.config_refresh_error) throw new Error(boot.config_refresh_error);
  const [endpoints] = await Promise.all([
    fetchAll("endpoints"),
    fetchAll("keys"),
  ]);
  setOptions(
    $("endpoint-select"),
    endpoints,
    (x) => x.EndpointId,
    (x) => `${x.Domain || x.EndpointId} · ${x.EndpointId}`,
    "选择 Endpoint",
    old.endpoint_id,
  );
  if (!$("endpoint-select").value && endpoints.length === 1)
    $("endpoint-select").value = endpoints[0].EndpointId;
  updateKeyOptions(old.key_id);
  const current = context();
  if (old.endpoint_id !== current.endpoint_id || old.key_id !== current.key_id)
    resetContext();
}
function updateKeyOptions(preferred = "") {
  const endpoint = $("endpoint-select").value;
  const local = new Set(state.boot.local_keys.map((k) => k.id));
  const keys = (state.cache.keys || []).filter(
    (k) => k.EndpointId === endpoint && local.has(k.ApiKeyId),
  );
  setOptions(
    $("key-select"),
    keys,
    (x) => x.ApiKeyId,
    (x) => `${x.Name || x.ApiKeyId} · ${x.EnvironmentId}`,
    "选择已保存的 API Key",
    preferred,
  );
  if (!$("key-select").value && keys.length === 1)
    $("key-select").value = keys[0].ApiKeyId;
  const key = (state.cache.keys || []).find(
    (k) => k.ApiKeyId === $("key-select").value,
  );
  $("context-note").textContent = key
    ? `Environment: ${key.EnvironmentId} · Key: ${key.ApiKeyId}`
    : "仅显示本机持有明文且绑定所选 Endpoint 的密钥。可创建新 Key 或导入已有 Key。";
}
function resetContext() {
  state.watch++;
  state.selected = null;
  state.turn = null;
  state.requestBusy = false;
  state.sessions = [];
  state.sessionCursor = "";
  state.rows = [];
  state.cursor = "";
  state.version++;
  $("messages").replaceChildren();
  $("chat-title").textContent = "选择一个 Session";
  $("chat-id").textContent = "";
  $("chat-status").textContent = "连接已变更，请点击「连接 / 刷新」";
  renderSessionList();
  updateComposer();
  if (state.view === "sessions") renderRows();
}
const fieldSpecs = {
  endpoints: [
    ["CustomDomain", "自定义域名（可选）"],
    ["UserId", "业务用户标识（可选）"],
  ],
  harnesses: [
    ["Name", "名称"],
    ["Model.Id", "模型 ID"],
    ["Model.BaseUrl", "模型 Base URL"],
    ["AgentLoop", "Agent Loop", "loop"],
    ["System", "系统提示词", "textarea"],
  ],
  stores: [
    ["Name", "名称（最多 48 字符）"],
    ["ProjectName", "项目名称"],
    ["Description", "描述"],
  ],
  templates: [
    ["Name", "名称"],
    ["SessionStoreId", "SessionStore", "stores"],
    ["RoleName", "执行角色"],
    ["Resources.CpuMilli", "CPU（毫核）", "number"],
    ["Resources.MemoryMiB", "内存（MiB）", "number"],
    ["Resources.MinReplicas", "最小副本数", "number"],
    ["Resources.MaxReplicas", "最大副本数", "number"],
  ],
  environments: [
    ["Name", "名称"],
    ["Config.Type", "环境类型", "environment-type"],
    ["Config.Resources.CpuMilli", "CPU（毫核）", "number"],
    ["Config.Resources.MemoryMb", "内存（MiB）", "number"],
  ],
  keys: [
    ["Name", "名称"],
    ["EnvironmentId", "Environment", "environments"],
    ["EndpointId", "Endpoint", "endpoints"],
  ],
  resources: [
    ["Name", "名称"],
    ["Target.Type", "目标类型"],
    ["Target.EnvironmentId", "Environment", "environments"],
  ],
  sessions: [
    ["title", "会话标题"],
    ["agent.id", "Harness", "harnesses"],
    ["environment_id", "Environment", "environments"],
    ["runtime_template_id", "RuntimeTemplate", "templates"],
  ],
};
function getPath(obj, path) {
  return path.split(".").reduce((o, k) => o?.[k], obj);
}
function setPath(obj, path, value) {
  const parts = path.split(".");
  const last = parts.pop();
  let current = obj;
  for (const part of parts) {
    if (!current[part] || typeof current[part] !== "object") current[part] = {};
    current = current[part];
  }
  current[last] = value;
}
let editing, createToken, lastCreateSignature;
async function openEditor(kind) {
  editing = kind || (state.view === "chat" ? "sessions" : state.view);
  createToken = crypto.randomUUID();
  lastCreateSignature = "";
  $("editor-title").textContent = "创建 " + state.boot.catalog[editing].label;
  $("editor-hint").textContent =
    editing === "sessions"
      ? "使用当前选中的 Endpoint 与环境密钥。Harness 和 RuntimeTemplate 应处于可用状态。"
      : editing === "stores"
        ? "创建托管 SERVERLESS_PG。网络按 config.yaml 预填；私网 VpcConfig 需 VpcId 和恰好一个 SubnetIds。可在完整 JSON 编辑。创建后刷新至 Ready；请求超时请先查列表，避免重复创建。"
      : editing === "endpoints"
        ? "创建账号的数据面访问入口。请求超时后请先刷新列表，确认是否已创建。"
        : editing === "templates" || editing === "environments"
          ? "默认参数来自 config.yaml。配置中的环境变量由服务端保留；在 JSON 中显式传入空对象可清空。"
          : "填写基础参数；展开完整 JSON 可调整其余配置。";
  $("editor-error").textContent = "";
  const preset = clone(state.boot.presets[editing]);
  if (preset.Name) preset.Name += "-" + Date.now().toString(36).slice(-5);
  const dependencies = [
    ...new Set(
      fieldSpecs[editing].map((f) => f[2]).filter((k) => state.boot.catalog[k]),
    ),
  ];
  await Promise.all(dependencies.map(fetchAll));
  if (editing === "keys")
    preset.EndpointId = context().endpoint_id || preset.EndpointId;
  if (editing === "sessions") {
    if (!ready()) throw new Error("请先连接数据面");
    const key = state.cache.keys.find((k) => k.ApiKeyId === context().key_id);
    preset.environment_id = key?.EnvironmentId || "";
  }
  if (state.view === "quickstart") {
    if (editing === "templates") preset.SessionStoreId = quick.ids.stores || "";
    if (editing === "keys") {
      preset.EndpointId = quick.ids.endpoints || "";
      preset.EnvironmentId = quick.ids.environments || "";
    }
    if (editing === "sessions") {
      preset.agent.id = quick.ids.harnesses;
      preset.environment_id = quick.ids.environments;
      preset.runtime_template_id = quick.ids.templates;
    }
  }
  const fields = $("editor-fields");
  fields.replaceChildren();
  for (const [path, label, type] of fieldSpecs[editing]) {
    const wrapper = node("label", label),
      input = node(
        type === "textarea"
          ? "textarea"
          : type === "loop" || type === "environment-type" || state.boot.catalog[type]
            ? "select"
            : "input",
      );
    input.dataset.path = path;
    input.dataset.type = type || "text";
    if (type === "number") {
      input.type = "number";
      input.min = "0";
    }
    if (type === "textarea") {
      input.rows = 3;
      wrapper.className = "wide";
    }
    if (type === "loop" || type === "environment-type")
      for (const value of type === "loop" ? ["adk", "codex", "piagent"] : ["Cloud", "SelfHosted"]) {
        const option = node("option", value);
        option.value = value;
        input.append(option);
      }
    else if (state.boot.catalog[type]) {
      let items = state.cache[type] || [];
      if (type === "stores")
        items = items.filter(x => x.Status === "Ready" && x.ProviderType === "SERVERLESS_PG");
      if (type === "templates")
        items = items.filter((x) => x.Status === "Ready");
      if (type === "harnesses")
        items = items.filter((x) => x.Status === "Active");
      setOptions(
        input,
        items,
        (x) => resourceId(x, type),
        (x) =>
          `${x.Name || x.Domain || resourceId(x, type)} · ${resourceId(x, type)}`,
        "请选择",
      );
    }
    input.value = getPath(preset, path) ?? "";
    if (path === "SessionStoreId") input.required = true;
    wrapper.append(input);
    fields.append(wrapper);
  }
  if (editing === "sessions") {
    const label = node("label", "方舟模型 API Key Name");
    const input = node("input");
    input.id = "model-key-name";
    input.value = state.boot.model_key_name;
    label.append(input);
    fields.append(label);
  }
  $("json-body").value = pretty(preset);
  $("advanced").open = false;
  fields.querySelectorAll("[data-path]").forEach((input) =>
    input.addEventListener("input", () => {
      try {
        const obj = JSON.parse($("json-body").value);
        setPath(
          obj,
          input.dataset.path,
          input.dataset.type === "number" ? Number(input.value) : input.value,
        );
        $("json-body").value = pretty(obj);
        $("editor-error").textContent = "";
      } catch {
        $("editor-error").textContent = "请先修正 JSON 格式，再编辑基础字段";
      }
    }),
  );
  $("editor").showModal();
}
$("json-body").addEventListener("input", () => {
  try {
    const obj = JSON.parse($("json-body").value);
    $("editor-fields")
      .querySelectorAll("[data-path]")
      .forEach(
        (input) => (input.value = getPath(obj, input.dataset.path) ?? ""),
      );
  } catch {
    /* Keep incomplete JSON editable. */
  }
});
$("editor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await busy($("submit-create"), async () => {
    try {
      const body = JSON.parse($("json-body").value),
        model = $("model-key-name")?.value || "",
        signature = pretty({ body, model, context: context() });
      if (lastCreateSignature && signature !== lastCreateSignature)
        createToken = crypto.randomUUID();
      lastCreateSignature = signature;
      const result = await api("create", {
        kind: editing,
        body,
        context: context(),
        model_key_name: model,
        token: createToken,
      });
      $("editor").close();
      toast(
        editing === "keys"
          ? result.local_key_available
            ? "API Key 已创建，明文已保存到本机"
            : "API Key 已创建，但本机没有明文（可能为幂等重放）。请导入明文或创建新 Key。"
          : "创建请求成功，请刷新确认资源状态",
      );
      if (state.view === "quickstart") {
        const id = result[state.boot.catalog[editing].id];
        if (editing === "sessions" && id) {
          await switchView("chat");
          await selectSession(result);
        } else {
          if (id) quick.ids[editing] = id;
          await loadQuickResources();
          renderQuickstart();
          detail("创建结果", result);
        }
        return;
      }
      detail("创建结果", result);
      if (editing === "keys") await loadContext();
      if (state.view === "chat") await loadSessions();
      else await loadList();
    } catch (error) {
      $("editor-error").textContent = error.message;
    }
  });
});
let deleting;
function confirmDelete(kind, item, operation = "delete") {
  deleting = {
    operation,
    kind,
    id: resourceId(item, kind),
    context: context(),
    token: crypto.randomUUID(),
  };
  const label = operation === "archive" ? "归档" : "删除";
  $("confirm-title").textContent = label + " " + state.boot.catalog[kind].label;
  $("confirm-delete").textContent = "确认" + label;
  $("confirm-text").textContent =
    `${item.Name || item.title || deleting.id} (${deleting.id})。` +
    (operation === "archive"
      ? "此操作调用 ArchiveHarness，归档后不能创建新 Session，历史版本保留。"
      : kind === "sessions"
        ? "会先归档停止活动工作，再提交异步删除。"
        : kind === "keys"
          ? "撤销后使用该密钥的数据面访问将失效。"
          : "此操作会影响引用该资源的工作负载。");
  $("confirm-id").value = "";
  const needsReason = kind === "templates" && operation === "delete";
  $("delete-reason-field").hidden = !needsReason;
  $("delete-reason").required = needsReason;
  $("delete-reason").value = "";
  $("delete-error").textContent = "";
  $("confirm").showModal();
}
$("confirm-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("confirm-id").value !== deleting.id) {
    $("delete-error").textContent = "输入的资源 ID 不一致";
    return;
  }
  if (deleting.kind === "templates" && deleting.operation === "delete") {
    const reason = $("delete-reason").value.trim();
    if (!reason || new TextEncoder().encode(reason).length > 1024) {
      $("delete-error").textContent = "请填写删除原因（1–1024 UTF-8 字节）";
      return;
    }
    if (deleting.reason !== undefined && deleting.reason !== reason)
      deleting.token = crypto.randomUUID();
    deleting.reason = reason;
  }
  await busy($("confirm-delete"), async () => {
    try {
      const result = await api(deleting.operation, deleting);
      $("confirm").close();
      toast(result.message || "删除请求已受理，请刷新确认状态");
      await loadList();
    } catch (error) {
      $("delete-error").textContent = error.message;
    }
  });
});
async function loadSessions(append = false) {
  if (!ready()) throw new Error("请先选择 Endpoint 和 API Key");
  const version = state.version;
  const result = await api("list", {
    kind: "sessions",
    cursor: append ? state.sessionCursor : "",
    context: context(),
  });
  if (version !== state.version) return;
  state.sessions = append ? [...state.sessions, ...result.items] : result.items;
  state.sessionCursor = result.next_cursor;
  renderSessionList();
}
function renderSessionList() {
  const list = $("session-list");
  list.replaceChildren();
  const text = $("session-search").value.toLowerCase();
  for (const session of state.sessions.filter((s) =>
    (s.title + " " + s.id).toLowerCase().includes(text),
  )) {
    const button = node("button");
    button.classList.toggle("active", state.selected?.id === session.id);
    button.append(
      node("strong", session.title || session.id),
      node("small", `${session.status} · ${session.id}`),
    );
    action(button, () => selectSession(session));
    list.append(button);
  }
  if (!state.sessions.length)
    list.append(
      node("p", "连接后在此选择会话，或创建一个新的 Session。", "muted"),
    );
  $("session-more").hidden = !state.sessionCursor;
}
function updateComposer() {
  const disabled = !state.selected || !!state.turn || state.requestBusy;
  $("prompt").disabled = disabled;
  $("send").disabled = disabled;
  $("send").textContent = state.turn ? "等待回复…" : "发送 ↑";
  $("stop-watch").hidden = !state.turn;
}
function eventText(event) {
  if (typeof event.content === "string") return event.content;
  if (Array.isArray(event.content))
    return event.content
      .filter((b) => b.type === "text")
      .map((b) => b.text || "")
      .join("");
  return "";
}
function appendEvent(event) {
  const key = event.id || String(event.sequence);
  if (state.seen.has(key)) return;
  state.seen.add(key);
  const messages = $("messages"),
    nearBottom =
      messages.scrollHeight - messages.scrollTop - messages.clientHeight < 120;
  const type = event.type || "event";
  if (type === "user.message" || type === "agent.message") {
    const block = node(
      "div",
      undefined,
      "message " + (type === "user.message" ? "user" : "agent"),
    );
    block.append(
      node("div", type === "user.message" ? "你" : "HARNESS", "role"),
      node("div", eventText(event) || pretty(event.content), "content"),
    );
    messages.append(block);
  } else {
    const block = node("details", undefined, "event-item");
    block.append(
      node("summary", `${type} · #${event.sequence || ""}`),
      node("pre", pretty(event)),
    );
    messages.append(block);
  }
  if (nearBottom) messages.scrollTop = messages.scrollHeight;
}
async function selectSession(session) {
  state.watch++;
  const generation = state.watch;
  state.selected = session;
  state.turn = null;
  state.requestBusy = true;
  state.after = 0;
  state.seen = new Set();
  $("messages").replaceChildren();
  $("chat-title").textContent = session.title || "Session";
  $("chat-id").textContent = session.id;
  $("chat-status").textContent = "正在读取历史消息…";
  renderSessionList();
  updateComposer();
  try {
    const ctx = clone(context());
    for (let i = 0; i < 1000; i++) {
      const page = await api("events", {
        id: session.id,
        context: ctx,
        after: state.after,
      });
      if (generation !== state.watch) return;
      const previous = state.after;
      for (const event of page.data) {
        appendEvent(event);
        state.after = Math.max(state.after, Number(event.sequence) || 0);
      }
      if (!page.has_more) break;
      if (state.after <= previous)
        throw new Error("事件分页未前进，已停止读取");
      if (i === 999) throw new Error("历史事件超过本地读取上限");
    }
    $("chat-status").textContent = "历史已加载 · 可以发送问题";
    $("messages").scrollTop = $("messages").scrollHeight;
  } catch (e) {
    if (generation === state.watch) {
      $("chat-status").textContent = e.message;
      toast(e.message, true);
      state.selected = null;
    }
  } finally {
    if (generation === state.watch) {
      state.requestBusy = false;
      updateComposer();
    }
  }
}
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function watchTurn(turn) {
  const generation = state.watch;
  let answered = false;
  while (state.turn === turn && generation === state.watch) {
    if (Date.now() - turn.started > 300000) {
      state.turn = null;
      updateComposer();
      $("chat-status").textContent =
        "等待超过 5 分钟，未确认完成。可重新选择会话读取最新历史；服务端可能仍在运行。";
      return;
    }
    try {
      const page = await api("events", {
        id: turn.id,
        context: turn.context,
        after: state.after,
      });
      if (state.turn !== turn || generation !== state.watch) return;
      const previous = state.after;
      for (const event of page.data) {
        appendEvent(event);
        state.after = Math.max(state.after, Number(event.sequence) || 0);
        if (Number(event.sequence) <= turn.after) continue;
        if (event.type === "agent.message" && eventText(event)) answered = true;
        let message = "";
        if (event.type === "session.error" || event.type === "agent.error")
          message = "本轮失败，请展开错误事件查看详情";
        if (event.type === "session.status_terminated") message = "会话已终止";
        if (event.type === "session.status_idle") {
          const stop = event.stop_reason?.type;
          if (stop === "requires_action")
            message =
              "需要工具确认或客户端动作，请查看事件详情；当前页面不自动批准。";
          else if (stop === "end_turn")
            message = answered
              ? "本轮完成 · end_turn"
              : "本轮已结束，未返回文本回复";
          else if (stop) message = "本轮已停止 · " + stop;
        }
        if (message) {
          state.turn = null;
          updateComposer();
          $("chat-status").textContent = message;
          return;
        }
      }
      if (page.has_more && state.after <= previous)
        throw new Error("事件分页未前进");
      $("chat-status").textContent = "Agent 正在处理…";
      if (!page.has_more) await delay(1800);
    } catch (e) {
      if (generation !== state.watch) return;
      state.turn = null;
      updateComposer();
      $("chat-status").textContent =
        "读取中断：" + e.message + "。可重新选择 Session 恢复历史。";
      return;
    }
  }
}
let pendingSend = null;
$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selected || state.turn || state.requestBusy) return;
  const prompt = $("prompt").value.trim();
  if (!prompt) return;
  const session = state.selected,
    ctx = clone(context()),
    signature = pretty({ id: session.id, ctx, prompt });
  if (!pendingSend || pendingSend.signature !== signature)
    pendingSend = { signature, id: crypto.randomUUID() };
  const generation = state.watch;
  state.requestBusy = true;
  updateComposer();
  $("chat-status").textContent = "正在发送…";
  try {
    const sent = await api("send", {
      id: session.id,
      context: ctx,
      prompt,
      event_id: pendingSend.id,
    });
    if (generation !== state.watch) return;
    if (
      !Array.isArray(sent.data) ||
      !sent.data.some((ev) => ev.id === pendingSend.id)
    )
      throw new Error("发送响应未包含本次事件，尚未确认发送结果");
    const after = Math.max(...sent.data.map((e) => Number(e.sequence) || 0));
    for (const event of sent.data) appendEvent(event);
    state.after = Math.max(state.after, after);
    state.turn = { id: session.id, context: ctx, after, started: Date.now() };
    pendingSend = null;
    $("prompt").value = "";
    void watchTurn(state.turn);
  } catch (error) {
    if (generation === state.watch) {
      $("chat-status").textContent =
        "发送未确认：" + error.message + "。原样重试会复用事件 ID。";
      toast(error.message, true);
    }
  } finally {
    if (generation === state.watch) {
      state.requestBusy = false;
      updateComposer();
    }
  }
});
$("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("chat-form").requestSubmit();
  }
});
$("stop-watch").addEventListener("click", () => {
  state.watch++;
  state.turn = null;
  updateComposer();
  $("chat-status").textContent =
    "已停止本地等待。服务端仍可能继续执行；重新选择会话可查看最新历史。";
});
$("endpoint-select").addEventListener("change", () => {
  updateKeyOptions();
  resetContext();
});
$("key-select").addEventListener("change", () => {
  updateKeyOptions($("key-select").value);
  resetContext();
});
$("search").addEventListener("input", renderRows);
$("session-search").addEventListener("input", renderSessionList);
async function refreshCurrentView() {
  if (state.view === "chat" || state.view === "sessions") await loadContext();
  return state.view === "chat" ? loadSessions() : loadList();
}
action($("refresh"), refreshCurrentView);
action($("create"), openEditor);
action($("connect"), refreshCurrentView);
action($("chat-refresh"), refreshCurrentView);
action($("session-more"), () => loadSessions(true));
action($("load-more"), () => loadList(true));
action($("load-all"), async () => {
  const version = state.version;
  const seen = new Set();
  while (state.cursor && version === state.version) {
    if (seen.has(state.cursor)) throw new Error("分页游标循环");
    seen.add(state.cursor);
    await loadList(true);
  }
});
$("filter-toggle").addEventListener(
  "click",
  () => ($("filter-panel").hidden = !$("filter-panel").hidden),
);
action($("apply-filters"), async () => {
  const parsed = JSON.parse($("filters").value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
    throw new Error("筛选必须为 JSON 对象");
  state.filters = parsed;
  syncStatusFilter();
  $("filter-count").textContent = Object.keys(parsed).length || "";
  state.version++;
  await loadList();
});
$("status-filter").addEventListener("change", async () => {
  const spec = statusFilters[state.view];
  if (!spec) return;
  const value = $("status-filter").value;
  if (value) state.filters[spec.field] = value;
  else delete state.filters[spec.field];
  if (state.view === "harnesses") state.filters.IncludeArchived = true;
  if (state.view === "sessions") state.filters.include_archived = true;
  $("filters").value = pretty(state.filters);
  $("filter-count").textContent = Object.keys(state.filters).length || "";
  state.version++;
  state.rows = [];
  state.cursor = "";
  renderRows();
  try {
    await loadList();
  } catch (error) {
    toast(error.message, true);
  }
});
action($("get-by-id"), async () => {
  const id = window.prompt(
    "输入 " + state.boot.catalog[state.view].label + " ID",
  );
  if (id)
    detail(id, await api("get", { kind: state.view, id, context: context() }));
});
$("config-info").addEventListener("click", () =>
  detail("本地连接配置", {
    config_path: state.boot.config_path,
    region: state.boot.region,
    control_host: state.boot.control_host,
    local_keys: state.boot.local_keys,
    note: "Session ID 与环境 Key 在打开页面或刷新数据面连接时重新读取。账号、地域、模型与资源默认配置改动后仍需重启 server。",
  }),
);
$("import-key").addEventListener("click", () => {
  $("import-id").value = "";
  $("import-value").value = "";
  $("import-error").textContent = "";
  $("import-dialog").showModal();
});
$("import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = e.submitter;
  await busy(button, async () => {
    try {
      await api("keys/import", {
        id: $("import-id").value.trim(),
        value: $("import-value").value,
      });
      $("import-value").value = "";
      $("import-dialog").close();
      await loadContext();
      if (state.view === "quickstart") {
        quick.ids.keys = $("import-id").value.trim();
        await loadQuickResources();
        renderQuickstart();
      }
      toast("密钥已保存到本机");
    } catch (error) {
      $("import-error").textContent = error.message;
    }
  });
});
document
  .querySelectorAll(".close-dialog")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
const quick = { step: 0, start: "config", ids: {}, loaded: false };
const quickKinds = ["harnesses", "endpoints", "environments", "stores", "templates", "keys"];
function quickItems(kind) {
  let items = state.cache[kind] || [];
  if (kind === "harnesses") items = items.filter(x => x.Status === "Active");
  if (kind === "stores") items = items.filter(x => x.Status === "Ready" && x.ProviderType === "SERVERLESS_PG");
  if (kind === "templates") items = items.filter(x => x.Status === "Ready" && x.SessionStoreId === quick.ids.stores && quick.ids.stores);
  if (kind === "environments") items = items.filter(x => !/archived|deleted|failed|deleting/i.test(x.Status || ""));
  if (kind === "keys") {
    const local = new Set(state.boot.local_keys.map(x => x.id));
    items = items.filter(x => local.has(x.ApiKeyId) && x.EndpointId === quick.ids.endpoints && x.EnvironmentId === quick.ids.environments);
  }
  return items;
}
function quickSelected(kind) {
  return quickItems(kind).find(x => resourceId(x, kind) === quick.ids[kind]);
}
function renderQuickOptions() {
  for (const kind of quickKinds) {
    const select = $("quick-" + kind), items = quickItems(kind);
    setOptions(select, items, x => resourceId(x, kind), x => `${x.Name || x.Domain || resourceId(x, kind)} · ${resourceId(x, kind)}`, "请选择 " + state.boot.catalog[kind].label, quick.ids[kind]);
    if (!quick.ids[kind] && items.length === 1) select.value = resourceId(items[0], kind);
    quick.ids[kind] = select.value;
  }
  const harness = quickSelected("harnesses");
  $("quick-harness-summary").textContent = harness ? `已选择 ${harness.Name || harness.HarnessId} · Active` : "尚未选择 Harness。可创建新 Harness，或刷新资源列表。";
}
async function loadQuickResources() {
  const boot = await refreshBootstrap();
  if (boot.config_refresh_error) throw new Error(boot.config_refresh_error);
  // Settle all reads before rendering; preserve previous selections if any read fails.
  const results = await Promise.allSettled(quickKinds.map(fetchAll));
  const failed = results.find(r => r.status === "rejected");
  if (failed) throw failed.reason;
  quick.loaded = true;
  renderQuickOptions();
}
function validateQuick(step) {
  if (step >= 1 && !quickSelected("harnesses")) throw new Error("请选择一个 Active Harness。");
  if (step >= 2) {
    for (const kind of ["endpoints", "environments", "stores", "templates", "keys"]) {
      if (!quickSelected(kind)) throw new Error("请选择可用的 " + state.boot.catalog[kind].label + "；资源准备好后请刷新。");
    }
  }
}
function renderQuickstart() {
  document.querySelectorAll("[data-stage]").forEach(el => el.hidden = Number(el.dataset.stage) !== quick.step);
  document.querySelectorAll("[data-step]").forEach(el => {
    const step = Number(el.dataset.step);
    el.classList.toggle("current", step === quick.step);
    el.classList.toggle("complete", step < quick.step);
    if (step === quick.step) el.setAttribute("aria-current", "step");
    else el.removeAttribute("aria-current");
  });
  $("quick-back").hidden = quick.step === 0;
  $("quick-reload").hidden = quick.step === 0;
  $("quick-next").textContent = ["开始配置 →", "下一步：配置环境 →", "下一步：确认调用 →", "创建 Session 并聊天 →"][quick.step];
  $("quick-footer-note").textContent = quick.step === 0 ? "已选择：" + (quick.start === "config" ? "从本地配置开始" : "连接已有资源") : `步骤 ${quick.step + 1} / 4 · 选择已有资源或逐项创建`;
  if (quick.step === 3) {
    $("quick-review").replaceChildren();
    for (const kind of quickKinds) {
      const item = quickSelected(kind);
      const dd = node("dd");
      dd.append(node("strong", item?.Name || item?.Domain || "—"), node("code", quick.ids[kind] || "未选择"));
      $("quick-review").append(node("dt", state.boot.catalog[kind].label), dd);
    }
  }
}
async function goQuickStep(step) {
  $("quick-error").textContent = "";
  if (step > 0 && !quick.loaded) await loadQuickResources();
  if (step > quick.step) validateQuick(step - 1);
  quick.step = step;
  renderQuickstart();
}
async function useQuickConnection() {
  await loadQuickResources();
  validateQuick(2);
  await loadContext();
  $("endpoint-select").value = quick.ids.endpoints;
  updateKeyOptions(quick.ids.keys);
  if (!ready()) throw new Error("所选环境密钥不可用，请刷新资源后重选。");
  resetContext();
}
function quickAction(button, fn) {
  action(button, async () => {
    $("quick-error").textContent = "";
    try { await fn(); }
    catch (error) { $("quick-error").textContent = error.message; throw error; }
  });
}
document.querySelectorAll("[data-start]").forEach(button => button.addEventListener("click", () => {
  quick.start = button.dataset.start;
  document.querySelectorAll("[data-start]").forEach(el => {
    el.classList.toggle("selected", el === button);
    el.setAttribute("aria-pressed", String(el === button));
  });
  renderQuickstart();
}));
document.querySelectorAll("[data-go]").forEach(button => action(button, () => switchView(button.dataset.go)));
document.querySelectorAll("[data-step]").forEach(button => quickAction(button, () => goQuickStep(Number(button.dataset.step))));
for (const kind of quickKinds) $("quick-" + kind).addEventListener("change", () => {
  quick.ids[kind] = $("quick-" + kind).value;
  renderQuickOptions();
  $("quick-error").textContent = "";
});
document.querySelectorAll("[data-quick-create]").forEach(button => quickAction(button, () => openEditor(button.dataset.quickCreate)));
quickAction($("quick-next"), async () => {
  if (quick.step === 3) {
    await useQuickConnection();
    await openEditor("sessions");
  } else {
    const start = quick.step === 0 && quick.start === "config";
    await goQuickStep(quick.step + 1);
    if (start) await openEditor("harnesses");
  }
});
quickAction($("quick-back"), () => goQuickStep(quick.step - 1));
quickAction($("quick-reload"), async () => { await loadQuickResources(); renderQuickstart(); });
quickAction($("quick-existing-chat"), async () => { await useQuickConnection(); await switchView("chat"); });
$("quick-import").addEventListener("click", () => $("import-key").click());

async function init() {
  try {
    const response = await fetch("/api/bootstrap");
    if (!response.ok) throw new Error("无法连接本地 server");
    state.boot = await response.json();
    $("region").textContent = state.boot.region;
    $("host").textContent = state.boot.control_host;
    renderNav();
    await switchView("quickstart");
  } catch (error) {
    toast(error.message, true);
    notice(error.message, true);
  }
}
void init();
