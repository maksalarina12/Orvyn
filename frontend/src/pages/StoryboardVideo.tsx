import { useEffect, useState } from "react";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import type { Asset, Project, Storyboard } from "../types/api";

export function StoryboardVideo() {
  const meta = useApiState(() => api.storyboardMeta(), []);
  const projects = useApiState<{ items: Project[] }>(() => api.projects({}), []);
  const [listKey, setListKey] = useState(0);
  const storyboards = useApiState<{ items: Storyboard[] }>(() => api.storyboards({}), [listKey]);
  const [open, setOpen] = useState<Storyboard | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [fps, setFps] = useState(24);
  const [projectId, setProjectId] = useState("");
  const [transition, setTransition] = useState("cut");
  const [transitionSec, setTransitionSec] = useState(0.5);
  const [audioAssetId, setAudioAssetId] = useState("");
  const [audioKey, setAudioKey] = useState(0);
  const [uploadingAudio, setUploadingAudio] = useState(false);
  const [sceneAsset, setSceneAsset] = useState("");
  const [sceneDuration, setSceneDuration] = useState(2);
  const [sceneNote, setSceneNote] = useState("");
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshList = () => setListKey((k) => k + 1);

  const projectAssets = useApiState<{ items: Asset[] }>(
    () => api.assets({ project_id: open?.project_id ?? "", limit: 100 }),
    [open?.id, open?.project_id]
  );
  const imageAssets = (projectAssets.data?.items ?? []).filter((a) => a.file_type === "image");
  const audioAssets = useApiState<{ items: Asset[] }>(
    () => api.assets({ file_type: "audio", limit: 100 }),
    [audioKey]
  );

  useEffect(() => {
    if (!open) return;
    setTransition(open.transition ?? "cut");
    setTransitionSec(open.transition_sec ?? 0.5);
    setAudioAssetId(open.audio_asset_id ?? "");
  }, [open?.id, open?.transition, open?.transition_sec, open?.audio_asset_id]);

  const patchBoard = async (payload: {
    title?: string;
    aspect?: string;
    fps?: number;
    project_id?: string | null;
    transition?: string;
    transition_sec?: number;
    audio_asset_id?: string | null;
  }) => {
    if (!open) return;
    try {
      setOpen(await api.updateStoryboard(open.id, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan pengaturan storyboard");
    }
  };

  const uploadAudio = async (file: File) => {
    if (!open) return;
    setUploadingAudio(true);
    setError(null);
    try {
      const asset = await api.uploadAsset(file, open.project_id ?? undefined);
      setAudioKey((k) => k + 1);
      setAudioAssetId(asset.id);
      setOpen(await api.updateStoryboard(open.id, { audio_asset_id: asset.id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengunggah audio");
    } finally {
      setUploadingAudio(false);
    }
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const created = await api.createStoryboard({
        title: title.trim(),
        aspect,
        fps,
        project_id: projectId || null,
      });
      setOpen(created);
      setCreating(false);
      setTitle("");
      refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat storyboard");
    }
  };

  const openBoard = async (id: string) => {
    try {
      setOpen(await api.storyboard(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuka storyboard");
    }
  };

  const addScene = async () => {
    if (!open || !sceneAsset) return;
    try {
      setOpen(await api.addScene(open.id, { asset_id: sceneAsset, duration_sec: sceneDuration, note: sceneNote }));
      setSceneAsset("");
      setSceneNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah scene");
    }
  };

  const updateScene = async (sceneId: string, payload: { duration_sec?: number; idx?: number; note?: string }) => {
    if (!open) return;
    try {
      setOpen(await api.updateScene(open.id, sceneId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah scene");
    }
  };

  const removeScene = async (sceneId: string) => {
    if (!open) return;
    try {
      setOpen(await api.removeScene(open.id, sceneId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus scene");
    }
  };

  const render = async () => {
    if (!open || rendering) return;
    setRendering(true);
    setError(null);
    try {
      setOpen(await api.renderStoryboard(open.id));
      refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal merender animatic");
    } finally {
      setRendering(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Hapus storyboard ini?")) return;
    try {
      await api.deleteStoryboard(id);
      if (open?.id === id) setOpen(null);
      refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus storyboard");
    }
  };

  if (meta.loading) return <div className="page-loading">Loading…</div>;

  const aspects = meta.data?.aspects ?? [{ label: "16:9", width: 640, height: 360 }];
  const fpsOptions = meta.data?.fps_options ?? [12, 24, 30];
  const transitions = meta.data?.transitions ?? ["cut", "fade", "wipeleft", "slideleft", "circleopen"];
  const transitionRange = meta.data?.transition_sec_range ?? { min: 0.2, max: 2 };
  const limits = meta.data?.limits ?? { max_scenes: 30, min_scene_sec: 0.5, max_scene_sec: 10 };

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Storyboard &amp; Video</h1>
          <p>
            Keyframe gambar → animatic MP4 nyata via FFmpeg (assembly lokal). Generative video tidak tersedia di
            hardware ini — di sini yang nyata: animatic.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => {
            setCreating((c) => !c);
            setOpen(null);
          }}
        >
          {creating ? "Tutup" : "+ Storyboard baru"}
        </button>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {creating ? (
        <form className="panel create-form" onSubmit={create}>
          <label>
            Judul
            <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="mis. Teaser Launch" />
          </label>
          <label>
            Aspect
            <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
              {aspects.map((a) => (
                <option key={a.label} value={a.label}>
                  {a.label} ({a.width}×{a.height})
                </option>
              ))}
            </select>
          </label>
          <label>
            FPS
            <select value={fps} onChange={(e) => setFps(Number(e.target.value))}>
              {fpsOptions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <label>
            Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">(tanpa project)</option>
              {(projects.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" type="submit">
            Buat storyboard
          </button>
        </form>
      ) : null}

      {open ? (
        <section className="panel">
          <div className="panel-head">
            <h2>
              {open.title}{" "}
              <span className="muted small">
                ({open.aspect} • {open.fps} fps • {open.transition === "cut" ? "cut" : `${open.transition} ${Number(open.transition_sec).toFixed(1)}s`})
              </span>
            </h2>
            <div className="plan-item-status">
              <StatusPill tone="neutral">
                {open.scenes?.length ?? 0} scene • {(open.duration_total ?? 0).toFixed(1)}s
              </StatusPill>
              <StatusPill tone={open.status === "rendered" ? "ok" : "neutral"}>{open.status}</StatusPill>
            </div>
          </div>

          {open.scenes && open.scenes.length > 0 ? (
            <div className="scene-list">
              {open.scenes.map((scene, index) => (
                <div key={scene.id} className="scene-row">
                  <img
                    className="scene-thumb"
                    src={assetFileUrl(scene.asset_id)}
                    alt={scene.asset?.filename ?? scene.asset_id}
                    loading="lazy"
                  />
                  <div className="scene-info">
                    <div className="list-title">
                      Scene {index + 1} {scene.note ? <span className="muted small">— {scene.note}</span> : null}
                    </div>
                    <div className="muted small">
                      {scene.asset?.width ?? "?"}×{scene.asset?.height ?? "?"} • {scene.duration_sec.toFixed(1)}s
                    </div>
                  </div>
                  <div className="scene-actions">
                    <button className="btn" type="button" disabled={index === 0} onClick={() => updateScene(scene.id, { idx: index - 1 })}>
                      ↑
                    </button>
                    <button
                      className="btn"
                      type="button"
                      disabled={index === (open.scenes?.length ?? 1) - 1}
                      onClick={() => updateScene(scene.id, { idx: index + 1 })}
                    >
                      ↓
                    </button>
                    <button className="btn btn-danger" type="button" onClick={() => removeScene(scene.id)}>
                      Hapus
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Belum ada scene" detail="Tambahkan keyframe gambar dari project ini sebagai scene." />
          )}

          <div className="gc-approve" style={{ marginTop: 14 }}>
            <label>
              Transisi
              <select
                value={transition}
                onChange={(e) => {
                  const value = e.target.value;
                  setTransition(value);
                  void patchBoard({ transition: value });
                }}
              >
                {transitions.map((name) => (
                  <option key={name} value={name}>
                    {name === "cut" ? "Potongan langsung (cut)" : name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Durasi transisi ({transitionRange.min}–{transitionRange.max}s)
              <input
                type="number"
                min={transitionRange.min}
                max={transitionRange.max}
                step="0.1"
                value={transitionSec}
                disabled={transition === "cut"}
                onChange={(e) => setTransitionSec(Number(e.target.value))}
                onBlur={() => void patchBoard({ transition_sec: transitionSec })}
              />
            </label>
            <label>
              Audio track
              <select
                value={audioAssetId}
                onChange={(e) => {
                  const value = e.target.value;
                  setAudioAssetId(value);
                  void patchBoard({ audio_asset_id: value || null });
                }}
              >
                <option value="">— tanpa audio —</option>
                {(audioAssets.data?.items ?? []).map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Upload audio
              <input
                type="file"
                accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac"
                disabled={uploadingAudio}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void uploadAudio(file);
                  e.currentTarget.value = "";
                }}
              />
            </label>
          </div>

          <div className="gc-approve">
            <label>
              Keyframe (gambar {open.project_id ? "dari project" : "apa pun"})
              <select value={sceneAsset} onChange={(e) => setSceneAsset(e.target.value)}>
                <option value="">— pilih gambar —</option>
                {imageAssets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Durasi ({limits.min_scene_sec}–{limits.max_scene_sec}s)
              <input
                type="number"
                min={limits.min_scene_sec}
                max={limits.max_scene_sec}
                step="0.5"
                value={sceneDuration}
                onChange={(e) => setSceneDuration(Number(e.target.value))}
              />
            </label>
            <label>
              Catatan scene
              <input value={sceneNote} onChange={(e) => setSceneNote(e.target.value)} placeholder="opsional" />
            </label>
            <button className="btn btn-primary" type="button" onClick={addScene} disabled={!sceneAsset}>
              + Tambah scene
            </button>
          </div>

          <div className="gc-actions" style={{ marginTop: 14 }}>
            <button
              className="btn btn-primary"
              type="button"
              onClick={render}
              disabled={rendering || (open.scenes?.length ?? 0) === 0}
            >
              {rendering ? "Merender…" : "Render animatic (FFmpeg)"}
            </button>
            {open.output_asset_id ? (
              <span className="muted small">Hasil render tersimpan sebagai asset video di project.</span>
            ) : null}
          </div>

          {open.output_asset_id ? (
            <div className="scene-video">
              <video controls src={assetFileUrl(open.output_asset_id)} />
            </div>
          ) : null}

          <div className="gc-actions">
            <button
              className="btn"
              type="button"
              onClick={() => {
                setOpen(null);
                refreshList();
              }}
            >
              Tutup editor
            </button>
            <button className="btn btn-danger" type="button" onClick={() => remove(open.id)}>
              Hapus storyboard
            </button>
          </div>
        </section>
      ) : null}

      {storyboards.data && storyboards.data.items.length > 0 ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Storyboard tersimpan</h2>
          </div>
          <ul className="list">
            {storyboards.data.items.map((sb) => (
              <li key={sb.id} className="list-row">
                <div>
                  <div className="list-title">{sb.title}</div>
                  <div className="muted small">
                    {sb.aspect} • {sb.fps} fps • {sb.scene_count ?? 0} scene • {Number(sb.duration_total ?? 0).toFixed(1)}s •{" "}
                    {sb.status}
                  </div>
                </div>
                <div className="plan-row-actions">
                  <button className="btn" type="button" onClick={() => openBoard(sb.id)}>
                    Buka
                  </button>
                  <button className="btn btn-danger" type="button" onClick={() => remove(sb.id)}>
                    Hapus
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <EmptyState
          title="Belum ada storyboard"
          detail="Buat storyboard, tambahkan keyframe dari hasil generation atau upload, lalu render animatic MP4."
        />
      )}
    </div>
  );
}
