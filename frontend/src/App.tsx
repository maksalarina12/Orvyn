import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { QuickGenerate } from "./pages/QuickGenerate";
import { GuidedCreation } from "./pages/GuidedCreation";
import { CampaignStudio } from "./pages/CampaignStudio";
import { StoryboardVideo } from "./pages/StoryboardVideo";
import { RemixImprove } from "./pages/RemixImprove";
import { ProjectsAssets } from "./pages/ProjectsAssets";
import { WorkflowCenter } from "./pages/WorkflowCenter";
import { ModelSettings } from "./pages/ModelSettings";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="/quick-generate" element={<QuickGenerate />} />
        <Route path="/guided-creation" element={<GuidedCreation />} />
        <Route path="/campaign-studio" element={<CampaignStudio />} />
        <Route path="/storyboard-video" element={<StoryboardVideo />} />
        <Route path="/remix-improve" element={<RemixImprove />} />
        <Route path="/projects" element={<ProjectsAssets />} />
        <Route path="/workflows" element={<WorkflowCenter />} />
        <Route path="/models" element={<ModelSettings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
