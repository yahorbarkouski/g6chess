import { Monitor, Moon, Smile, Sun } from "lucide-react";
import type { ComponentType, ReactNode, SVGProps } from "react";
import { type Theme, useTheme } from "../../hooks/useTheme";

const GITHUB_URL = "https://github.com/yahorbarkouski/g6explanation";
const FEEDBACK_URL = "mailto:admin@g6chess.com";

export function WorkspaceFooter() {
  return (
    <footer className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex items-center justify-end gap-0.5 p-1.5 text-xs backdrop-blur-sm">
      <FooterLink href={FEEDBACK_URL}>
        <Smile className="size-3.5" strokeWidth={1.75} />
      </FooterLink>
      <FooterLink external href={GITHUB_URL}>
        <GithubIcon className="size-3.5" />
      </FooterLink>
      <ThemeToggle />
    </footer>
  );
}

interface FooterLinkProps {
  children: ReactNode;
  external?: boolean;
  href: string;
}

function FooterLink({ children, external = false, href }: FooterLinkProps) {
  return (
    <a
      className="pointer-events-auto inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-stone-400 outline-none transition-colors hover:text-stone-700 dark:text-stone-600 dark:hover:text-stone-300"
      href={href}
      rel={external ? "noopener noreferrer" : undefined}
      target={external ? "_blank" : undefined}
    >
      {children}
    </a>
  );
}

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  );
}

type LucideIcon = ComponentType<SVGProps<SVGSVGElement>>;

const THEME_ICONS: Record<Theme, LucideIcon> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

const THEME_LABELS: Record<Theme, string> = {
  light: "Light theme",
  dark: "Dark theme",
  system: "System theme",
};

function ThemeToggle() {
  const { theme, cycle } = useTheme();
  const Icon = THEME_ICONS[theme];
  const label = THEME_LABELS[theme];

  return (
    <button
      aria-label={`${label}, click to switch`}
      className="pointer-events-auto inline-flex cursor-pointer items-center justify-center rounded-md px-2 py-1 text-stone-400 outline-none transition-colors hover:text-stone-700 dark:text-stone-600 dark:hover:text-stone-300"
      onClick={cycle}
      title={label}
      type="button"
    >
      <Icon className="size-3.5" strokeWidth={1.75} />
    </button>
  );
}
