"use strict";
import {optionsForm, parseIds} from "./forms.js";

const $ = (selector, root = document) => root.querySelector(selector);
const plugins = new Map();
const dirtyForms = new Set();
const formatDate = value => new Date(value).toLocaleString("zh-CN", {hour12: false});
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
let restarting = false;

async function request(path, options = {}) {
  const response = await fetch(path, {cache: "no-store", ...options});
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已失效，请刷新页面重新登录。");
    if (response.status === 422) throw new Error("输入不符合要求，请检查群号、QQ 号和插件参数。");
    let message = `请求失败（${response.status}），请刷新或查看 Coolify 日志。`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* A proxy can return HTML instead of JSON. */ }
    throw new Error(message);
  }
  return response.json();
}

function updateStatus(card, plugin) {
  const badge = $(".badge", card);
  badge.className = "badge";
  if (plugin.load_state === "failed") {
    badge.textContent = "加载失败";
    badge.classList.add("error");
  } else if (!plugin.loaded) {
    badge.textContent = "未加载";
  } else if (plugin.settings.enabled) {
    badge.textContent = "已加载，功能开启";
    badge.classList.add("active");
  } else {
    badge.textContent = "已加载，功能关闭";
  }
  const error = $(".load-error", card);
  error.hidden = !plugin.load_error;
  error.textContent = plugin.load_error || "";
  const pending = $(".pending-load", card);
  pending.hidden = !plugin.restart_required;
  pending.textContent = plugin.settings.load_on_start ? "待重启后加载" : "待重启后停止加载";
  $("#restart-notice").hidden = ![...plugins.values()].some(item => item.restart_required);
}

function groupRule(groupId, members, schema, overrides, inherited) {
  const row = document.createElement("div");
  row.className = "group-rule";
  const idLabel = document.createElement("label");
  idLabel.className = "field";
  idLabel.textContent = "群号";
  const id = document.createElement("input");
  id.type = "text";
  id.inputMode = "numeric";
  id.pattern = "[1-9][0-9]{0,19}";
  id.required = true;
  id.value = groupId;
  idLabel.append(id);
  const modeLabel = document.createElement("label");
  modeLabel.className = "field";
  modeLabel.textContent = "成员范围";
  const mode = document.createElement("select");
  for (const [value, text] of [["all", "全群成员"], ["allowlist", "指定成员"]]) {
    const option = document.createElement("option");
    option.value = value; option.textContent = text; mode.append(option);
  }
  mode.value = members === null ? "all" : "allowlist";
  modeLabel.append(mode);
  const usersLabel = document.createElement("label");
  usersLabel.className = "field group-users";
  usersLabel.textContent = "允许的 QQ 号";
  const users = document.createElement("textarea");
  users.rows = 2;
  users.placeholder = "每行一个 QQ 号；留空不允许任何成员";
  users.value = (members || []).join("\n");
  usersLabel.append(users);
  const updateMode = () => { usersLabel.hidden = mode.value === "all"; };
  mode.addEventListener("change", updateMode);
  updateMode();
  const remove = document.createElement("button");
  remove.type = "button"; remove.className = "secondary remove-group"; remove.textContent = "移除此群";
  remove.addEventListener("click", () => {
    const form = row.closest("form"); row.remove(); form.dispatchEvent(new Event("input", {bubbles: true}));
  });
  row.append(idLabel, modeLabel, remove, usersLabel);
  let readOverrides = () => ({});
  if (Object.keys(schema.properties || {}).length) {
    const details = document.createElement("details");
    details.className = "group-options";
    const summary = document.createElement("summary");
    summary.textContent = "本群参数";
    const hint = document.createElement("p");
    hint.className = "field-hint";
    hint.textContent = "默认继承公共参数；勾选后仅对此群覆盖。取消勾选恢复继承。";
    const fields = document.createElement("div");
    details.append(summary, hint, fields);
    row.append(details);
    readOverrides = optionsForm(fields, schema, overrides, {inherited});
    const updateSummary = () => {
      const count = fields.querySelectorAll(".override-toggle input:checked").length;
      summary.textContent = count ? `本群参数（${count} 项覆盖）` : "本群参数（全部继承）";
    };
    fields.addEventListener("change", updateSummary);
    details.addEventListener("toggle", () => { if (details.open) readOverrides.refresh(); });
    updateSummary();
  }
  row.refreshInherited = () => readOverrides.refresh?.();
  row.read = () => {
    if (!/^[1-9][0-9]{0,19}$/.test(id.value.trim())) throw new Error("请填写有效群号，或移除空白群规则。");
    return {id: id.value.trim(), users: mode.value === "all" ? null : parseIds(users.value), options: readOverrides()};
  };
  return row;
}

