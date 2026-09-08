export const importInvalidationKeys = [
  "dashboard",
  "exceptions",
  "reports",
  "commerce",
  "products",
  "shops"
];

export function hasPermission(permissions = [], permission) {
  if (permissions.includes("admin")) return true;
  return Array.isArray(permission)
    ? permission.some((candidate) => permissions.includes(candidate))
    : permissions.includes(permission);
}

export function firstAuthorizedView(nav, permissions = [], requested = "") {
  const visible = nav.filter((item) => hasPermission(permissions, item.permission));
  if (visible.some((item) => item.key === requested)) return requested;
  return visible[0]?.key || "";
}

export function createSessionLifecycle({
  cache = new Map(),
  clearStreams = () => {},
  clearCredentials = () => {},
  clearBusinessData = () => {}
} = {}) {
  let generation = 0;

  function advance() {
    generation += 1;
    return generation;
  }

  return {
    capture: () => generation,
    isCurrent: (token) => token === generation,
    applyIfCurrent(token, apply) {
      if (token !== generation) return false;
      apply();
      return true;
    },
    startSession() {
      clearStreams();
      cache.clear();
      clearBusinessData();
      return advance();
    },
    logout() {
      clearStreams();
      cache.clear();
      clearCredentials();
      clearBusinessData();
      return advance();
    },
    importSucceeded() {
      for (const key of importInvalidationKeys) cache.delete(key);
    }
  };
}
