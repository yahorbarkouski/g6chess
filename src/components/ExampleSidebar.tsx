import { FlaskConical } from "lucide-react";
import { cn } from "../lib/utils";
import type { VisualizationExampleSummary } from "../types/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface ExampleSidebarProps {
  examples: VisualizationExampleSummary[];
  selectedExampleId: string | null;
  onSelectExample: (exampleId: string) => void;
}

export function ExampleSidebar({
  examples,
  selectedExampleId,
  onSelectExample,
}: ExampleSidebarProps) {
  return (
    <aside className="rounded-lg bg-white p-3 shadow-[0_1px_2px_rgba(68,64,60,0.08),0_10px_30px_rgba(68,64,60,0.08)] xl:sticky xl:top-4 xl:h-[calc(100dvh-2rem)] xl:overflow-auto">
      <div className="mb-3 flex items-center gap-2 px-1">
        <FlaskConical className="size-4 text-emerald-800" />
        <h2 className="font-semibold text-sm tracking-normal">Games</h2>
      </div>
      <div className="space-y-2">
        {examples.map((example) => {
          const selected = example.id === selectedExampleId;
          return (
            <Button
              aria-pressed={selected}
              className={cn(
                "h-auto w-full flex-col items-start justify-start gap-2 p-3 text-left active:scale-[0.99]",
                selected
                  ? "bg-emerald-900 text-white hover:bg-emerald-950 hover:text-white"
                  : "bg-stone-100 text-stone-950 hover:bg-stone-200",
              )}
              key={example.id}
              onClick={() => onSelectExample(example.id)}
              variant="ghost"
            >
              <span className="text-wrap pretty font-medium leading-snug">{example.title}</span>
              <span className="flex flex-wrap gap-1">
                {example.tags.map((tag) => (
                  <Badge
                    className={selected ? "bg-white/15 text-white" : undefined}
                    key={tag}
                    tone={selected ? "neutral" : "green"}
                  >
                    {tag}
                  </Badge>
                ))}
              </span>
            </Button>
          );
        })}
      </div>
    </aside>
  );
}