function createPlugin(plugin) {
  const card = $("#plugin-template").content.firstElementChild.cloneNode(true);
  card.id = `plugin-${plugin.id}`;
  $("h3", card).textContent = plugin.name;
  $(".description", card).textContent = plugin.description;
  $(".commands", card).textContent = plugin.commands.join("  ");
  const form = $("form", card);
  for (const name of ["enabled", "load_on_start"]) form.elements[name].checked = plugin.settings[name];
  const privateMode = form.elements.private_mode;
  privateMode.value = !plugin.settings.allow_private ? "off" :
    (plugin.settings.private_user_ids === null ? "all" : "allowlist");
  form.elements.private_user_ids.value = (plugin.settings.private_user_ids || []).join("\n");
  const updatePrivate = () => { $(".private-users", form).hidden = privateMode.value !== "allowlist"; };
  privateMode.addEventListener("change", updatePrivate); updatePrivate();
  let readOptions;
  try {
    readOptions = optionsForm($(".options", form), plugin.options_schema, plugin.settings.options);
    if (!Object.keys(plugin.options_schema.properties || {}).length) $(".options", form).hidden = true;
    let currentPublic = plugin.settings.options;
    const inherited = () => {
      try { currentPublic = readOptions(); } catch { /* Invalid public input is reported on save. */ }
      return currentPublic;
    };
    const appendGroup = (id = "", members = null, overrides = {}) => {
      $(".group-rules", form).append(groupRule(id, members, plugin.options_schema, overrides, inherited));
    };
    for (const id of plugin.settings.group_ids) {
      appendGroup(id, plugin.settings.group_user_ids[id] ?? null, plugin.settings.group_options?.[id] || {});
    }
    $(".add-group", form).addEventListener("click", () => {
      appendGroup(); form.dispatchEvent(new Event("input", {bubbles: true}));
    });
    $(".options", form).addEventListener("input", () => {
      form.querySelectorAll(".group-rule").forEach(row => row.refreshInherited());
    });
  } catch (error) {
    readOptions = undefined;
    $(".save-status", form).textContent = error.message;
    $(".save-status", form).className = "save-status error";
    $("button[type=submit]", form).disabled = true;
  }
  form.addEventListener("input", () => {
    dirtyForms.add(plugin.id);
    const status = $(".save-status", form);
    status.className = "save-status"; status.textContent = "有未保存的修改";
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!readOptions || restarting) return;
    const button = $("button[type=submit]", form);
    const status = $(".save-status", form);
    button.disabled = true;
    status.className = "save-status";
    status.textContent = "正在保存…";
    try {
      const groups = [...form.querySelectorAll(".group-rule")].map(row => row.read());
      if (new Set(groups.map(group => group.id)).size !== groups.length) throw new Error("同一插件不能重复添加相同群号。");
      const settings = {
        enabled: form.elements.enabled.checked, load_on_start: form.elements.load_on_start.checked,
        group_ids: groups.map(group => group.id),
        group_user_ids: Object.fromEntries(groups.filter(group => group.users !== null).map(group => [group.id, group.users])),
        group_options: Object.fromEntries(groups.filter(group => Object.keys(group.options).length).map(group => [group.id, group.options])),
        allow_private: privateMode.value !== "off",
        private_user_ids: privateMode.value === "all" ? null : (privateMode.value === "allowlist" ?
          parseIds(form.elements.private_user_ids.value) : plugins.get(plugin.id).settings.private_user_ids),
        options: readOptions()
      };
      const saved = await request(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
        method: "PUT", headers: {"Content-Type": "application/json", "X-Requested-With": "qqbot-admin"},
        body: JSON.stringify(settings)
      });
      plugins.set(plugin.id, saved); dirtyForms.delete(plugin.id);
      updateStatus(card, saved); renderGroups();
      status.textContent = saved.restart_required ? "已保存，加载配置需重启后生效。" : "已保存，对新消息生效。";
    } catch (error) {
      status.className = "save-status error"; status.textContent = error.message;
    } finally { button.disabled = false; }
  });
  updateStatus(card, plugin);
  return card;
}

function switchView(name) {
  $("#plugins").hidden = name !== "plugins"; $("#groups").hidden = name !== "groups";
  document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === name)));
}

function renderGroups() {
  const container = $("#groups"); container.replaceChildren();
  const ids = [...new Set([...plugins.values()].flatMap(plugin => plugin.settings.group_ids))];
  if (!ids.length) {
    const empty = document.createElement("p"); empty.className = "empty-state";
    empty.textContent = "尚未配置任何群。先在插件中添加允许使用的群。"; container.append(empty); return;
  }
  for (const group of ids) {
    const section = document.createElement("section"); section.className = "group-summary";
    const title = document.createElement("h3"); title.textContent = `群 ${group}`; section.append(title);
    for (const plugin of plugins.values()) {
      if (!plugin.settings.group_ids.includes(group)) continue;
      const row = document.createElement("div"); row.className = "group-summary-row";
      const text = document.createElement("p");
      const users = plugin.settings.group_user_ids[group];
      const scope = users === undefined ? "全群成员" : (users.length ? `指定 ${users.length} 位成员` : "成员白名单为空，无人可用");
      const active = plugin.loaded && plugin.settings.enabled ? "已开启" : "当前不可用";
      const overrides = Object.keys(plugin.settings.group_options?.[group] || {}).length;
      text.textContent = `${plugin.name}：${active}，${scope}，${overrides ? `${overrides} 项群参数覆盖` : "继承公共参数"}`;
      const edit = document.createElement("button"); edit.className = "secondary"; edit.type = "button"; edit.textContent = "编辑插件";
      edit.addEventListener("click", () => { switchView("plugins"); document.getElementById(`plugin-${plugin.id}`).scrollIntoView({block: "start"}); });
      row.append(text, edit); section.append(row);
    }
    container.append(section);
  }
}

