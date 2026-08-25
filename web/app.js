const $ = (selector) => document.querySelector(selector);

const state = {
  queryFile: null,
  importFiles: [],
  searching: false,
  importing: false,
};

const elements = {
  serviceStatus: $("#serviceStatus"),
  totalImages: $("#totalImages"),
  queueCount: $("#queueCount"),
  failedCount: $("#failedCount"),
  refreshStatusBtn: $("#refreshStatusBtn"),
  queryDropzone: $("#queryDropzone"),
  queryFileInput: $("#queryFileInput"),
  queryPreview: $("#queryPreview"),
  topKInput: $("#topKInput"),
  thresholdInput: $("#thresholdInput"),
  searchBtn: $("#searchBtn"),
  clearSearchBtn: $("#clearSearchBtn"),
  searchHint: $("#searchHint"),
  resultsGrid: $("#resultsGrid"),
  resultSummary: $("#resultSummary"),
  importDropzone: $("#importDropzone"),
  importFileInput: $("#importFileInput"),
  importFileSummary: $("#importFileSummary"),
  urlInput: $("#urlInput"),
  idPrefixInput: $("#idPrefixInput"),
  batchSizeInput: $("#batchSizeInput"),
  skipExistingInput: $("#skipExistingInput"),
  importBtn: $("#importBtn"),
  importProgressBar: $("#importProgressBar"),
  importProgressText: $("#importProgressText"),
  logList: $("#logList"),
  clearLogBtn: $("#clearLogBtn"),
};

function nowTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function addLog(message, type = "info") {
  const row = document.createElement("div");
  row.className = `log-row ${type}`;
  row.innerHTML = `<span class="log-time">${nowTime()}</span><span>${escapeHtml(message)}</span>`;
  elements.logList.prepend(row);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

async function apiJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(detail);
  }
  return data;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}

function setServiceStatus(status, ok) {
  elements.serviceStatus.classList.toggle("ready", ok === true);
  elements.serviceStatus.classList.toggle("error", ok === false);
  elements.serviceStatus.innerHTML = `<span class="dot"></span>${escapeHtml(status)}`;
}

function formatNumber(value) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("zh-CN");
}

async function refreshStatus(silent = false) {
  try {
    const [health, stats] = await Promise.all([
      fetch("/health").then((res) => res.json()),
      fetch("/api/stats").then((res) => res.json()),
    ]);
    const ready = Boolean(health.model_loaded && health.db_connected);
    setServiceStatus(ready ? "服务正常" : "服务启动中", ready);
    elements.totalImages.textContent = formatNumber(stats.total_images);
    elements.queueCount.textContent = formatNumber(stats.queue_pending + stats.queue_processing);
    elements.failedCount.textContent = formatNumber(stats.failed_count);
    if (!silent) addLog(`状态已刷新，索引 ${formatNumber(stats.total_images)} 张`, "success");
  } catch (error) {
    setServiceStatus("连接失败", false);
    elements.totalImages.textContent = "-";
    elements.queueCount.textContent = "-";
    elements.failedCount.textContent = "-";
    if (!silent) addLog(`状态刷新失败：${error.message}`, "error");
  }
}

function bindDropzone(dropzone, callback) {
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-over");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    const files = [...event.dataTransfer.files].filter((file) => file.type.startsWith("image/"));
    if (files.length) callback(files);
  });
}

async function setQueryFile(file) {
  state.queryFile = file;
  elements.searchBtn.disabled = !file || state.searching;
  if (!file) {
    elements.queryPreview.hidden = true;
    elements.queryPreview.removeAttribute("src");
    elements.searchHint.textContent = "服务地址会自动使用当前页面所在主机。";
    return;
  }

  elements.queryPreview.src = await fileToDataUrl(file);
  elements.queryPreview.hidden = false;
  elements.searchHint.textContent = `${file.name}，${Math.round(file.size / 1024)} KB`;
}

