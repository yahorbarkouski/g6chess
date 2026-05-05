import { init as initUltrachess } from "ultrachess";
import "./styles.css";

interface ReactScanRenderMetrics {
  totalRenders: number;
  latestFps: number | null;
  components: Record<
    string,
    {
      renders: number;
      latestFps: number | null;
    }
  >;
}

declare global {
  interface Window {
    __G6_REACT_SCAN_METRICS__?: ReactScanRenderMetrics;
  }
}

void bootstrap();

async function bootstrap(): Promise<void> {
  await installReactScan();

  const [{ createElement }, { createRoot }, { App }] = await Promise.all([
    import("react"),
    import("react-dom/client"),
    import("./App"),
  ]);
  const root = document.getElementById("root");

  if (root === null) {
    throw new Error("Root element #root was not found.");
  }

  await initUltrachess();
  createRoot(root).render(createElement(App));
}

async function installReactScan(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_REACT_SCAN !== "1") {
    return;
  }

  const { scan } = await import("react-scan");
  const captureMetrics = import.meta.env.VITE_REACT_SCAN_CAPTURE === "1";

  if (!captureMetrics) {
    scan({
      enabled: true,
      showFPS: true,
      showToolbar: true,
    });
    return;
  }

  const metrics: ReactScanRenderMetrics = {
    totalRenders: 0,
    latestFps: null,
    components: {},
  };
  window.__G6_REACT_SCAN_METRICS__ = metrics;

  scan({
    enabled: true,
    showFPS: true,
    showToolbar: true,
    onRender: (_fiber, renders) => {
      for (const render of renders) {
        const name = render.componentName ?? "Unknown";
        const componentMetrics = metrics.components[name] ?? {
          renders: 0,
          latestFps: null,
        };
        componentMetrics.renders += render.count;
        componentMetrics.latestFps = render.fps;
        metrics.components[name] = componentMetrics;
        metrics.totalRenders += render.count;
        metrics.latestFps = render.fps;
      }
    },
  });
}
