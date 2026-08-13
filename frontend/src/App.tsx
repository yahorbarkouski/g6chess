import { Analytics } from "@vercel/analytics/react";
import { Toaster } from "sonner";
import { AnalysisWorkspace } from "./components/analysis/AnalysisWorkspace";

export function App() {
  return (
    <>
      <AnalysisWorkspace />
      <Toaster richColors />
      <Analytics />
    </>
  );
}
