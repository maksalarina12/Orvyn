import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { GenerationJob } from "../types/api";

type JobNotice = { job: GenerationJob };

export function useJobWatch() {
  const [active, setActive] = useState<GenerationJob[]>([]);
  const [notice, setNotice] = useState<JobNotice | null>(null);
  const seen = useRef<Map<string, string>>(new Map());
  const seeded = useRef(false);

  const poll = useCallback(async () => {
    try {
      const { items } = await api.jobs({ limit: 8 });
      setActive(items.filter((j) => j.status === "queued" || j.status === "running"));
      for (const job of items) {
        const prev = seen.current.get(job.id);
        if (seeded.current && prev && prev !== job.status) {
          if (job.status === "completed" && job.result_asset_ids.length > 0) setNotice({ job });
          if (job.status === "failed") setNotice({ job });
        }
        seen.current.set(job.id, job.status);
      }
      seeded.current = true;
    } catch {
      /* backend offline: biarkan badge kosong */
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (!alive) return;
      void poll();
    };
    tick();
    const timer = window.setInterval(tick, 5000);
    const onChange = () => tick();
    window.addEventListener("orvyn:jobs-changed", onChange);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener("orvyn:jobs-changed", onChange);
    };
  }, [poll]);

  const dismiss = useCallback(() => setNotice(null), []);

  return { active, notice, dismiss };
}
