export function currentRoute(location) {
  if (!location) return "/";
  return `${location.pathname || "/"}${location.search || ""}${location.hash || ""}`;
}

export function isSafeInternalRoute(value) {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//");
}

export function buildReturnToState(location, extra = {}) {
  return { ...extra, returnTo: currentRoute(location) };
}

export function resolveReturnTo(location, fallback = "/") {
  const candidate = location?.state?.returnTo;
  return isSafeInternalRoute(candidate) ? candidate : fallback;
}
