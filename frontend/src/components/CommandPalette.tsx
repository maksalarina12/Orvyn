import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

export interface PaletteItem {
  id: string;
  label: string;
  hint?: string;
  keywords?: string;
  run: () => void;
}

const SHORTCUTS: { keys: string; desc: string }[] = [
  { keys: "⌘K / Ctrl K", desc: "Buka command palette" },
  { keys: "⌘B / Ctrl B", desc: "Ciutkan / lebarkan rail navigasi" },
  { keys: "1 – 9", desc: "Lompat ke halaman sesuai nomor nav" },
  { keys: "⌘⏎ / Ctrl ⏎", desc: "Kirim job dari kolom prompt (Quick Generate)" },
  { keys: "?", desc: "Daftar pintasan ini" },
  { keys: "Esc", desc: "Tutup palette / dialog" },
];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

export function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const pages: PaletteItem[] = useMemo(() => {
    const go = (to: string) => () => {
      navigate(to);
      setOpen(false);
    };
    return [
      { id: "p1", label: "Dashboard", hint: "1", keywords: "home ringkasan konsol", run: go("/") },
      { id: "p2", label: "Quick Generate", hint: "2", keywords: "gambar video prompt cepat", run: go("/quick-generate") },
      { id: "p3", label: "Guided Creation", hint: "3", keywords: "angle brief rencana", run: go("/guided-creation") },
      { id: "p4", label: "Campaign Studio", hint: "4", keywords: "kampanye paket aset", run: go("/campaign-studio") },
      { id: "p5", label: "Storyboard & Video", hint: "5", keywords: "scene render animatic", run: go("/storyboard-video") },
      { id: "p6", label: "Remix & Improve", hint: "6", keywords: "revisi img2img", run: go("/remix-improve") },
      { id: "p7", label: "Projects & Assets", hint: "7", keywords: "library proyek aset upload", run: go("/projects") },
      { id: "p8", label: "Workflow Center", hint: "8", keywords: "pipeline langkah otomasi", run: go("/workflows") },
      { id: "p9", label: "Model & Backend", hint: "9", keywords: "provider kredensial health", run: go("/models") },
      {
        id: "rail",
        label: "Ciutkan / lebarkan rail navigasi",
        hint: "⌘B",
        keywords: "sidebar collapse toggle",
        run: () => {
          window.dispatchEvent(new CustomEvent("orvyn:rail-toggle"));
          setOpen(false);
        },
      },
      {
        id: "help",
        label: "Lihat semua pintasan keyboard",
        hint: "?",
        keywords: "shortcut bantuan keyboard",
        run: () => {
          setHelp(true);
        },
      },
    ];
  }, [navigate]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return pages;
    return pages.filter((p) => `${p.label} ${p.keywords ?? ""} ${p.hint ?? ""}`.toLowerCase().includes(q));
  }, [pages, query]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => {
          setHelp(false);
          setQuery("");
          setActive(0);
          return !v;
        });
        return;
      }
      if (e.key === "Escape" && (open || help)) {
        setOpen(false);
        setHelp(false);
      }
      if ((open || help) && e.key === "?" && !isTypingTarget(e.target)) {
        setHelp(true);
        setOpen(false);
      }
    };
    const onOpen = () => {
      setHelp(false);
      setQuery("");
      setActive(0);
      setOpen(true);
    };
    const onHelp = () => {
      setOpen(false);
      setHelp(true);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("orvyn:palette", onOpen);
    window.addEventListener("orvyn:help", onHelp);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("orvyn:palette", onOpen);
      window.removeEventListener("orvyn:help", onHelp);
    };
  }, [open, help]);

  useEffect(() => {
    if (open) {
      const t = window.setTimeout(() => inputRef.current?.focus(), 10);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  if (!open && !help) return null;

  const runItem = (item: PaletteItem) => {
    item.run();
  };

  return (
    <div className="palette-backdrop" onMouseDown={() => (setOpen(false), setHelp(false))}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={help ? "Pintasan keyboard" : "Command palette"}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {help ? (
          <>
            <div className="palette-head">
              <span className="palette-title">Pintasan keyboard</span>
              <button className="palette-close" onClick={() => setHelp(false)} aria-label="Tutup">
                Esc
              </button>
            </div>
            <ul className="shortcut-list">
              {SHORTCUTS.map((s) => (
                <li key={s.keys}>
                  <kbd>{s.keys}</kbd>
                  <span>{s.desc}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <div className="palette-input-row">
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive((i) => Math.min(i + 1, items.length - 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive((i) => Math.max(i - 1, 0));
                  } else if (e.key === "Enter") {
                    e.preventDefault();
                    const item = items[active];
                    if (item) runItem(item);
                  }
                }}
                placeholder="Cari halaman atau perintah…"
                aria-label="Cari halaman atau perintah"
              />
              <kbd>Esc</kbd>
            </div>
            <ul className="palette-list">
              {items.length === 0 ? <li className="palette-empty">Tidak ada hasil untuk “{query}”.</li> : null}
              {items.map((item, i) => (
                <li key={item.id}>
                  <button
                    className={i === active ? "palette-item active" : "palette-item"}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => runItem(item)}
                  >
                    <span>{item.label}</span>
                    {item.hint ? <kbd>{item.hint}</kbd> : null}
                  </button>
                </li>
              ))}
            </ul>
            <div className="palette-foot">
              <span>↑↓ pilih · ⏎ jalankan</span>
              <span>
                <kbd>?</kbd> pintasan
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function openPalette() {
  window.dispatchEvent(new CustomEvent("orvyn:palette"));
}

export function openShortcutHelp() {
  window.dispatchEvent(new CustomEvent("orvyn:help"));
}
