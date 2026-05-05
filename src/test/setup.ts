import "@testing-library/jest-dom/vitest";

class TestStorage implements Storage {
  private readonly values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function ensureStorage(name: "localStorage" | "sessionStorage"): void {
  const existing = globalThis[name] as Storage | undefined;
  if (
    existing &&
    typeof existing.clear === "function" &&
    typeof existing.getItem === "function" &&
    typeof existing.setItem === "function"
  ) {
    return;
  }

  Object.defineProperty(globalThis, name, {
    configurable: true,
    value: new TestStorage(),
    writable: true,
  });
}

ensureStorage("localStorage");
ensureStorage("sessionStorage");