async function refresh() {
  const errorBox = $("#page-error"); $("#refresh").disabled = true; errorBox.hidden = true;
  try {
    const [status, list] = await Promise.all([request("/api/status"), request("/api/plugins")]);
    const accounts = status.connected_accounts;
    $("#connection").textContent = accounts.length ? "QQ 已连接" : "QQ 尚未连接";
    $("#connection").classList.toggle("connected", accounts.length > 0);
    $("#accounts").textContent = accounts.length ? `账号 ${accounts.join("、")}` : "请检查 SnowLuma 登录状态和 OneBot 连接。";
    $("#started").textContent = formatDate(status.started_at); $("#checked").textContent = formatDate(Date.now());
    $("#restart").disabled = restarting || !status.process_restart_supported;
    $("#restart").title = status.process_restart_supported ? "重新读取已保存配置，不更新镜像或环境变量" : "本环境未启用进程重启";
    $("#coolify").hidden = true;
    try {
      const url = new URL(status.coolify_url);
      if (url.protocol === "https:") { $("#coolify").href = url.href; $("#coolify").hidden = false; }
    } catch { /* The optional external link must not block plugin management. */ }
    plugins.clear(); dirtyForms.clear(); list.forEach(plugin => plugins.set(plugin.id, plugin));
    $("#plugins").replaceChildren(...list.map(createPlugin));
    $("#plugin-count").textContent = `${list.length} 个插件`;
    renderGroups();
    const select = $("#permission-form").elements.plugin_id; const selected = select.value;
    select.replaceChildren(...list.map(plugin => { const option = document.createElement("option"); option.value = plugin.id; option.textContent = plugin.name; return option; }));
    if (list.some(plugin => plugin.id === selected)) select.value = selected;
    return true;
  } catch (error) {
    errorBox.textContent = error.message; errorBox.hidden = false; return false;
  } finally { $("#refresh").disabled = restarting; }
}

$("#refresh").addEventListener("click", () => {
  if (!dirtyForms.size || confirm("有未保存的修改，刷新会丢弃这些修改。继续刷新？")) refresh();
});
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
$("#permission-form").addEventListener("submit", async event => {
  event.preventDefault(); const form = event.currentTarget; const result = $("#permission-result");
  const params = new URLSearchParams({user_id: form.elements.user_id.value.trim()});
  if (form.elements.group_id.value.trim()) params.set("group_id", form.elements.group_id.value.trim());
  try {
    const decision = await request(`/api/plugins/${encodeURIComponent(form.elements.plugin_id.value)}/permission?${params}`);
    result.className = decision.allowed ? "allowed" : "error";
    result.textContent = `${decision.allowed ? "允许" : "拒绝"}：${decision.reason}`;
  } catch (error) { result.className = "error"; result.textContent = error.message; }
});
$("#restart").addEventListener("click", async () => {
  const status = $("#process-status"); status.hidden = false; status.className = "notice";
  if (dirtyForms.size) { status.textContent = "请先保存配置；有未保存的修改，尚未执行重启。"; return; }
  if (!confirm("重启 NoneBot 会短暂断开 QQ 连接，随后自动恢复。确认重启进程？")) { status.hidden = true; return; }
  restarting = true; $("#restart").disabled = true; $("#refresh").disabled = true;
  $(".plugins-area").inert = true;
  status.textContent = "正在请求重启…";
  try {
    const previous = await request("/api/restart", {method: "POST", headers: {"X-Requested-With": "qqbot-admin"}});
    status.textContent = "重启请求已接受，等待进程恢复…";
    let restored = false;
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      await sleep(1500);
      try {
        const current = await request("/api/status", {signal: AbortSignal.timeout(2000)});
        if (current.started_at !== previous.started_at) { restored = true; break; }
      } catch { /* A short connection gap is expected while Docker starts the process. */ }
    }
    restarting = false;
    if (restored) {
      status.textContent = "进程已重启，正在刷新状态。QQ 连接可能仍在恢复。";
      await refresh();
    } else {
      status.className = "notice error";
      status.textContent = "尚未确认进程恢复，请刷新状态或到 Coolify 查看日志。未自动重复重启。";
      $("#refresh").disabled = false;
    }
  } catch (error) {
    restarting = false; status.className = "notice error"; status.textContent = error.message;
    $("#refresh").disabled = false; $("#restart").disabled = false;
  } finally { $(".plugins-area").inert = false; }
});
refresh();
