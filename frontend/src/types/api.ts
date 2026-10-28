export interface HealthCheck {
  ok: boolean;
  reason?: string;
  [key: string]: unknown;
}

export interface Health {
  status: "ok" | "degraded" | "error";
  app_version: string;
  host: string;
  checks: {
    storage: HealthCheck & { free_gb?: number; total_gb?: number };
    memory: HealthCheck & { available_gb?: number; total_gb?: number };
    ffmpeg: HealthCheck & { version?: string };
    database: HealthCheck & { path?: string };
    inference_backend: HealthCheck & {
      torch_installed?: boolean;
      diffusers_installed?: boolean;
      types?: string[];
      models?: string[];
    };
  };
}

export interface Project {
  id: string;
  name: string;
  description: string;
  category: string;
  brief: string;
  tags: string[];
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: string;
  project_id: string | null;
  path: string;
  filename: string;
  file_type: "image" | "video" | "audio";
  mime_type: string;
  width: number | null;
  height: number | null;
  file_size: number;
  source: string;
  prompt: string | null;
  notes: string;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderStatus {
  provider_id: string;
  display_name: string;
  is_external: boolean;
  enabled: boolean;
  configured: boolean;
  capabilities: {
    modes: string[];
    parameters: string[];
    limits: Record<string, unknown>;
    external?: boolean;
    config_schema?: { key: string; label: string; secret: boolean; required: boolean }[];
  };
  config_redacted: Record<string, unknown>;
  health: {
    ok: boolean;
    types?: string[];
    reason?: string;
    space_url?: string;
    version?: string;
    models?: string[];
    model?: string;
  };
  unknown?: boolean;
}

export interface GenerationJob {
  id: string;
  project_id: string | null;
  provider_id: string;
  mode: string;
  prompt: string;
  negative_prompt: string | null;
  params: Record<string, unknown>;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  attempts: number;
  max_attempts: number;
  original_provider_id: string | null;
  provider_chain: string[];
  allow_fallback: boolean;
  error: string | null;
  result_asset_ids: string[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface PlanBrief {
  product: string;
  audience?: string | null;
  tone?: string | null;
  setting?: string | null;
  benefit?: string | null;
  category: string;
  n_angles: number;
  aspect: string;
  steps: number;
  guidance: number;
  seed?: number | null;
  negative_prompt?: string | null;
  project_id?: string | null;
  title?: string | null;
}

export interface PlanItem {
  id: string;
  plan_id: string;
  idx: number;
  angle_id: string;
  angle_label: string;
  title: string;
  prompt: string;
  negative_prompt: string | null;
  params: Record<string, unknown>;
  job_id: string | null;
  status: string;
  job_status?: string | null;
  job_error?: string | null;
}

export interface CreationPlan {
  id: string;
  project_id: string | null;
  title: string;
  category: string;
  status: "draft" | "approved";
  brief: PlanBrief;
  items?: PlanItem[];
  item_count?: number;
  created_at: string;
  updated_at: string;
}

export interface PlanPreviewItem {
  angle_id: string;
  angle_label: string;
  title: string;
  prompt: string;
  negative_prompt: string;
  params: Record<string, unknown>;
}

export interface PlanMeta {
  categories: string[];
  aspects: { label: string; width: number; height: number }[];
}

export interface StoryboardSceneAsset {
  id: string;
  filename: string;
  path: string;
  width: number | null;
  height: number | null;
  file_type: string;
  prompt: string | null;
}

export interface StoryboardScene {
  id: string;
  storyboard_id: string;
  idx: number;
  asset_id: string;
  duration_sec: number;
  note: string;
  asset: StoryboardSceneAsset | null;
}

export interface StoryboardAudioAsset {
  id: string;
  filename: string;
  path: string;
  mime_type: string;
  file_size: number;
}

export interface Storyboard {
  id: string;
  project_id: string | null;
  title: string;
  aspect: string;
  fps: number;
  transition: string;
  transition_sec: number;
  audio_asset_id: string | null;
  audio_asset?: StoryboardAudioAsset | null;
  status: "draft" | "rendered";
  output_asset_id: string | null;
  scenes?: StoryboardScene[];
  duration_total?: number;
  scene_count?: number;
  created_at: string;
  updated_at: string;
}

export interface StoryboardMeta {
  aspects: { label: string; width: number; height: number }[];
  fps_options: number[];
  transitions: string[];
  transition_sec_range: { min: number; max: number };
  audio_types: string[];
  limits: { max_scenes: number; min_scene_sec: number; max_scene_sec: number };
}

export interface CampaignAsset extends Asset {
  role: string;
}

export interface Campaign {
  id: string;
  project_id: string | null;
  name: string;
  description: string;
  status: "draft" | "active" | "completed";
  assets?: CampaignAsset[];
  asset_count?: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignExportInfo {
  path: string;
  filename: string;
  file_size: number;
  asset_count: number;
}

export interface WorkflowStep {
  id: string;
  workflow_id: string;
  idx: number;
  kind: string;
  ref_id: string | null;
  title: string;
  status: "pending" | "done" | "failed" | "skipped";
  note: string;
  result?: Record<string, unknown> | null;
  ref_summary?: { title: string; status: string; item_count?: number; scene_count?: number; asset_count?: number } | null;
}

export interface Workflow {
  id: string;
  project_id: string | null;
  name: string;
  description: string;
  status: "draft" | "done";
  steps?: WorkflowStep[];
  step_count?: number;
  steps_finished?: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowMeta {
  step_kinds: { kind: string; needs_ref: string | null; description: string }[];
}

export interface PromptStudioBrief {
  subject: string;
  shot: string;
  placement: string;
  style: string;
  lighting: string;
  mood: string;
  extra: string;
  variant_mode: "styles" | "angles" | "both";
  count: number;
}

export interface PromptStudioMeta {
  shots: string[];
  placements: string[];
  styles: string[];
  lightings: string[];
  moods: string[];
  variant_modes: ("styles" | "angles" | "both")[];
  shot_labels: Record<string, string>;
}

export interface PromptVariant {
  id: string;
  label: string;
  hint: string;
  prompt: string;
}

export interface PromptStudioPreview {
  subject_anchor: string;
  base_mega_prompt: string;
  placement: string;
  variants: PromptVariant[];
}
