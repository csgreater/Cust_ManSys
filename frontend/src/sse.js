export function parseSseBlock(block) {
  let event = "message";
  const dataLines = [];
  for (const rawLine of block.split(/\r?\n/)) {
    if (rawLine.startsWith("event:")) event = rawLine.slice(6).trim();
    if (rawLine.startsWith("data:")) dataLines.push(rawLine.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) };
}

export class StreamInterruptedError extends Error {
  constructor(message = "实时分析已中断：服务未返回完成结果，请重试。") {
    super(message);
    this.name = "StreamInterruptedError";
  }
}

export class SessionExpiredError extends Error {
  constructor(message = "登录已失效，请重新登录。") {
    super(message);
    this.name = "SessionExpiredError";
    this.status = 401;
  }
}

export async function consumeEventStream(response, onEvent, { terminalEvents = ["result", "clarification", "error"] } = {}) {
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    if (response.status === 401) throw new SessionExpiredError(message);
    throw new Error(message);
  }
  if (!response.body) throw new Error("浏览器无法读取实时分析进度");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalEvent = "";
  let eventCount = 0;
  const dispatch = async (parsed) => {
    if (!parsed) return;
    eventCount += 1;
    if (terminalEvents.includes(parsed.event)) terminalEvent = parsed.event;
    await onEvent(parsed.event, parsed.data);
  };
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      await dispatch(parsed);
    }
    if (done) break;
  }
  if (buffer.trim()) {
    const parsed = parseSseBlock(buffer);
    await dispatch(parsed);
  }
  if (!terminalEvent) throw new StreamInterruptedError();
  return { terminalEvent, eventCount };
}
