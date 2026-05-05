import { CircleDot } from "lucide-react";
import { cn } from "../lib/utils";
import type { VisualizationExample } from "../types/api";
import { Button } from "./ui/button";

interface MoveStripProps {
  example: VisualizationExample | null;
  selectedPly: number;
  onSelectPly: (ply: number) => void;
}

export function MoveStrip({ example, selectedPly, onSelectPly }: MoveStripProps) {
  return (
    <div className="rounded-lg bg-white p-3 shadow-[0_1px_2px_rgba(68,64,60,0.08),0_10px_30px_rgba(68,64,60,0.08)]">
      <div className="mb-3 flex items-center gap-2">
        <CircleDot className="size-4 text-emerald-800" />
        <h2 className="font-semibold text-sm tracking-normal">Move Line</h2>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          className={cn(selectedPly === 0 && "bg-emerald-900 text-white hover:bg-emerald-950")}
          onClick={() => onSelectPly(0)}
          size="sm"
          variant={selectedPly === 0 ? "primary" : "outline"}
        >
          Start
        </Button>
        {example?.moves.map((move) => {
          const selected = selectedPly === move.ply;
          const moveNumber = Math.ceil(move.ply / 2);
          const movePrefix = move.player_color === "white" ? `${moveNumber}.` : `${moveNumber}...`;
          return (
            <Button
              className={cn(
                "tabular-nums",
                selected && "bg-emerald-900 text-white hover:bg-emerald-950",
              )}
              key={move.ply}
              onClick={() => onSelectPly(move.ply)}
              size="sm"
              variant={selected ? "primary" : move.has_context ? "outline" : "ghost"}
            >
              <span className="text-xs opacity-70">{movePrefix}</span>
              {move.san}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
