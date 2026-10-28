const KEY = "orvyn.promptHistory";
const LIMIT = 8;

export function loadPromptHistory(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = JSON.parse(raw ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is string => typeof v === "string" && v.trim().length > 0).slice(0, LIMIT);
  } catch {
    return [];
  }
}

export function pushPromptHistory(prompt: string): string[] {
  const value = prompt.trim();
  if (!value) return loadPromptHistory();
  const next = [value, ...loadPromptHistory().filter((p) => p !== value)].slice(0, LIMIT);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    return next;
  }
  return next;
}

export function clearPromptHistory(): string[] {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    return [];
  }
  return [];
}
