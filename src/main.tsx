import { createRoot } from "react-dom/client";
import { init as initUltrachess } from "ultrachess";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("Root element #root was not found.");
}

void initUltrachess().then(() => {
  createRoot(root).render(<App />);
});
