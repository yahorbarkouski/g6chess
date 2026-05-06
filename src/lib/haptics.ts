import { WebHaptics } from "web-haptics";

type HapticInput = Parameters<WebHaptics["trigger"]>[0];
type HapticOptions = Parameters<WebHaptics["trigger"]>[1];

let cached: WebHaptics | null | undefined;

function getInstance(): WebHaptics | null {
  if (cached !== undefined) {
    return cached;
  }
  if (typeof window === "undefined") {
    cached = null;
    return cached;
  }
  try {
    cached = new WebHaptics();
  } catch {
    cached = null;
  }
  return cached;
}

export function triggerHaptic(input?: HapticInput, options?: HapticOptions): void {
  const instance = getInstance();
  if (instance === null) {
    return;
  }
  void instance.trigger(input, options);
}

export function warmupHaptics(): void {
  getInstance();
}
