import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Health, ProviderStatus } from "../types/api";
import { CommandPalette, openPalette, openShortcutHelp } from "../components/CommandPalette";
import { useSmoothScroll } from "../hooks/useSmoothScroll";
import { useJobWatch } from "../hooks/useJobWatch";
import { JobToast } from "../components/JobToast";

const NAV_ITEMS: { to: string; label: string; code: string; short: string }[] = [
  { to: "/", label: "Dashboard", code: "01", short: "Home" },
  { to: "/quick-generate", label: "Quick Generate", code: "02", short: "Quick" },
  { to: "/guided-creation", label: "Guided Creation", code: "03", short: "Guided" },
  { to: "/campaign-studio", label: "Campaign Studio", code: "04", short: "Campaign" },
  { to: "/storyboard-video", label: "Storyboard & Video", code: "05", short: "Video" },
  { to: "/remix-improve", label: "Remix & Improve", code: "06", short: "Remix" },
  { to: "/projects", label: "Projects & Assets", code: "07", short: "Library" },
  { to: "/workflows", label: "Workflow Center", code: "08", short: "Flow" },
  { to: "/models", label: "Model & Backend", code: "09", short: "Models" },
];

const MOBILE_ITEMS = ["/", "/quick-generate", "/projects", "/workflows", "/models"];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

export function Shell() {
  useSmoothScroll();
  const { active: activeJobs, notice: jobNotice, dismiss: dismissJobNotice } = useJobWatch();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem("orvyn.rail") === "collapsed";
    } catch {
      return false;
    }
  });
  const [health, setHealth] = useState<Health | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api
        .health()
        .then((h) => !cancelled && setHealth(h))
        .catch(() => !cancelled && setHealth(null));
      api
        .providers()
        .then((p) => !cancelled && setProviders(p.items))
        .catch(() => !cancelled && setProviders(null));
    };
    load();
    const timer = window.setInterval(load, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const onToggle = () => setCollapsed((v) => !v);
    window.addEventListener("orvyn:rail-toggle", onToggle);
    return () => window.removeEventListener("orvyn:rail-toggle", onToggle);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("orvyn.rail", collapsed ? "collapsed" : "expanded");
    } catch {
      /* noop */
    }
  }, [collapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setCollapsed((v) => !v);
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      if (document.querySelector(".palette-backdrop")) return;
      if (e.key === "?") {
        e.preventDefault();
        openShortcutHelp();
        return;
      }
      if (/^[1-9]$/.test(e.key)) {
        const item = NAV_ITEMS[Number(e.key) - 1];
        if (item) {
          e.preventDefault();
          navigate(item.to);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  const page = NAV_ITEMS.find((n) => n.to === pathname)?.label ?? "Dashboard";
  const checks = health?.checks;
  const inference = checks?.inference_backend;
  const readyProviders = (providers ?? []).filter((p) => p.enabled && p.health.ok).length;
  const enabledProviders = (providers ?? []).filter((p) => p.enabled).length;

  return (
    <div className={collapsed ? "shell is-collapsed" : "shell"}>
      <aside className="rail" aria-label="Navigasi utama">
        <div className="rail-head">
          <Link to="/" className="rail-brand" title="Dashboard">
            <span className="rail-mark">O</span>
            <span className="rail-word">Orvyn</span>
          </Link>
          <button
            className="rail-toggle"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Lebarkan navigasi (Ctrl+B)" : "Ciutkan navigasi (Ctrl+B)"}
            aria-expanded={!collapsed}
            title={collapsed ? "Lebarkan navigasi (Ctrl+B)" : "Ciutkan navigasi (Ctrl+B)"}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        <nav className="rail-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              title={`${item.label} (${Number(item.code)})`}
              className={({ isActive }) => (isActive ? "rail-link active" : "rail-link")}
            >
              <span className="rail-code">{item.code}</span>
              <span className="rail-name">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <span className="rail-stat" title={health ? `API ${health.status}` : "API offline"}>
            <span className={`dot ${health ? (health.status === "error" ? "dot-off" : "dot-ok") : "dot-off"}`} />
            <span className="rail-foot-text">{health ? health.status.toUpperCase() : "OFFLINE"}</span>
          </span>
          <span className="rail-stat mono-num" title="Provider siap / aktif">
            <span className="rail-foot-text">
              {readyProviders}/{enabledProviders || 0} PROVIDER
            </span>
          </span>
          <span className="rail-version">{health ? `v${health.app_version}` : "—"}</span>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <span className="crumb-root">ORVYN</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-page">{page}</span>
          </div>
          <div className="topbar-right">
            {activeJobs.length > 0 ? (
              <Link className="run-badge" to="/" title={activeJobs.map((j) => `${j.id} · ${j.status}`).join("\n")}>
                <span className="dot dot-warn" />
                {activeJobs.length} job
              </Link>
            ) : null}
            <button className="search-btn" onClick={openPalette} title="Cari halaman atau perintah">
              <span className="search-label">Cari / perintah</span>
              <kbd>⌘K</kbd>
            </button>
            <span className="lamp-group" title="Status runtime">
              <span className={checks?.database?.ok ? "dot dot-ok" : "dot dot-off"} title="Database" />
              <span className={checks?.ffmpeg?.ok ? "dot dot-ok" : "dot dot-off"} title="FFmpeg" />
              <span
                className={inference?.ok ? "dot dot-ok" : "dot dot-warn"}
                title={inference?.ok ? "Inference lokal siap" : "Inference lokal belum siap"}
              />
            </span>
            <button className="help-btn" onClick={openShortcutHelp} title="Pintasan keyboard (?)">
              ?
            </button>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>

        <nav className="mobile-nav" aria-label="Navigasi cepat">
          {NAV_ITEMS.filter((n) => MOBILE_ITEMS.includes(n.to)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => (isActive ? "mobile-link active" : "mobile-link")}
            >
              <span className="mobile-code">{item.code}</span>
              <span>{item.short}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <CommandPalette />
      <JobToast job={jobNotice?.job ?? null} onDismiss={dismissJobNotice} />
    </div>
  );
}
