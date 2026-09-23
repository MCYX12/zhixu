"use strict";
const $ = (id) => document.getElementById(id);
const iconPaths = {
  plus: "M12 5v14M5 12h14",
  chevron: "m7 10 5 5 5-5",
  "chevron-right": "m9 6 6 6-6 6",
  "arrow-up": "M12 19V5m-5 5 5-5 5 5",
  "arrow-right": "M5 12h14m-5-5 5 5-5 5",
  "arrow-up-right": "M6 18 18 6M6 6h12v12",
  sparkles:
    "m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3ZM20 2v4m-2-2h4",
  library: "M4 4h4v16H4zM11 4h4v16h-4zM18 5l3-1 3 15-3 1z",
  history: "M3 11a9 9 0 1 1 2 7M3 4v7h7m2-5v6l4 2",
  message:
    "M20 4H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h3l5 4v-4h8a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1Z",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  settings:
    "m10 3-1 3-3 1-3-1-2 4 2 2v3l-2 2 2 4 3-1 3 1 1 3h4l1-3 3-1 3 1 2-4-2-2v-3l2-2-2-4-3 1-3-1-1-3Z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  "log-in": "M9 4H4v16h5m4-12 4 4-4 4m-5-4h13",
  "log-out": "M9 4H4v16h5m7-12 4 4-4 4m-5-4h9",
  help: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3v.1",
  paperclip: "m8 12 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l9-9m-5 13 8-8",
  layers: "m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5",
  lock: "M6 10h12v11H6zM8 10V7a4 4 0 0 1 8 0v3m-4 5v2",
  "file-search":
    "M13 3H5v18h14V9l-6-6Zm0 0v6h6m-8 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm2 5 3 3",
  file: "M13 3H5v18h14V9l-6-6Zm0 0v6h6M8 13h8m-8 4h6",
  pen: "m4 16-1 5 5-1L21 7l-4-4L4 16Zm10-10 4 4M4 16l4 4",
  compass: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-6-3-2 4-4 2 2-4 4-2Z",
  panels: "M3 4h18v16H3zM15 4v16",
  quote:
    "M4 5h6v7H5v1a4 4 0 0 0 4 4v2a7 7 0 0 1-7-7V5h2Zm12 0h6v7h-5v1a4 4 0 0 0 4 4v2a7 7 0 0 1-7-7V5h2Z",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  upload: "M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5",
  search: "M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm-2 4 6 6",
  x: "m6 6 12 12M6 18 18 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  refresh:
    "M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5m-4 6a8 8 0 0 0 14 5l3-3m0 5v-5h-5",
  stop: "M6 6h12v12H6z",
  copy: "M8 8h13v13H8zM16 8V3H3v13h5",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7",
  users:
    "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM2 21v-3a7 7 0 0 1 14 0v3m0-17a4 4 0 0 1 0 8m3 3a6 6 0 0 1 3 6",
  database:
    "M20 5c0 2-4 3-8 3S4 7 4 5s4-3 8-3 8 1 8 3ZM4 5v14c0 2 4 3 8 3s8-1 8-3V5M4 12c0 2 4 3 8 3s8-1 8-3",
  activity: "M2 12h5l3-8 4 16 3-8h5",
  check: "m5 12 4 4L19 6",
};
function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${iconPaths[name] || iconPaths.file}"/></svg>`;
}
function hydrate(root = document) {
  root.querySelectorAll("i[data-icon]").forEach((el) => {
    el.outerHTML = icon(el.dataset.icon);
  });
}
function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
const state = {
  user: null,
  csrf: null,
  view: "workbench",
  docs: [],
  conversations: [],
  messages: [],
  conversation: null,
  busy: false,
  controller: null,
  filter: "all",
  files: [],
  accessDoc: null,
  saveFailed: false,
  uploading: false,
};
const names = {
  workbench: "AI 工作台",
  knowledge: "文档知识库",
  history: "历史会话",
  status: "系统状态",
};
const modes = {
  auto: "智能模式",
  local: "本地对话",
  knowledge: "知识库问答",
  web: "联网搜索",
};
const visibilityNames = {
  private: "仅自己",
  group: "组内共享",
  public: "全员可见",
};
let toastTimer;
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    $("toast").hidden = true;
  }, 4500);
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.csrf) headers.set("X-CSRF-Token", state.csrf);
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    options.body = JSON.stringify(options.json);
    delete options.json;
  }
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    let body;
    try {
      body = await response.json();
    } catch {}
    const error = new Error(
      body?.error?.message ||
        (response.status === 422
          ? "输入格式不正确，请检查后重试"
          : `服务暂时不可用（${response.status}）`),
    );
    error.status = response.status;
    if (response.status === 401 && state.user) {
      state.user = null;
      state.csrf = null;
      state.messages = [];
      state.conversation = null;
      state.docs = [];
      state.conversations = [];
      renderIdentity();
      renderMessages();
      renderRecent();
      renderHome(null);
      renderLibrary();
      renderHistory();
      renderSourceRail([]);
    }
    throw error;
  }
  return response;
}
const getJSON = async (path, options) => (await api(path, options)).json();
function requireUser() {
  if (state.user) return true;
  $("login-dialog").showModal();
  $("api-key").focus();
  return false;
}
function timeLabel(ts) {
  const date = new Date(ts * 1000);
  return (
    date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) +
    " " +
    date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
  );
}
function sizeLabel(bytes) {
  if (!bytes) return "目录索引";
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function badge(doc) {
  return `<span class="badge ${esc(doc.visibility)}">${icon(doc.visibility === "private" ? "lock" : doc.visibility === "group" ? "users" : "library")}${visibilityNames[doc.visibility]}</span>`;
}
function fileIcon(path) {
  const ext = path.split(".").pop().toLowerCase();
  return `<span class="file-icon ${ext === "pdf" ? "pdf" : ext === "docx" ? "docx" : ""}">${icon("file")}</span>`;
}
function renderIdentity() {
  const user = state.user;
  $("members-panel").hidden = user?.role !== "admin";
  if (user?.role !== "admin") $("members-list").replaceChildren();
  $("user-name").textContent = user ? user.id : "连接工作空间";
  $("user-role").textContent = user
    ? user.role === "admin"
      ? "工作空间管理员"
      : "团队成员"
    : "使用你的访问密钥";
  $("user-avatar").textContent = user ? user.id[0].toUpperCase() : "访";
  $("top-avatar").textContent = user ? user.id[0].toUpperCase() : "Z";
  const btn = $("profile");
  btn.setAttribute("aria-label", user ? "退出当前账号" : "连接工作空间");
  const previous = btn.querySelector("svg:last-child");
  if (previous) previous.outerHTML = icon(user ? "log-out" : "log-in");
}
function renderRecent() {
  const chats = state.conversations.slice(0, 7);
  $("recent-chats").innerHTML = chats.length
    ? chats
        .map(
          (c) =>
            `<button class="recent-chat" data-conversation="${esc(c.id)}">${icon("message")}<span>${esc(c.title)}</span></button>`,
        )
        .join("")
    : `<p class="sidebar-empty">${state.user ? "还没有会话，从一个问题开始" : "连接后，继续你的工作"}</p>`;
}
function renderHome(data) {
  $("stat-docs").innerHTML = `${data?.documents ?? "—"}<small>份</small>`;
  $("stat-chats").innerHTML = `${data?.conversations ?? "—"}<small>次</small>`;
  $("nav-doc-count").textContent = data?.documents ?? "—";
  const docs = data?.recent_documents || [];
  $("home-documents").innerHTML = docs.length
    ? docs
        .slice(0, 3)
        .map(
          (d) =>
            `<div class="home-doc" role="button" tabindex="0" data-document="${esc(d.id)}">${fileIcon(d.path)}<div class="home-doc-info"><strong>${esc(d.path)}</strong><small>${visibilityNames[d.visibility]} · ${d.chunk_count} 个知识片段</small></div><span>${timeLabel(d.updated_at)}</span></div>`,
        )
        .join("")
    : `<div class="empty-inline">${icon("file")}<span>${state.user ? "尚无文档，上传第一份资料开始积累知识" : "连接工作空间，查看你的知识文档"}</span></div>`;
  $("rail-upload").innerHTML =
    `${data?.documents ? "添加更多知识" : "添加第一份知识"}${icon("arrow-right")}`;
}
async function refreshData() {
  if (!state.user) {
    renderHome(null);
    return;
  }
  const [workspace, docs, conversations] = await Promise.all([
    getJSON("/api/workspace"),
    getJSON("/api/documents"),
    getJSON("/api/conversations"),
  ]);
  $("web-mode-option").disabled = !workspace.web_allowed;
  state.docs = docs.data;
  state.conversations = conversations.data;
  renderHome(workspace);
  renderRecent();
  renderLibrary();
  renderHistory();
}
function navigate(view) {
  window.scrollTo({ top: 0, behavior: "instant" });
  state.view = view;
  document.querySelectorAll(".view").forEach((el) => {
    el.hidden = el.id !== `view-${view}`;
    el.classList.toggle("active", !el.hidden);
  });
  document
    .querySelectorAll(".nav-item[data-view]")
    .forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  $("page-name").textContent = names[view];
  $("sidebar").classList.remove("open");
  if (view === "status") loadStatus();
  if (view === "knowledge") renderLibrary();
  if (view === "history") renderHistory();
}
function newChat() {
  if (state.busy) {
    toast("请先停止当前回答");
    return;
  }
  state.messages = [];
  state.conversation = null;
  state.saveFailed = false;
  $("question").value = "";
  if ($("mode").value !== "web") $("mode").value = "auto";
  updateMode();
  renderMessages();
  renderSourceRail([]);
  navigate("workbench");
  $("question").focus();
}
function renderLibrary() {
  const own = state.docs.filter((d) => d.owner_id === state.user?.id);
  $("library-metrics").innerHTML =
    `<div class="metric"><span>${icon("library")}</span><div><p>可访问文档</p><strong>${state.user ? state.docs.length : "—"}<small>份</small></strong></div></div><div class="metric"><span>${icon("lock")}</span><div><p>我的文档</p><strong>${state.user ? own.length : "—"}<small>份</small></strong></div></div><div class="metric"><span>${icon("layers")}</span><div><p>知识片段</p><strong>${state.user ? state.docs.reduce((n, d) => n + d.chunk_count, 0) : "—"}<small>个</small></strong></div></div>`;
  const query = $("document-search").value.trim().toLowerCase();
  const docs = state.docs.filter(
    (d) =>
      (state.filter === "all" ||
        (d.visibility === state.filter &&
          (state.filter !== "private" || d.owner_id === state.user?.id))) &&
      d.path.toLowerCase().includes(query),
  );
  $("document-rows").innerHTML = docs
    .map(
      (d) =>
        `<tr><td><button class="document-cell" data-document="${esc(d.id)}">${fileIcon(d.path)}<span><strong>${esc(d.path)}</strong><small>${sizeLabel(d.size)} · ${esc(d.owner_id)}</small></span></button></td><td>${badge(d)}</td><td>${d.chunk_count} 个</td><td>${timeLabel(d.updated_at)}</td><td><div class="row-actions"><button class="icon-button" data-document="${esc(d.id)}" aria-label="预览 ${esc(d.path)}">${icon("file-search")}</button>${d.can_manage ? `<button class="icon-button" data-access="${esc(d.id)}" aria-label="设置 ${esc(d.path)} 的权限">${icon("lock")}</button><button class="icon-button" data-delete-document="${esc(d.id)}" aria-label="删除 ${esc(d.path)}">${icon("trash")}</button>` : ""}</div></td></tr>`,
    )
    .join("");
  $("document-empty").hidden = docs.length > 0;
  $("document-empty").querySelector("h3").textContent = !state.user
    ? "连接后查看你的知识库"
    : state.docs.length
      ? "没有匹配的文档"
      : "为知识库添上第一份资料";
  $("document-count").textContent = state.user
    ? `共 ${docs.length} 份文档`
    : "尚未连接工作空间";
}
function renderHistory() {
  const query = $("history-search").value.trim().toLowerCase();
  const rows = state.conversations.filter((c) =>
    c.title.toLowerCase().includes(query),
  );
  $("history-list").innerHTML = rows.length
    ? rows
        .map(
          (c) =>
            `<article class="history-card"><span class="starter-icon sage">${icon("message")}</span><button data-conversation="${esc(c.id)}"><h3>${esc(c.title)}</h3><p>${modes[c.mode]} · ${timeLabel(c.updated_at)}</p></button><button class="icon-button" data-delete-conversation="${esc(c.id)}" aria-label="删除会话 ${esc(c.title)}">${icon("trash")}</button></article>`,
        )
        .join("")
    : `<div class="large-empty"><span class="empty-icon">${icon("history")}</span><h3>${query ? "没有匹配的会话" : "把有价值的思考留下来"}</h3><p>${state.user ? "完成一次对话后，会自动保存在这里。" : "连接工作空间后，你的会话会按账号保存。"}</p></div>`;
}
function markdown(el, text) {
  if (window.marked && window.DOMPurify) {
    el.innerHTML = DOMPurify.sanitize(marked.parse(text, { breaks: true }), {
      ALLOWED_TAGS: [
        "p",
        "br",
        "strong",
        "em",
        "del",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "pre",
        "code",
        "blockquote",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "hr",
      ],
      ALLOWED_ATTR: [],
    });
  } else el.textContent = text;
}
function addMessage(message, index) {
  const el = document.createElement("article");
  el.className = `message ${message.role}`;
  el.innerHTML = `<span class="message-avatar">${message.role === "assistant" ? icon("sparkles") : esc(state.user?.id[0].toUpperCase() || "你")}</span><div class="message-main"><div class="message-who">${message.role === "assistant" ? "知序 AI" : "你"}${message.role === "assistant" ? (message.sources?.some((s) => s.kind === "web") ? "<span>联网检索 · 本地回答</span>" : "<span>本地模型</span>") : ""}</div><div class="message-content"></div><div class="message-sources"></div><div class="message-actions"></div></div>`;
  const content = el.querySelector(".message-content");
  if (message.role === "assistant") {
    if (message.content) markdown(content, message.content);
    else
      content.innerHTML =
        '<div class="typing-indicator" aria-label="正在生成"><span></span><span></span><span></span></div>';
  } else content.textContent = message.content;
  const sources = message.sources || [];
  el.querySelector(".message-sources").innerHTML = sources
    .map(
      (s) =>
        `<button class="source-chip" data-source="${esc(s.web_id ? "web:" + s.web_id : s.chunk_id)}">[${s.id}] ${esc(s.path)}</button>`,
    )
    .join("");
  if (message.content)
    el.querySelector(".message-actions").innerHTML =
      `<button class="icon-button" data-copy-message="${index}" aria-label="复制消息">${icon("copy")}</button>`;
  $("messages").append(el);
  return el;
}
function renderMessages() {
  const hasMessages = state.messages.length > 0;
  $("welcome").hidden = hasMessages;
  $("starter-section").hidden = hasMessages;
  $("conversation-heading").hidden = !hasMessages;
  $("conversation-title").textContent =
    state.conversation?.title ||
    state.messages.find((m) => m.role === "user")?.content.slice(0, 30) ||
    "新的对话";
  $("messages").replaceChildren();
  state.messages.forEach(addMessage);
}
function renderSourceRail(sources) {
  $("source-rail").innerHTML = sources.length
    ? `<h3>本次参考来源 <span class="badge">${sources.length}</span></h3><p>点击查看原文，核对答案中的引用。</p>${sources.map((s) => `<button class="source-card" data-source="${esc(s.web_id ? "web:" + s.web_id : s.chunk_id)}"><small>来源 ${s.id}</small><strong>${esc(s.path)}</strong><span>${esc(s.kind === "web" ? (s.coverage === "page" ? "网页正文节选" : "仅搜索摘要") : s.title || "查看资料片段")} ↗</span></button>`).join("")}`
    : `<h3>每个答案，都有来处</h3><p>使用知识库问答或联网搜索时，参考来源会展示在这里，方便随时核对。</p><div class="source-placeholder">${icon("quote")}<span>提问后查看参考来源</span></div>`;
}
async function saveConversation() {
  const title =
    state.conversation?.title ||
    state.messages.find((m) => m.role === "user")?.content.slice(0, 50) ||
    "新的对话";
  const saved = await getJSON(
    state.conversation
      ? `/api/conversations/${state.conversation.id}`
      : "/api/conversations",
    {
      method: state.conversation ? "PUT" : "POST",
      json: {
        title,
        messages: state.messages,
        mode: $("mode").value,
        revision: state.conversation?.revision || 0,
      },
    },
  );
  state.conversation = saved;
  state.saveFailed = false;
  await refreshData();
}
async function openConversation(id) {
  if (state.busy) {
    toast("请先停止当前回答");
    return;
  }
  if (!requireUser()) return;
  try {
    const c = await getJSON(`/api/conversations/${encodeURIComponent(id)}`);
    state.conversation = c;
    state.messages = c.messages;
    state.saveFailed = false;
    $("mode").value = c.mode;
    updateMode();
    renderMessages();
    renderSourceRail(
      c.messages.filter((m) => m.role === "assistant").at(-1)?.sources || [],
    );
    navigate("workbench");
    $("messages").scrollTop = $("messages").scrollHeight;
  } catch (e) {
    toast(e.message);
  }
}
async function sendQuestion(event) {
  event.preventDefault();
  if (state.busy || !requireUser()) return;
  const question = $("question").value.trim();
  if (!question) return;
  if (state.saveFailed) {
    toast("请先保存上一条回答，再继续对话");
    return;
  }
  const mode = $("mode").value;
  const webQuery = question;
  if (mode === "web" && (webQuery.length < 2 || webQuery.length > 300)) {
    toast("联网问题请控制在 2～300 字，当前问题将用于公开搜索");
    $("question").focus();
    return;
  }
  const previous = state.messages.map((m) => ({
    role: m.role,
    content: m.content,
  }));
  let input = [
    ...(mode === "web" ? [] : previous),
    { role: "user", content: question },
  ];
  if (input.reduce((n, m) => n + m.content.length, 0) > 16000) {
    toast("会话内容较长，请开启新对话后继续");
    return;
  }
  state.busy = true;
  state.controller = new AbortController();
  $("send-button").hidden = true;
  $("stop-button").hidden = false;
  $("mode").disabled = true;
  $("question").disabled = true;
  $("new-chat").disabled = true;
  state.messages.push(
    { role: "user", content: question, sources: [] },
    { role: "assistant", content: "", sources: [] },
  );
  renderMessages();
  const answer = state.messages.at(-1);
  const answerEl = $("messages").lastElementChild;
  const content = answerEl.querySelector(".message-content");
  $("chat-state").textContent =
    mode === "web" ? "正在联网搜索与读取网页…" : "正在检索与思考…";
  let completed = false;
  try {
    const response = await api("/v1/chat/completions", {
      method: "POST",
      json: {
        model: mode,
        messages: input,
        stream: true,
        max_tokens: 1024,
        ...(mode === "web" ? { web_query: webQuery } : {}),
      },
      signal: state.controller.signal,
    });
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "",
      lastPaint = 0;
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (raw === "[DONE]") {
            completed = true;
            continue;
          }
          const chunk = JSON.parse(raw);
          if (chunk.error) throw new Error(chunk.error.message);
          if (chunk.sources) {
            answer.sources = chunk.sources;
            renderSourceRail(answer.sources);
          }
          answer.content += (chunk.choices || [])[0]?.delta?.content || "";
          if (Date.now() - lastPaint > 70) {
            markdown(content, answer.content);
            $("messages").scrollTop = $("messages").scrollHeight;
            lastPaint = Date.now();
          }
        }
      }
      $("chat-state").textContent = "正在生成回答…";
    }
    if (!completed || !answer.content) throw new Error("回答中断，请稍后重试");
    renderMessages();
    $("question").value = "";
    $("chat-state").textContent = "回答完成 · 正在保存";
    try {
      await saveConversation();
      $("chat-state").innerHTML =
        `${icon("check")}已保存 · ${mode === "web" ? "联网检索，本地生成" : "全程本地处理"}`;
    } catch (e) {
      state.saveFailed = true;
      $("chat-state").innerHTML =
        '<button class="text-button" id="retry-save">会话未保存，点击重试</button>';
      toast("回答已完成，但保存失败：" + e.message);
    }
  } catch (e) {
    if (state.messages.at(-1) === answer) state.messages.splice(-2);
    renderMessages();
    $("chat-state").textContent =
      e.name === "AbortError" ? "已停止，未保存本次对话" : e.message;
    if (e.name !== "AbortError") toast(e.message);
  } finally {
    state.busy = false;
    state.controller = null;
    $("send-button").hidden = false;
    $("stop-button").hidden = true;
    $("mode").disabled = false;
    $("question").disabled = false;
    $("new-chat").disabled = false;
    $("messages").scrollTop = $("messages").scrollHeight;
  }
}
function groupOptions(id) {
  $(id).innerHTML =
    (state.user?.groups || [])
      .map((g) => `<option value="${esc(g)}">${esc(g)}</option>`)
      .join("") || '<option value="">未分配团队</option>';
}
function updateAccessOptions(select) {
  select.querySelector("[value=public]").disabled =
    state.user?.role !== "admin";
  select.querySelector("[value=group]").disabled = !state.user?.groups?.length;
}
function openUpload() {
  if (state.uploading) {
    toast("文档正在处理，请稍候");
    return;
  }
  if (!requireUser()) return;
  state.files = [];
  renderUploadFiles();
  $("upload-error").textContent = "";
  $("upload-files").value = "";
  $("upload-visibility").value = "private";
  $("upload-group-field").hidden = true;
  updateAccessOptions($("upload-visibility"));
  groupOptions("upload-group");
  $("upload-dialog").showModal();
}
function renderUploadFiles() {
  $("upload-file-list").innerHTML = state.files
    .map(
      (f, i) =>
        `<div class="upload-file"><strong>${esc(f.name)}</strong><span id="upload-file-state-${i}">${sizeLabel(f.size)}</span></div>`,
    )
    .join("");
}
function chooseFiles(files) {
  state.files = Array.from(files).slice(0, 10);
  renderUploadFiles();
  if (files.length > 10) toast("单次最多选择 10 个文档");
}
async function uploadFiles(event) {
  event.preventDefault();
  if (!state.files.length) {
    $("upload-error").textContent = "请先选择要上传的文档";
    return;
  }
  if (state.files.some((f) => f.size > 5 * 1024 * 1024)) {
    $("upload-error").textContent = "单个文档不能超过 5 MB";
    return;
  }
  state.uploading = true;
  $("upload-submit").disabled = true;
  $("upload-files").disabled = true;
  $("upload-visibility").disabled = true;
  $("upload-group").disabled = true;
  $("upload-error").textContent = "";
  let failures = 0;
  const successful = [];
  try {
    for (let i = 0; i < state.files.length; i++) {
      const file = state.files[i];
      const label = $(`upload-file-state-${i}`);
      label.textContent = "正在解析…";
      try {
        const params = new URLSearchParams({
          filename: file.name,
          visibility: $("upload-visibility").value,
        });
        if ($("upload-visibility").value === "group")
          params.set("workspace_id", $("upload-group").value);
        await getJSON("/api/documents?" + params, {
          method: "POST",
          body: file,
          headers: { "Content-Type": "application/octet-stream" },
        });
        label.textContent = "已建立索引";
        successful.push(file);
      } catch (e) {
        failures++;
        label.textContent = "未完成";
        $("upload-error").textContent = e.message;
      }
    }
    await refreshData();
    if (!failures) {
      $("upload-dialog").close();
      navigate("knowledge");
      toast(`${successful.length} 份文档已加入知识库`);
    } else {
      toast(`${successful.length} 份完成，${failures} 份失败`);
      state.files = state.files.filter((f) => !successful.includes(f));
      renderUploadFiles();
    }
  } finally {
    state.uploading = false;
    $("upload-submit").disabled = false;
    $("upload-files").disabled = false;
    $("upload-visibility").disabled = false;
    $("upload-group").disabled = false;
  }
}
async function openDocument(id) {
  if (!requireUser()) return;
  try {
    const doc = await getJSON(`/api/documents/${encodeURIComponent(id)}`);
    $("preview-title").textContent = doc.path;
    $("preview-meta").innerHTML =
      `${badge(doc)}<span>${doc.chunk_count} 个片段 · ${sizeLabel(doc.size)}</span>`;
    $("preview-content").innerHTML = doc.chunks
      .map(
        (c) =>
          `<div class="preview-chunk"><strong>${esc(c.title)} · 片段 ${c.ordinal + 1}</strong><pre>${esc(c.text)}</pre></div>`,
      )
      .join("");
    $("preview-actions").innerHTML =
      (doc.origin === "upload"
        ? `<button class="secondary-button" data-download="${esc(id)}">${icon("download")}下载原件</button>`
        : "") +
      `<button class="primary-button" data-ask-document="${esc(id)}">${icon("message")}向知识库提问</button>`;
    $("preview-dialog").showModal();
  } catch (e) {
    toast(e.message);
  }
}
async function openSource(chunkId) {
  try {
    if (chunkId.startsWith("web:")) {
      const c = await getJSON(
        "/api/web-sources/" + encodeURIComponent(chunkId.slice(4)),
      );
      $("preview-title").textContent = c.title;
      $("preview-meta").textContent =
        `${c.coverage === "page" ? "网页正文节选" : "仅搜索摘要"} · 发布：${c.published_at || "未提供"} · 检索：${new Date(c.retrieved_at).toLocaleString("zh-CN")}`;
      $("preview-content").innerHTML =
        `<div class="preview-chunk"><strong>${esc(c.url)}</strong><pre>${esc(c.text)}</pre></div>`;
      $("preview-actions").replaceChildren();
      const link = document.createElement("a");
      const url = new URL(c.url);
      if (["http:", "https:"].includes(url.protocol)) {
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "primary-button";
        link.textContent = "打开来源网站 ↗";
        $("preview-actions").append(link);
      }
      $("preview-dialog").showModal();
      return;
    }
    const c = await getJSON("/v1/sources/" + encodeURIComponent(chunkId));
    $("preview-title").textContent = c.path;
    $("preview-meta").textContent = c.title || "参考片段";
    $("preview-content").innerHTML =
      `<div class="preview-chunk"><strong>来源片段 ${c.ordinal + 1}</strong><pre>${esc(c.text)}</pre></div>`;
    $("preview-actions").innerHTML = "";
    $("preview-dialog").showModal();
  } catch (e) {
    toast(e.message);
  }
}
function openAccess(id) {
  const doc = state.docs.find((d) => d.id === id);
  if (!doc) return;
  state.accessDoc = doc;
  $("access-name").textContent = doc.path;
  $("access-visibility").value = doc.visibility;
  updateAccessOptions($("access-visibility"));
  groupOptions("access-group");
  if (doc.workspace_id) $("access-group").value = doc.workspace_id;
  $("access-error").textContent = "";
  $("access-dialog").showModal();
}
async function confirmAction(title, text, action) {
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = text;
  $("confirm-dialog").showModal();
  $("confirm-ok").onclick = async () => {
    try {
      await action();
      $("confirm-dialog").close();
    } catch (e) {
      toast(e.message);
    }
  };
}
async function loadStatus() {
  if (!state.user) {
    $("status-cards").innerHTML =
      '<div class="status-card"><span>服务状态</span><h3>连接后查看</h3><p>使用访问密钥获取实时状态。</p></div>';
    $("audit-list").innerHTML =
      '<p class="subtle">连接工作空间后显示操作记录。</p>';
    return;
  }
  $("refresh-status").disabled = true;
  try {
    const d = await getJSON("/api/status");
    $("members-panel").hidden = state.user?.role !== "admin";
    if (state.user?.role === "admin") {
      const members = await getJSON("/api/members");
      $("members-list").innerHTML = members.data
        .map((m) => {
          const own = m.id === state.user.id;
          return `<form class="member-row" data-member="${esc(m.id)}"><strong>${esc(m.id)}${own ? "（当前账号）" : ""}</strong><label>角色<select name="role" ${own ? "disabled" : ""}><option value="member" ${m.role === "member" ? "selected" : ""}>成员</option><option value="admin" ${m.role === "admin" ? "selected" : ""}>管理员</option></select></label><label>所属组（逗号分隔）<input name="groups" value="${esc(m.groups.join(", "))}" ${own ? "disabled" : ""} maxlength="2079" /></label><label><input type="checkbox" name="active" ${m.active ? "checked" : ""} ${own ? "disabled" : ""} />启用</label><button type="submit" class="primary-button" ${own ? "disabled" : ""}>保存</button></form>`;
        })
        .join("");
    }
    const backup = d.backup;
    $("backup-status").textContent = !backup
      ? "仅管理员可查看"
      : backup.state === "ok"
        ? "成功 · " +
          new Date(backup.last_success * 1000).toLocaleString("zh-CN")
        : backup.state === "failed"
          ? "失败 · 下次检查重试"
          : backup.state === "stale"
            ? "备份逾期 · 请检查定时任务"
            : "尚无自动备份记录";
    if (backup?.state === "ok") {
      $("backup-status").textContent += backup.cleanup_warning
        ? " · 清理异常，请检查"
        : ` · 清理 ${backup.deleted_count || 0} 份`;
    }
    $("token-budget-status").textContent = d.token_budget_enabled
      ? "已启用本地分词预算"
      : "仅字符上限";
    $("web-network-status").textContent =
      d.web_network?.label || "跟随系统设置";
    $("web-policy-status").textContent = d.web_allowed
      ? d.search_service_ready
        ? "手动搜索已可用"
        : "搜索服务未启动"
      : d.external_access
        ? "当前账号未授权"
        : "未启用";
    $("model-dot").classList.toggle("offline", !d.model_ready);
    $("status-cards").innerHTML =
      `<div class="status-card"><span>${icon("activity")}本地模型</span><h3>${d.model_ready ? "运行正常" : "暂未就绪"}</h3><p>${esc(d.model)} · 探测耗时 ${d.latency_ms} ms</p></div><div class="status-card"><span>${icon("layers")}正在生成</span><h3>${d.active} <small>/ ${d.concurrency}</small></h3><p>同时处理的生成请求</p></div><div class="status-card"><span>${icon("history")}等待队列</span><h3>${d.waiting} <small>/ ${d.queue_limit}</small></h3><p>超过预算的请求将明确提示</p></div>`;
    const actions = {
      "web.search": "完成了公开网页检索",
      "session.login": "连接了工作空间",
      "document.upload": "上传了文档",
      "document.access_changed": "更新了文档权限",
      "document.deleted": "删除了文档",
      "member.updated": "更新了成员权限",
      "key.rotated": "通过本机管理命令轮换了访问密钥",
    };
    $("audit-list").innerHTML = d.events.length
      ? d.events
          .slice(0, 8)
          .map(
            (e) =>
              `<div class="audit-row"><span class="audit-dot"></span><div><p>${esc(e.user_id)} ${actions[e.action] || esc(e.action)}</p><small>${timeLabel(e.created_at)}</small></div></div>`,
          )
          .join("")
      : '<p class="subtle">暂无操作记录</p>';
  } catch (e) {
    toast(e.message);
  } finally {
    $("refresh-status").disabled = false;
  }
}
function downloadBlob(blob, name) {
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function downloadDocument(id) {
  try {
    const doc = state.docs.find((d) => d.id === id);
    const r = await api(`/api/documents/${encodeURIComponent(id)}/download`);
    downloadBlob(await r.blob(), doc?.path || "document");
  } catch (e) {
    toast(e.message);
  }
}
function updateMode() {
  const web = $("mode").value === "web";
  $("web-query-panel").hidden = !web;
  if (!state.busy && !state.saveFailed)
    $("chat-state").textContent = web
      ? "当前问题用于联网搜索 · 本地模型总结"
      : "当前未联网 · 查网上信息请选择「联网搜索」后直接提问";
}
function confirmMemberChange(name) {
  const dialog = $("member-confirm-dialog");
  $("member-confirm-detail").textContent =
    `将更新成员 ${name} 的角色、所属组或启用状态。`;
  return new Promise((resolve) => {
    const finish = (confirmed) => {
      dialog.close();
      resolve(confirmed);
    };
    $("member-confirm-form").onsubmit = (e) => {
      e.preventDefault();
      finish(true);
    };
    $("member-confirm-cancel").onclick = () => finish(false);
    dialog.oncancel = (e) => {
      e.preventDefault();
      finish(false);
    };
    dialog.showModal();
  });
}
function wire() {
  hydrate();
  $("members-panel").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    if (!form.dataset.member) return;
    if (!(await confirmMemberChange(form.dataset.member))) return;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api("/api/members/" + encodeURIComponent(form.dataset.member), {
        method: "PATCH",
        json: {
          role: form.elements.role.value,
          groups: form.elements.groups.value
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean),
          active: form.elements.active.checked,
        },
      });
      toast("成员权限已更新");
      await loadStatus();
    } catch (e) {
      toast(e.message);
    } finally {
      button.disabled = false;
    }
  });
  $("mode").onchange = updateMode;
  document.querySelector(".brand").onclick = (e) => {
    e.preventDefault();
    navigate("workbench");
  };
  $("upload-dialog").addEventListener("cancel", (e) => {
    if (state.uploading) e.preventDefault();
  });
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("button,[data-document]");
    if (!button) return;
    if (button.dataset.view) navigate(button.dataset.view);
    if (button.dataset.close) {
      if (button.dataset.close === "upload-dialog" && state.uploading) {
        toast("文档正在处理，请稍候");
        return;
      }
      $(button.dataset.close).close();
    }
    if (button.dataset.document) openDocument(button.dataset.document);
    if (button.dataset.source) openSource(button.dataset.source);
    if (button.dataset.conversation)
      openConversation(button.dataset.conversation);
    if (button.dataset.access) openAccess(button.dataset.access);
    if (button.dataset.download) downloadDocument(button.dataset.download);
    if (button.dataset.prompt) {
      navigate("workbench");
      $("mode").value = button.dataset.mode;
      updateMode();
      $("question").value = button.dataset.prompt.replace(/\\n/g, "\n");
      $("question").focus();
    }
    if (button.dataset.askDocument) {
      const doc = state.docs.find((d) => d.id === button.dataset.askDocument);
      if (state.busy) {
        toast("请先停止当前回答");
        return;
      }
      $("preview-dialog").close();
      navigate("workbench");
      $("mode").value = "knowledge";
      updateMode();
      $("question").value =
        `根据知识库中的《${doc?.path || "文档"}》，请解释：`;
      $("question").focus();
    }
    if (button.dataset.filter) {
      state.filter = button.dataset.filter;
      document
        .querySelectorAll("[data-filter]")
        .forEach((el) => el.classList.toggle("active", el === button));
      renderLibrary();
    }
    if (button.dataset.copyMessage !== undefined) {
      try {
        await navigator.clipboard.writeText(
          state.messages[Number(button.dataset.copyMessage)].content,
        );
        toast("已复制");
      } catch {
        toast("浏览器不允许复制，请选中文字复制");
      }
    }
    if (button.dataset.deleteDocument) {
      const id = button.dataset.deleteDocument;
      const doc = state.docs.find((d) => d.id === id);
      confirmAction(
        "删除这份文档？",
        `将删除「${doc?.path}」及其索引和上传原件。已有对话不会删除，此操作不可撤销。`,
        async () => {
          await api("/api/documents/" + id, { method: "DELETE" });
          await refreshData();
          toast("文档已删除");
        },
      );
    }
    if (button.dataset.deleteConversation) {
      const id = button.dataset.deleteConversation;
      confirmAction(
        "删除这段会话？",
        "会话及其历史消息将从本机删除，此操作不可撤销。",
        async () => {
          await api("/api/conversations/" + id, { method: "DELETE" });
          if (state.conversation?.id === id) newChat();
          await refreshData();
          toast("会话已删除");
        },
      );
    }
    if (button.id === "retry-save") {
      try {
        await saveConversation();
        $("chat-state").textContent = "会话已保存";
      } catch (e) {
        toast(e.message);
      }
    }
  });
  $("new-chat").onclick = newChat;
  $("history-new").onclick = newChat;
  $("all-history").onclick = () => navigate("history");
  $("chat-form").onsubmit = sendQuestion;
  $("question").onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("chat-form").requestSubmit();
    }
  };
  $("stop-button").onclick = () => state.controller?.abort();
  $("help-button").onclick = () => $("help-dialog").showModal();
  $("mobile-menu").onclick = () => $("sidebar").classList.toggle("open");
  $("profile").onclick = async () => {
    if (!state.user) {
      requireUser();
      return;
    }
    if (state.busy) {
      toast("请先停止当前回答");
      return;
    }
    try {
      await api("/api/session", { method: "DELETE" });
      state.user = null;
      state.csrf = null;
      state.docs = [];
      state.conversations = [];
      newChat();
      renderIdentity();
      renderRecent();
      renderHome(null);
      renderLibrary();
      toast("已退出工作空间");
    } catch (e) {
      toast(e.message);
    }
  };
  $("login-form").onsubmit = async (e) => {
    e.preventDefault();
    $("login-submit").disabled = true;
    $("login-error").textContent = "";
    try {
      const d = await getJSON("/api/session", {
        method: "POST",
        headers: { Authorization: "Bearer " + $("api-key").value.trim() },
      });
      state.user = d.user;
      state.csrf = d.csrf;
      $("api-key").value = "";
      $("login-dialog").close();
      renderIdentity();
      await refreshData();
      loadStatus();
      toast("已连接工作空间");
    } catch (e) {
      $("login-error").textContent = e.message;
    } finally {
      $("login-submit").disabled = false;
    }
  };
  ["upload-button", "empty-upload", "rail-upload", "attach-button"].forEach(
    (id) => ($(id).onclick = openUpload),
  );
  $("upload-files").onchange = (e) => chooseFiles(e.target.files);
  $("upload-form").onsubmit = uploadFiles;
  $("upload-visibility").onchange = () =>
    ($("upload-group-field").hidden = $("upload-visibility").value !== "group");
  const zone = $("dropzone");
  zone.ondragover = (e) => {
    e.preventDefault();
    zone.classList.add("dragging");
  };
  zone.ondragleave = () => zone.classList.remove("dragging");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("dragging");
    if (!$("upload-submit").disabled) chooseFiles(e.dataTransfer.files);
  };
  $("document-search").oninput = renderLibrary;
  $("history-search").oninput = renderHistory;
  $("refresh-status").onclick = loadStatus;
  $("confirm-cancel").onclick = () => $("confirm-dialog").close();
  $("access-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await getJSON("/api/documents/" + state.accessDoc.id, {
        method: "PATCH",
        json: {
          visibility: $("access-visibility").value,
          workspace_id: $("access-group").value || null,
        },
      });
      $("access-dialog").close();
      await refreshData();
      toast("文档权限已更新");
    } catch (e) {
      $("access-error").textContent = e.message;
    }
  };
  $("export-chat").onclick = () => {
    if (!state.messages.length) return;
    const text = state.messages
      .map(
        (m) =>
          `## ${m.role === "user" ? "你" : "知序 AI"}\n\n${m.content}\n${(m.sources || []).map((s) => `\n[${s.id}] ${s.path}${s.kind === "web" ? " — " + s.url : ""}`).join("")}`,
      )
      .join("\n\n");
    downloadBlob(
      new Blob([text], { type: "text/markdown;charset=utf-8" }),
      (state.conversation?.title || "知序会话").replace(/[\\/:*?"<>|]/g, "_") +
        ".md",
    );
  };
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      newChat();
    }
    if (e.key === "Escape") $("sidebar").classList.remove("open");
  });
  document.addEventListener("keydown", (e) => {
    const row = e.target.closest(".home-doc");
    if (row && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      openDocument(row.dataset.document);
    }
  });
}
async function init() {
  wire();
  renderLibrary();
  renderHistory();
  try {
    const d = await getJSON("/api/me");
    state.user = d.user;
    state.csrf = d.csrf;
    renderIdentity();
    await refreshData();
    await loadStatus();
  } catch (e) {
    if (e.status !== 401) toast(e.message);
    renderIdentity();
    renderRecent();
    renderHome(null);
  }
}
init();
