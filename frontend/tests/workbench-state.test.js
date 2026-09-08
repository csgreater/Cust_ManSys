import assert from "node:assert/strict";
import test from "node:test";

import {
  createSessionLifecycle,
  firstAuthorizedView,
  importInvalidationKeys
} from "../src/workbench/state.js";

test("logout advances the session and clears streams, cached pages, credentials and business data", () => {
  const cache = new Map([["dashboard", "loaded"], ["reports", "loaded"]]);
  const effects = [];
  const lifecycle = createSessionLifecycle({
    cache,
    clearStreams: () => effects.push("streams"),
    clearCredentials: () => effects.push("credentials"),
    clearBusinessData: () => effects.push("business")
  });
  const previous = lifecycle.capture();

  lifecycle.logout();

  assert.equal(lifecycle.isCurrent(previous), false);
  assert.equal(cache.size, 0);
  assert.deepEqual(effects, ["streams", "credentials", "business"]);
});

test("a response captured before a new login cannot update the current session", () => {
  let applied = "new session";
  const lifecycle = createSessionLifecycle();
  const oldRequest = lifecycle.capture();
  lifecycle.startSession();

  const accepted = lifecycle.applyIfCurrent(oldRequest, () => { applied = "old response"; });

  assert.equal(accepted, false);
  assert.equal(applied, "new session");
});

test("a successful import invalidates every derived business view", () => {
  const cache = new Map(importInvalidationKeys.map((key) => [key, `${key}-cache`]));
  cache.set("settings", "settings-cache");
  const lifecycle = createSessionLifecycle({ cache });

  lifecycle.importSucceeded();

  assert.deepEqual([...cache.entries()], [["settings", "settings-cache"]]);
});

test("login navigation chooses the requested authorized page or the first authorized page", () => {
  const nav = [
    { key: "dashboard", permission: "view" },
    { key: "exceptions", permission: "analytics" },
    { key: "imports", permission: "import" }
  ];

  assert.equal(firstAuthorizedView(nav, ["analytics"], "imports"), "exceptions");
  assert.equal(firstAuthorizedView(nav, ["import"], "imports"), "imports");
  assert.equal(firstAuthorizedView(nav, ["admin"], "dashboard"), "dashboard");
});

test("a navigation item can be visible when any one of its permissions is granted", () => {
  const nav = [
    { key: "exceptions", permission: ["analytics", "import"] },
    { key: "reports", permission: "analytics" }
  ];

  assert.equal(firstAuthorizedView(nav, ["import"], ""), "exceptions");
});
