import { useEffect, useState } from "react";
import { AssetPreview } from "./AssetPreview";
import { assetFileUrl } from "../services/api";
import type { GenerationJob } from "../types/api";

export function JobToast({
  job,
  onDismiss,
}: {
  job: GenerationJob | null;
  onDismiss: () => void;
}) {
  const [previewJob, setPreviewJob] = useState<GenerationJob | null>(null);

  useEffect(() => {
    if (!job) return;
    const timer = window.setTimeout(onDismiss, 14000);
    return () => window.clearTimeout(timer);
  }, [job, onDismiss]);

  if (!job && !previewJob) return null;
  const completed = job?.status === "completed";
  const firstAsset = job?.result_asset_ids[0];

  return (
    <>
      {job ? (
        <aside className="job-toast" role="status" aria-live="polite">
          {completed && firstAsset ? (
            <img className="job-toast-thumb" src={assetFileUrl(firstAsset)} alt="" />
          ) : (
            <span className="job-toast-flag">{completed ? "OK" : "!"}</span>
          )}
          <div className="job-toast-body">
            <span className="job-toast-kicker">
              {completed ? "Generation selesai" : "Generation gagal"}
            </span>
            <p>{job.prompt}</p>
            <span className="job-toast-meta">
              {completed
                ? `${job.result_asset_ids.length} aset · ${job.provider_id}`
                : job.error
                  ? job.error.slice(0, 90)
                  : job.provider_id}
            </span>
          </div>
          <div className="job-toast-actions">
            {completed && firstAsset ? (
              <button
                className="btn btn-small btn-primary"
                type="button"
                onClick={() => {
                  setPreviewJob(job);
                  onDismiss();
                }}
              >
                Lihat
              </button>
            ) : null}
            <button className="btn btn-small" type="button" onClick={onDismiss}>
              Tutup
            </button>
          </div>
        </aside>
      ) : null}

      {previewJob && previewJob.result_asset_ids.length > 0 ? (
        <AssetPreview
          assetId={previewJob.result_asset_ids[0]}
          ids={previewJob.result_asset_ids}
          job={previewJob}
          onClose={() => setPreviewJob(null)}
        />
      ) : null}
    </>
  );
}
