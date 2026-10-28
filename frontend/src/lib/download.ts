import type { Asset, GenerationJob } from "../types/api";

const EXT_BY_MIME: Record<string, string> = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/webp": "webp",
  "image/gif": "gif",
  "image/bmp": "bmp",
  "video/mp4": "mp4",
  "video/webm": "webm",
  "video/quicktime": "mov",
};

export function slugify(value: string, fallback = "orvyn"): string {
  const slug = value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 42);
  return slug || fallback;
}

export function assetDownloadName(asset: Asset | null, assetId: string, job?: GenerationJob | null): string {
  const ext =
    (asset?.mime_type ? EXT_BY_MIME[asset.mime_type] : undefined) ??
    (asset?.file_type === "video" || job?.mode === "text_to_video" ? "mp4" : "webp");
  const source =
    job?.prompt ||
    asset?.prompt ||
    asset?.filename?.replace(/\.[^.]+$/, "") ||
    "hasil";
  const seed = job?.params?.seed;
  const seedPart = seed === undefined || seed === null || seed === "" ? "" : `_s${seed}`;
  return `${slugify(source)}${seedPart}_${assetId.slice(-6)}.${ext}`;
}

export function triggerDownload(href: string, filename: string): void {
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export async function downloadZip(assetIds: string[]): Promise<void> {
  const response = await fetch("/api/assets/bulk-zip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_ids: assetIds }),
  });
  if (!response.ok) {
    let detail = "Unduh zip gagal";
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* noop */
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  triggerDownload(url, `orvyn-assets-${stamp}.zip`);
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}
