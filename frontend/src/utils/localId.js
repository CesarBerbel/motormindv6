let localIdCounter = 0;

export function makeLocalId(prefix = "local") {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  localIdCounter += 1;
  return `${prefix}-${Date.now()}-${localIdCounter}`;
}
