const AUTO_PREVIEW_KEY = "orvyn.autoPreview";

export function loadAutoPreview(): boolean {
  try {
    return window.localStorage.getItem(AUTO_PREVIEW_KEY) !== "0";
  } catch {
    return true;
  }
}

export function saveAutoPreview(value: boolean): void {
  try {
    window.localStorage.setItem(AUTO_PREVIEW_KEY, value ? "1" : "0");
  } catch {
    /* noop */
  }
}
