(() => {
  const API = "/api/coding-plan";
  const storeKey = "ark-coding-plan-sessions-v1";
  const ids = (name) => document.getElementById(name);
  const form = ids("chat-form"), input = ids("prompt"), messagesEl = ids("messages"), welcome = ids("welcome");
  const send = ids("send"), historyEl = ids("history"), gatewayEl = ids("gateway-state"), modelEl = ids("model-name");
  const sessions = loadSessions();
  let activeId = sessions[0]?.id || createSession();
  let isSending = false;

  function loadSessions() { try { const saved = JSON.parse(localStorage.getItem(storeKey)); return Array.isArray(saved) ? saved.slice(0, 12) : []; } catch { return []; } }
  function saveSessions() { localStorage.setItem(storeKey, JSON.stringify(sessions.slice(0, 12))); }
  function createSession() { const item = { id: crypto.randomUUID(), title: "新建编码任务", messages: [], updatedAt: Date.now() }; sessions.unshift(item); saveSessions(); return item.id; }
  function activeSession() { return sessions.find((item) => item.id === activeId); }
  function escapeHtml(value) { return value.replace(/[&<>"]/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;" })[c]); }
  function renderText(value) {
    const blocks = String(value).split(/```(?:[\w+-]+)?\n?([\s\S]*?)```/g);
    return blocks.map((part, index) => index % 2 ? `<pre><code>${escapeHtml(part.trim())}</code></pre>` : escapeHtml(part)
      .replace(/^### (.*)$/gm, "<h2>$1</h2>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>")
      .replace(/^/, "<p>").replace(/$/, "</p>")).join("");
  }
  function renderHistory() { historyEl.innerHTML = ""; sessions.forEach((session) => { const btn = document.createElement("button"); btn.textContent = session.title; btn.className = session.id === activeId ? "active" : ""; btn.onclick = () => { activeId = session.id; render(); }; historyEl.append(btn); }); }
  function messageNode(message) { const row = document.createElement("article"); row.className = `message ${message.role}`; row.innerHTML = `<div class="avatar">${message.role === "assistant" ? "&lt;/&gt;" : "YOU"}</div><div class="bubble">${renderText(message.content)}</div>`; return row; }
  function render() { const current = activeSession(); messagesEl.innerHTML = ""; const hasMessages = current?.messages?.length; welcome.hidden = Boolean(hasMessages); messagesEl.classList.toggle("visible", Boolean(hasMessages)); if (hasMessages) current.messages.forEach((message) => messagesEl.append(messageNode(message))); renderHistory(); requestAnimationFrame(() => messagesEl.parentElement.scrollTop = messagesEl.parentElement.scrollHeight); }
  function autosize() { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 180)}px`; }
  function setBusy(value) { isSending = value; send.disabled = value; send.querySelector("span").textContent = value ? "思考中" : "发送"; }
  function typingNode() { const row = document.createElement("article"); row.className = "message assistant"; row.innerHTML = '<div class="avatar">&lt;/&gt;</div><div class="bubble typing"><i></i><i></i><i></i></div>'; messagesEl.append(row); messagesEl.parentElement.scrollTop = messagesEl.parentElement.scrollHeight; return row; }
  async function sendMessage(text) {
    if (isSending || !text.trim()) return;
    const current = activeSession(); current.messages.push({ role: "user", content: text.trim() }); current.title = current.messages.find((m) => m.role === "user")?.content.slice(0, 22) || "新建编码任务"; current.updatedAt = Date.now(); saveSessions(); input.value = ""; autosize(); render(); setBusy(true);
    const typing = typingNode();
    try {
      const response = await fetch(`${API}/chat`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ messages: current.messages.slice(-20) }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.ok) throw new Error(body.detail || "请求未成功，请稍后重试。");
      current.messages.push(body.data.message); current.updatedAt = Date.now(); saveSessions();
    } catch (error) { current.messages.push({ role:"assistant", content:`### 调用未完成\n${error.message || "网络连接异常，请稍后重试。"}` }); saveSessions(); }
    typing.remove(); setBusy(false); render();
  }
  async function fetchStatus() {
    try { const response = await fetch(`${API}/status`); const body = await response.json(); const enabled = body.data?.enabled; const pulse = document.querySelector(".pulse"); gatewayEl.textContent = enabled ? "Gateway ready" : "等待服务端配置"; modelEl.textContent = enabled ? body.data.model : "未配置 API"; pulse.className = `pulse ${enabled ? "ok" : "offline"}`; } catch { gatewayEl.textContent = "状态不可用"; document.querySelector(".pulse").className = "pulse offline"; }
  }
  form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(input.value); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
  document.querySelectorAll(".prompt-card").forEach((button) => button.addEventListener("click", () => { input.value = button.dataset.prompt; autosize(); input.focus(); }));
  ids("new-chat").onclick = () => { activeId = createSession(); render(); input.focus(); };
  ids("clear-chat").onclick = () => { const current = activeSession(); if (!current || !current.messages.length) return; current.messages = []; current.title = "新建编码任务"; saveSessions(); render(); };
  document.addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); activeId = createSession(); render(); input.focus(); } });
  render(); autosize(); fetchStatus();
})();