function renderEmptyResult(message = "选择一张查询图片后开始搜索。") {
  elements.resultsGrid.innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2"></rect>
        <circle cx="9" cy="10" r="2"></circle>
        <path d="m21 16-5-5L5 20"></path>
      </svg>
      <strong>暂无结果</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

function canDisplayImage(url) {
  return /^https?:\/\//i.test(url) || /^data:image\//i.test(url);
}

function renderResults(results, queryTimeMs) {
  if (!results.length) {
    elements.resultSummary.textContent = `检索完成，耗时 ${queryTimeMs} ms，未返回匹配结果。`;
    renderEmptyResult("当前查询没有达到阈值的相似图片。");
    return;
  }

  elements.resultSummary.textContent = `检索完成，耗时 ${queryTimeMs} ms，返回 ${results.length} 条结果。`;
  elements.resultsGrid.innerHTML = "";

  for (const item of results) {
    const card = document.createElement("article");
    card.className = "result-card";

    const imageUrl = item.url || "";
    const thumb = canDisplayImage(imageUrl)
      ? `<img src="${escapeHtml(imageUrl)}" alt="匹配图片 ${escapeHtml(item.id)}" onerror="this.replaceWith(document.createTextNode('图片不可预览'))">`
      : "<span>图片不可预览</span>";
    const openLink = /^https?:\/\//i.test(imageUrl)
      ? `<a class="open-link" href="${escapeHtml(imageUrl)}" target="_blank" rel="noreferrer">打开图片</a>`
      : "";
    const score = `${(Number(item.score || 0) * 100).toFixed(2)}%`;

    card.innerHTML = `
      <div class="result-thumb">${thumb}</div>
      <div class="result-info">
        <div class="rank-line">
          <span class="rank-badge">#${escapeHtml(item.rank)}</span>
          <span class="score-badge">${score}</span>
        </div>
        <div class="result-id">${escapeHtml(item.id || "-")}</div>
        <div class="url-text">${escapeHtml(imageUrl || "无来源信息")}</div>
        ${openLink}
      </div>
    `;
    elements.resultsGrid.appendChild(card);
  }
}

async function searchImage() {
  if (!state.queryFile || state.searching) return;

  state.searching = true;
  elements.searchBtn.disabled = true;
  elements.searchHint.textContent = "正在生成查询向量并检索...";
  addLog(`开始搜索：${state.queryFile.name}`);

  try {
    const base64 = await fileToDataUrl(state.queryFile);
    const thresholdText = elements.thresholdInput.value.trim();
    const payload = {
      base64,
      top_k: Number(elements.topKInput.value),
      threshold: thresholdText ? Number(thresholdText) : null,
    };
    const result = await apiJson("/api/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderResults(result.results || [], result.query_time_ms);
    addLog(`搜索完成：${result.results?.length || 0} 条结果，${result.query_time_ms} ms`, "success");
    await refreshStatus(true);
  } catch (error) {
    elements.searchHint.textContent = "搜索失败，请查看日志。";
    addLog(`搜索失败：${error.message}`, "error");
  } finally {
    state.searching = false;
    elements.searchBtn.disabled = !state.queryFile;
  }
}

function sanitizeId(value, fallback) {
  const cleaned = String(value || "")
    .replace(/\.[^.]+$/, "")
    .replace(/[^\w.-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
  return cleaned || fallback;
}

function updateImportSummary() {
  const fileCount = state.importFiles.length;
  elements.importFileSummary.textContent = fileCount ? `已选择 ${fileCount} 张图片` : "可一次选择多张图片";
}

function setImportFiles(files) {
  state.importFiles = files.filter((file) => file.type.startsWith("image/"));
  updateImportSummary();
  addLog(`已选择 ${state.importFiles.length} 张本地图片`);
}

function getUrlLines() {
  return elements.urlInput.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function updateProgress(done, total, text) {
  const percent = total ? Math.round((done / total) * 100) : 0;
  elements.importProgressBar.style.width = `${percent}%`;
  elements.importProgressText.textContent = text || `${done}/${total}`;
}

async function buildFileImportItems() {
  const prefix = elements.idPrefixInput.value.trim();
  const items = [];
  for (let index = 0; index < state.importFiles.length; index += 1) {
    const file = state.importFiles[index];
    const baseId = sanitizeId(file.name, `local-${Date.now()}-${index + 1}`);
    const id = prefix ? `${prefix}-${baseId}` : baseId;
    items.push({
      id,
      base64: await fileToDataUrl(file),
      url: file.name,
    });
  }
  return items;
}

async function filterMissingItems(items) {
  if (!elements.skipExistingInput.checked || !items.length) return items;

  const result = await apiJson("/api/images/missing", {
    method: "POST",
    body: JSON.stringify({ ids: items.map((item) => item.id) }),
  });
  const missing = new Set(result.missing_ids || []);
  const existingCount = result.existing_ids?.length || 0;
  if (existingCount) addLog(`跳过已存在 ID：${existingCount} 个`, "warn");
  return items.filter((item) => missing.has(item.id));
}

async function submitLocalItems(items, progressOffset, progressTotal) {
  const missingItems = await filterMissingItems(items);
  if (!missingItems.length) {
    addLog("本地图片没有需要导入的新 ID。", "warn");
    updateProgress(progressOffset + items.length, progressTotal, "本地图片已检查完成");
    return 0;
  }

  const batchSize = Number(elements.batchSizeInput.value);
  let queued = 0;
  for (let start = 0; start < missingItems.length; start += batchSize) {
    const batch = missingItems.slice(start, start + batchSize);
    await apiJson("/api/images/ingest/batch", {
      method: "POST",
      body: JSON.stringify({ images: batch }),
    });
    queued += batch.length;
    updateProgress(
      progressOffset + Math.min(start + batch.length, items.length),
      progressTotal,
      `本地图片已提交 ${queued}/${missingItems.length} 张`
    );
    addLog(`本地图片批次已提交：${queued}/${missingItems.length}`, "success");
  }
  updateProgress(progressOffset + items.length, progressTotal, `本地图片已提交 ${queued} 张`);
  return queued;
}

async function submitUrlItems(urls, progressOffset, progressTotal) {
  if (!urls.length) return 0;

  const result = await apiJson("/api/images/ingest/urls", {
    method: "POST",
    body: JSON.stringify({
      urls,
      id_prefix: elements.idPrefixInput.value.trim(),
      skip_existing: elements.skipExistingInput.checked,
    }),
  });

  for (const error of result.errors || []) {
    addLog(`外部图片导入失败：${error.url}，${error.error_message}`, "error");
  }

  if (result.skipped_count) {
    addLog(`外部图片跳过已存在 ID：${result.skipped_count} 个`, "warn");
  }

  updateProgress(
    progressOffset + urls.length,
    progressTotal,
    `外部图片已提交 ${result.queued_count} 张，失败 ${result.failed_count} 张`
  );
  addLog(`外部图片导入完成：提交 ${result.queued_count} 张，失败 ${result.failed_count} 张`, result.failed_count ? "warn" : "success");
  return result.queued_count || 0;
}

async function importImages() {
  if (state.importing) return;

  const urls = getUrlLines();
  if (!state.importFiles.length && !urls.length) {
    addLog("请先选择本地图片，或填写外部图片 URL。", "warn");
    return;
  }

  state.importing = true;
  elements.importBtn.disabled = true;
  updateProgress(0, 1, "正在读取图片...");
  addLog("开始准备导入图片");

  try {
    const fileItems = await buildFileImportItems();
    const progressTotal = fileItems.length + urls.length;

    if (!progressTotal) {
      updateProgress(1, 1, "没有需要导入的新图片");
      addLog("没有需要导入的新图片。", "warn");
      return;
    }

    let queued = 0;
    if (fileItems.length) {
      queued += await submitLocalItems(fileItems, 0, progressTotal);
    }
    if (urls.length) {
      queued += await submitUrlItems(urls, fileItems.length, progressTotal);
    }

    await refreshStatus(true);
    addLog(`导入提交完成：${queued} 张`, "success");
  } catch (error) {
    updateProgress(0, 1, "导入失败，请查看日志");
    addLog(`导入失败：${error.message}`, "error");
  } finally {
    state.importing = false;
    elements.importBtn.disabled = false;
  }
}

elements.queryFileInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (file) setQueryFile(file);
});

elements.importFileInput.addEventListener("change", (event) => {
  setImportFiles([...event.target.files]);
});

elements.searchBtn.addEventListener("click", searchImage);
elements.clearSearchBtn.addEventListener("click", () => {
  state.queryFile = null;
  elements.queryFileInput.value = "";
  setQueryFile(null);
  renderEmptyResult();
  elements.resultSummary.textContent = "上传图片后在这里显示匹配结果。";
});

elements.importBtn.addEventListener("click", importImages);
elements.refreshStatusBtn.addEventListener("click", () => refreshStatus(false));
elements.clearLogBtn.addEventListener("click", () => {
  elements.logList.innerHTML = "";
});

bindDropzone(elements.queryDropzone, (files) => setQueryFile(files[0]));
bindDropzone(elements.importDropzone, setImportFiles);

addLog(`页面已连接到 ${window.location.origin}`);
refreshStatus(true);
setInterval(() => refreshStatus(true), 10000);
