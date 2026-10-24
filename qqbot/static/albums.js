"use strict";

// Album controls share the existing admin request/authentication behavior.
export function setupAlbums(request) {
  const $ = selector => document.querySelector(selector);
  const panel = $("#albums");
  const select = $("#album-select");
  const status = $("#album-status");
  const gallery = $("#album-images");
  const writeHeaders = {"X-Requested-With": "qqbot-admin"};
  let selected = "";
  let busy = false;

  function message(text, error = false) {
    status.textContent = text;
    status.className = error ? "album-status error" : "album-status";
  }

  async function action(work) {
    if (busy) return;
    busy = true;
    panel.inert = true;
    panel.setAttribute("aria-busy", "true");
    try { await work(); }
    catch (error) { message(error.message, true); }
    finally {
      busy = false;
      panel.inert = false;
      panel.removeAttribute("aria-busy");
    }
  }

  function imageCard(image) {
    const card = document.createElement("article");
    card.className = "album-image";
    const link = document.createElement("a");
    link.href = image.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.setAttribute("aria-label", `查看原图 ${image.id}`);
    const preview = document.createElement("img");
    preview.src = image.url;
    preview.alt = `图集图片 ${image.id}`;
    preview.loading = "lazy";
    preview.decoding = "async";
    link.append(preview);
    const body = document.createElement("div");
    body.className = "album-image-body";
    const filename = document.createElement("p");
    filename.className = "album-filename";
    filename.textContent = image.id;
    const source = document.createElement("p");
    source.className = "album-image-meta";
    const sourceName = {upload: "手动上传", anime_rating_watch: "图片监测"}[image.source] || image.source;
    source.textContent = `来源：${sourceName}${image.metadata?.group_id ? `，群 ${image.metadata.group_id}` : ""}`;
    const time = document.createElement("time");
    time.className = "album-image-meta";
    time.dateTime = image.created_at;
    time.textContent = new Date(image.created_at).toLocaleString("zh-CN", {hour12: false});
    const footer = document.createElement("div");
    footer.className = "album-image-actions";
    const original = document.createElement("a");
    original.href = image.url;
    original.target = "_blank";
    original.rel = "noopener";
    original.textContent = "查看原图";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary danger";
    remove.textContent = "删除";
    remove.setAttribute("aria-label", `删除图片 ${image.id}`);
    remove.addEventListener("click", () => {
      if (!confirm(`确认从图集“${image.album}”删除这张图片？删除后无法恢复，晚安插件也不会再抽到它。`)) return;
      action(async () => {
        message("正在删除图片…");
        await request(image.url, {method: "DELETE", headers: writeHeaders});
        await loadImages();
        message("图片已删除。");
      });
    });
    footer.append(original, remove);
    body.append(filename, source, time, footer);
    card.append(link, body);
    return card;
  }

  async function loadImages() {
    // Clear the previous collection before requesting another one.
    gallery.replaceChildren();
    $("#album-upload").hidden = !selected;
    $("#album-delete").disabled = true;
    $("#album-image-count").textContent = "";
    $("#album-current").textContent = selected || "尚未选择图集";
    if (!selected) {
      const empty = document.createElement("p");
      empty.className = "album-empty muted";
      empty.textContent = "还没有图集。先新建一个，再上传图片。";
      gallery.append(empty);
      return;
    }
    const images = await request(`/api/albums/${encodeURIComponent(selected)}/images`);
    images.sort((a, b) => b.created_at.localeCompare(a.created_at));
    $("#album-image-count").textContent = `${images.length} 张图片`;
    $("#album-delete").disabled = images.length > 0;
    $("#album-delete").title = images.length ? "请先删除图集中的图片" : "删除这个空图集";
    if (images.length) gallery.replaceChildren(...images.map(imageCard));
    else {
      const empty = document.createElement("p");
      empty.className = "album-empty muted";
      empty.textContent = "图集还是空的，可以上传图片，也可以让图片监测插件写入。";
      gallery.append(empty);
    }
  }

  async function loadAlbums(preferred = selected) {
    const albums = await request("/api/albums");
    selected = albums.some(album => album.id === preferred) ? preferred : (albums[0]?.id || "");
    select.replaceChildren();
    for (const album of albums) {
      const option = document.createElement("option");
      option.value = album.id;
      option.textContent = album.id;
      select.append(option);
    }
    if (!albums.length) {
      const option = document.createElement("option");
      option.textContent = "暂无图集";
      option.value = "";
      select.append(option);
    }
    select.value = selected;
    select.disabled = !albums.length;
    await loadImages();
  }

  function refresh() {
    return action(async () => {
      message("正在读取图集…");
      await loadAlbums();
      message("");
    });
  }

  $("#album-refresh").addEventListener("click", refresh);
  select.addEventListener("change", () => action(async () => {
    selected = select.value;
    $("#album-upload").reset();
    message("正在读取图片…");
    await loadImages();
    message("");
  }));
  $("#album-create").addEventListener("submit", event => {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.elements.id.value.trim();
    action(async () => {
      message("正在创建图集…");
      await request("/api/albums", {method: "POST",
        headers: {...writeHeaders, "Content-Type": "application/json"}, body: JSON.stringify({id})});
      form.reset();
      $("#album-upload").reset();
      await loadAlbums(id);
      message(`已打开图集“${id}”。`);
    });
  });
  $("#album-upload").addEventListener("submit", event => {
    event.preventDefault();
    const form = event.currentTarget;
    const file = form.elements.image.files[0];
    if (!file || !selected) return;
    if (file.size > 10 * 1024 * 1024) { message("图片不能超过 10 MiB。", true); return; }
    action(async () => {
      message("正在上传图片…");
      await request(`/api/albums/${encodeURIComponent(selected)}/images`, {method: "POST",
        headers: {...writeHeaders, "Content-Type": file.type || "application/octet-stream"}, body: file});
      form.reset();
      await loadImages();
      message("图片已上传。");
    });
  });
  $("#album-delete").addEventListener("click", () => {
    if (!selected || !confirm(`确认删除空图集“${selected}”？此操作不会修改插件中的图集配置。`)) return;
    action(async () => {
      message("正在删除图集…");
      await request(`/api/albums/${encodeURIComponent(selected)}`, {method: "DELETE", headers: writeHeaders});
      $("#album-upload").reset();
      await loadAlbums();
      message("空图集已删除。");
    });
  });
  return {refresh};
}
