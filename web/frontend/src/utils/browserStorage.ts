// Storage can be disabled by browser privacy settings. Keep the current tab usable.
const memory = new Map<string, string>();
export const browserStorage = {
  getItem(key: string): string | null {
    try { return window.localStorage.getItem(key); } catch { return memory.get(key) ?? null; }
  },
  setItem(key: string, value: string) {
    memory.set(key, value);
    try { window.localStorage.setItem(key, value); } catch { /* Tab-only fallback. */ }
  },
  removeItem(key: string) {
    memory.delete(key);
    try { window.localStorage.removeItem(key); } catch { /* Tab-only fallback. */ }
  },
};
