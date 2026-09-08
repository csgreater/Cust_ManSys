import assert from "node:assert/strict";
import test from "node:test";

import { consumeEventStream, parseSseBlock, SessionExpiredError, StreamInterruptedError } from "../src/sse.js";

test("parseSseBlock parses named unicode events", () => {
  const parsed = parseSseBlock('event: progress\ndata: {"stage":"understanding","summary":"理解问题"}');

  assert.equal(parsed.event, "progress");
  assert.equal(parsed.data.stage, "understanding");
  assert.equal(parsed.data.summary, "理解问题");
});

test("consumeEventStream handles events split across chunks", async () => {
  const encoder = new TextEncoder();
  const chunks = [
    'event: progress\ndata: {"stage":"under',
    'standing","status":"done"}\n\nevent: result\ndata: {"result":{"answer":"完成"}}\n\n'
  ];
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    }
  });
  const response = new Response(stream, { status: 200 });
  const events = [];

  await consumeEventStream(response, (event, data) => events.push({ event, data }));

  assert.deepEqual(events, [
    { event: "progress", data: { stage: "understanding", status: "done" } },
    { event: "result", data: { result: { answer: "完成" } } }
  ]);
});

test("consumeEventStream surfaces JSON error responses", async () => {
  const response = new Response(JSON.stringify({ detail: "没有权限" }), {
    status: 403,
    headers: { "content-type": "application/json" }
  });

  await assert.rejects(() => consumeEventStream(response, () => {}), /没有权限/);
});

test("consumeEventStream reports an interrupted stream when no terminal event arrives", async () => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('event: progress\ndata: {"stage":"querying","status":"running"}\n\n'));
      controller.close();
    }
  });

  await assert.rejects(
    () => consumeEventStream(new Response(stream, { status: 200 }), () => {}),
    (error) => error instanceof StreamInterruptedError && /未返回完成结果/.test(error.message)
  );
});

test("consumeEventStream identifies a 401 as an expired session", async () => {
  const response = new Response(JSON.stringify({ detail: "登录已失效" }), {
    status: 401,
    headers: { "content-type": "application/json" }
  });

  await assert.rejects(
    () => consumeEventStream(response, () => {}),
    (error) => error instanceof SessionExpiredError && error.status === 401
  );
});
