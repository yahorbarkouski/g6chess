import { init as initUltrachess } from "ultrachess";
import "./styles.css";

void bootstrap();

async function bootstrap(): Promise<void> {
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
