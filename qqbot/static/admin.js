"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const plugins = new Map();
const formatDate = value => new Date(value).toLocaleString("zh-CN", {hour12: false});

async function request(path, options = {}) {
  const response = await fetch(path, {cache: "no-store", ...options});
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已失效，请刷新页面重新登录。");
    if (response.status === 422) throw new Error("输入不符合要求，请检查群号和插件参数。");
    let message = `请求失败（${response.status}），请稍后刷新或查看 Coolify 日志。`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* Keep the status message when a proxy returns HTML. */ }
    throw new Error(message);
  }
  return response.json();
}

function updateStatus(card, plugin) {
  const badge = $(".badge", card);
  badge.className = "badge";
  if (plugin.load_error) {
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
  $("#restart-notice").hidden = ![...plugins.values()].some(item => item.restart_required);
}

function createPlugin(plugin) {
  const card = $("#plugin-template").content.firstElementChild.cloneNode(true);
  $("h3", card).textContent = plugin.name;
  $(".description", card).textContent = plugin.description;
  $(".commands", card).textContent = plugin.commands.join("  ");
  const form = $("form", card);
  for (const name of ["enabled", "load_on_start", "allow_private"]) {
    form.elements[name].checked = plugin.settings[name];
  }
  form.elements.group_ids.value = plugin.settings.group_ids.join("\n");
  const optionInputs = new Map();
  for (const [name, schema] of Object.entries(plugin.options_schema.properties || {})) {
    const label = document.createElement("label");
    label.className = "field";
    label.textContent = schema.title || name;
    const input = document.createElement("input");
    input.type = "text";
    input.value = plugin.settings.options[name] ?? "";
    if (schema.minLength) {input.minLength = schema.minLength; input.required = true;}
    if (schema.maxLength) input.maxLength = schema.maxLength;
    label.append(input);
    $(".options", card).append(label);
    optionInputs.set(name, input);
  }
  form.addEventListener("input", () => {
    const status = $(".save-status", form);
    status.className = "save-status";
    status.textContent = "有未保存的修改";
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = $("button", form);
    const status = $(".save-status", form);
    const groupIds = form.elements.group_ids.value.trim().split(/[\s,，]+/).filter(Boolean);
    if (groupIds.some(id => !/^[1-9][0-9]{0,19}$/.test(id))) {
      status.className = "save-status error";
      status.textContent = "群号必须是完整的正整数，请勿填写群名称。";
      return;
    }
    button.disabled = true;
    status.className = "save-status";
    status.textContent = "正在保存…";
    const settings = {
      enabled: form.elements.enabled.checked,
      load_on_start: form.elements.load_on_start.checked,
      allow_private: form.elements.allow_private.checked,
      group_ids: groupIds,
      options: Object.fromEntries([...optionInputs].map(([name, input]) => [name, input.value]))
    };
    try {
      const saved = await request(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json", "X-Requested-With": "qqbot-admin"},
        body: JSON.stringify(settings)
      });
      plugins.set(plugin.id, saved);
      updateStatus(card, saved);
      status.textContent = saved.restart_required ? "已保存，加载配置需重启后生效。" : "已保存，对新消息生效。";
    } catch (error) {
      status.className = "save-status error";
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  updateStatus(card, plugin);
  return card;
}

async function refresh() {
  const refreshButton = $("#refresh");
  const errorBox = $("#page-error");
  refreshButton.disabled = true;
  errorBox.hidden = true;
  try {
    const [status, list] = await Promise.all([request("/api/status"), request("/api/plugins")]);
    const accounts = status.connected_accounts;
    $("#connection").textContent = accounts.length ? "QQ 已连接" : "QQ 尚未连接";
    $("#connection").classList.toggle("connected", accounts.length > 0);
    $("#accounts").textContent = accounts.length ? `账号 ${accounts.join("、")}` : "请检查 NapCat 登录状态和 OneBot 连接。";
    $("#started").textContent = formatDate(status.started_at);
    $("#checked").textContent = formatDate(Date.now());
    $("#coolify").hidden = true;
    try {
      const url = new URL(status.coolify_url);
      if (url.protocol === "https:") {
        $("#coolify").href = url.href;
        $("#coolify").hidden = false;
      }
    } catch { /* An optional process-management link must not hide the plugin list. */ }
    plugins.clear();
    list.forEach(plugin => plugins.set(plugin.id, plugin));
    $("#plugins").replaceChildren(...list.map(createPlugin));
    $("#plugin-count").textContent = `${list.length} 个插件`;
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    refreshButton.disabled = false;
  }
}

$("#refresh").addEventListener("click", refresh);
refresh();
