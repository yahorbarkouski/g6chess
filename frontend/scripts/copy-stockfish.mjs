import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packageRoot = resolve(frontendRoot, "node_modules/stockfish");
const destination = resolve(frontendRoot, "public/stockfish");

await mkdir(destination, { recursive: true });
await Promise.all([
  copyFile(
    resolve(packageRoot, "bin/stockfish-18-single.js"),
    resolve(destination, "stockfish-18-single.js"),
  ),
  copyFile(
    resolve(packageRoot, "bin/stockfish-18-single.wasm"),
    resolve(destination, "stockfish-18-single.wasm"),
  ),
  copyFile(resolve(packageRoot, "Copying.txt"), resolve(destination, "COPYING.txt")),
  writeFile(
    resolve(destination, "SOURCE.txt"),
    [
      "Stockfish.js package: stockfish@18.0.8",
      "License: GPL-3.0",
      "Corresponding source commit:",
      "https://github.com/nmrugg/stockfish.js/tree/93c994592dcf3b4b21052ab925e9b534df9c0918",
      "",
    ].join("\n"),
  ),
]);
