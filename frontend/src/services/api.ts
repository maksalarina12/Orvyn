import type {
  Asset,
  Campaign,
  CampaignExportInfo,
  CreationPlan,
  GenerationJob,
  Health,
  PlanBrief,
  PlanMeta,
  PlanPreviewItem,
  Project,
  PromptStudioBrief,
  PromptStudioMeta,
  PromptStudioPreview,
  ProviderStatus,
  Storyboard,
  StoryboardMeta,
  Workflow,
  WorkflowMeta,
} from "../types/api";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const response = await fetch(`${BASE}${path}`, {
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  config: () => request<{ app_version: string; max_upload_mb: number }>("/config"),
  projects: (params: { query?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<{ items: Project[] }>(`/projects${qs ? `?${qs}` : ""}`);
  },
  createProject: (payload: { name: string; description?: string; category?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (id: string) =>
    request<{ deleted: string }>(`/projects/${id}?confirm=true`, { method: "DELETE" }),
  asset: (id: string) => request<Asset>(`/assets/${id}`),
  assets: (params: { limit?: number; project_id?: string; file_type?: string } = {}) => {
    const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "") as [string, string][];
    const qs = new URLSearchParams(Object.fromEntries(entries)).toString();
    return request<{ items: Asset[] }>(`/assets${qs ? `?${qs}` : ""}`);
  },
  uploadAsset: (file: File, projectId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (projectId) form.append("project_id", projectId);
    return request<Asset>("/assets/upload", { method: "POST", body: form });
  },
  providers: () => request<{ items: ProviderStatus[] }>("/providers"),
  enableProvider: (id: string, payload: { enable: boolean; confirmed_external?: boolean; config?: Record<string, unknown> }) =>
    request<ProviderStatus>(`/providers/${id}/enable`, { method: "POST", body: JSON.stringify(payload) }),
  submitGeneration: (payload: {
    provider_id: string;
    mode?: string;
    prompt: string;
    negative_prompt?: string | null;
    params?: Record<string, unknown>;
    project_id?: string | null;
    source_asset_id?: string | null;
    allow_fallback?: boolean;
  }) => request<GenerationJob>("/generations", { method: "POST", body: JSON.stringify(payload) }),
  job: (id: string) => request<GenerationJob>(`/generations/${id}`),
  jobs: (params: { limit?: number } = {}) =>
    request<{ items: GenerationJob[] }>(`/generations${params.limit ? `?limit=${params.limit}` : ""}`),
  cancelJob: (id: string) =>
    request<GenerationJob>(`/generations/${id}/cancel`, { method: "POST" }),
  deleteAsset: (id: string) =>
    request<{ deleted: string }>(`/assets/${id}?confirm=true&delete_file=true`, { method: "DELETE" }),
  updateAsset: (id: string, payload: { project_id?: string; notes?: string; is_favorite?: boolean }) =>
    request<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  planMeta: () => request<PlanMeta>("/plans/meta"),
  previewPlan: (brief: PlanBrief) =>
    request<{ brief: PlanBrief; items: PlanPreviewItem[]; count: number; note: string }>("/plans/preview", {
      method: "POST",
      body: JSON.stringify(brief),
    }),
  createPlan: (brief: PlanBrief) =>
    request<CreationPlan>("/plans", { method: "POST", body: JSON.stringify(brief) }),
  plans: (params: { project_id?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<{ items: CreationPlan[] }>(`/plans${qs ? `?${qs}` : ""}`);
  },
  plan: (id: string) => request<CreationPlan>(`/plans/${id}`),
  updatePlanItem: (planId: string, itemId: string, payload: { prompt?: string; negative_prompt?: string | null; params?: Record<string, unknown> }) =>
    request<CreationPlan>(`/plans/${planId}/items/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approvePlan: (planId: string, providerId: string) =>
    request<CreationPlan>(`/plans/${planId}/approve`, {
      method: "POST",
      body: JSON.stringify({ provider_id: providerId }),
    }),
  deletePlan: (id: string) => request<{ deleted: string }>(`/plans/${id}`, { method: "DELETE" }),
  storyboardMeta: () => request<StoryboardMeta>("/storyboards/meta"),
  storyboards: (params: { project_id?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<{ items: Storyboard[] }>(`/storyboards${qs ? `?${qs}` : ""}`);
  },
  storyboard: (id: string) => request<Storyboard>(`/storyboards/${id}`),
  createStoryboard: (payload: {
    title: string;
    project_id?: string | null;
    aspect?: string;
    fps?: number;
    transition?: string;
    transition_sec?: number;
  }) => request<Storyboard>("/storyboards", { method: "POST", body: JSON.stringify(payload) }),
  updateStoryboard: (
    id: string,
    payload: {
      title?: string;
      aspect?: string;
      fps?: number;
      project_id?: string | null;
      transition?: string;
      transition_sec?: number;
      audio_asset_id?: string | null;
    }
  ) => request<Storyboard>(`/storyboards/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteStoryboard: (id: string) =>
    request<{ deleted: string }>(`/storyboards/${id}`, { method: "DELETE" }),
  addScene: (storyboardId: string, payload: { asset_id: string; duration_sec?: number; note?: string }) =>
    request<Storyboard>(`/storyboards/${storyboardId}/scenes`, { method: "POST", body: JSON.stringify(payload) }),
  updateScene: (storyboardId: string, sceneId: string, payload: { duration_sec?: number; note?: string; idx?: number }) =>
    request<Storyboard>(`/storyboards/${storyboardId}/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  removeScene: (storyboardId: string, sceneId: string) =>
    request<Storyboard>(`/storyboards/${storyboardId}/scenes/${sceneId}`, { method: "DELETE" }),
  renderStoryboard: (id: string) =>
    request<Storyboard>(`/storyboards/${id}/render`, { method: "POST" }),
  campaigns: (params: { project_id?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<{ items: Campaign[] }>(`/campaigns${qs ? `?${qs}` : ""}`);
  },
  campaign: (id: string) => request<Campaign>(`/campaigns/${id}`),
  createCampaign: (payload: { name: string; description?: string; project_id?: string | null }) =>
    request<Campaign>("/campaigns", { method: "POST", body: JSON.stringify(payload) }),
  updateCampaign: (id: string, payload: { name?: string; description?: string; status?: string; project_id?: string | null }) =>
    request<Campaign>(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteCampaign: (id: string) =>
    request<{ deleted: string }>(`/campaigns/${id}`, { method: "DELETE" }),
  addCampaignAsset: (id: string, payload: { asset_id: string; role?: string }) =>
    request<Campaign>(`/campaigns/${id}/assets`, { method: "POST", body: JSON.stringify(payload) }),
  removeCampaignAsset: (id: string, assetId: string) =>
    request<Campaign>(`/campaigns/${id}/assets/${assetId}`, { method: "DELETE" }),
  renderCampaignOverlay: (
    id: string,
    payload: { asset_id: string; text: string; position?: string; font_size?: number; color?: string }
  ) =>
    request<{ asset: Asset; campaign: Campaign }>(`/campaigns/${id}/overlay`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  exportCampaign: (id: string) =>
    request<CampaignExportInfo>(`/campaigns/${id}/export`, { method: "POST" }),
  workflowMeta: () => request<WorkflowMeta>("/workflows/meta"),
  workflows: (params: { project_id?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<{ items: Workflow[] }>(`/workflows${qs ? `?${qs}` : ""}`);
  },
  workflow: (id: string) => request<Workflow>(`/workflows/${id}`),
  createWorkflow: (payload: { name: string; description?: string; project_id?: string | null }) =>
    request<Workflow>("/workflows", { method: "POST", body: JSON.stringify(payload) }),
  deleteWorkflow: (id: string) =>
    request<{ deleted: string }>(`/workflows/${id}`, { method: "DELETE" }),
  addWorkflowStep: (id: string, payload: { kind: string; ref_id?: string | null; title?: string }) =>
    request<Workflow>(`/workflows/${id}/steps`, { method: "POST", body: JSON.stringify(payload) }),
  removeWorkflowStep: (id: string, stepId: string) =>
    request<Workflow>(`/workflows/${id}/steps/${stepId}`, { method: "DELETE" }),
  runWorkflowStep: (id: string, stepId: string, providerId?: string | null) =>
    request<Workflow>(`/workflows/${id}/steps/${stepId}/run`, {
      method: "POST",
      body: JSON.stringify({ provider_id: providerId ?? null }),
    }),
  skipWorkflowStep: (id: string, stepId: string) =>
    request<Workflow>(`/workflows/${id}/steps/${stepId}/skip`, { method: "POST" }),
  retryWorkflowStep: (id: string, stepId: string) =>
    request<Workflow>(`/workflows/${id}/steps/${stepId}/retry`, { method: "POST" }),
  promptStudioMeta: () => request<PromptStudioMeta>("/prompt-studio/meta"),
  promptStudioPreview: (brief: PromptStudioBrief) =>
    request<PromptStudioPreview>("/prompt-studio/preview", { method: "POST", body: JSON.stringify(brief) }),
};

export function assetFileUrl(id: string): string {
  return `${BASE}/assets/${id}/file`;
}
