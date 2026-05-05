import {
  AlertTriangle,
  Braces,
  CheckCircle2,
  Code2,
  Database,
  FileJson,
  Gauge,
  ShieldCheck,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import type {
  CandidateMove,
  EngineLine,
  Score,
  VisualizationExample,
  VisualizationMove,
  VisualizationMoveContext,
} from "../types/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

type InspectorTab = "output" | "evidence" | "raw";

interface ContextPanelProps {
  example: VisualizationExample | null;
  context: VisualizationMoveContext | null;
  contextState: "idle" | "building" | "ready" | "error";
  move: VisualizationMove | null;
}

export function ContextPanel({ context, contextState, example, move }: ContextPanelProps) {
  const [activeTab, setActiveTab] = useState<InspectorTab>("output");
  const rawJson = useMemo(
    () => (context === null ? "" : JSON.stringify(context.result, null, 2)),
    [context],
  );

  if (context === null) {
    return (
      <aside className="rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(68,64,60,0.08),0_10px_30px_rgba(68,64,60,0.08)] xl:sticky xl:top-4 xl:h-[calc(100dvh-2rem)] xl:overflow-auto">
        <h2 className="font-semibold text-sm tracking-normal">Context Packet</h2>
        <p className="mt-3 text-sm text-stone-600">
          {contextState === "building"
            ? "Building a fresh production context packet for this ply."
            : move === null
              ? "Initial position"
              : "No packet for this ply"}
        </p>
        {contextState === "building" && example !== null && move !== null ? (
          <p className="mt-3 break-words font-mono text-[11px] leading-5 text-stone-500">
            GET /api/visualization/examples/{example.id}/contexts/{move.ply}
          </p>
        ) : null}
      </aside>
    );
  }

  const { evidence, verification } = context.result;
  const keyCandidate = findKeyCandidate(context);

  return (
    <aside className="space-y-4 rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(68,64,60,0.08),0_10px_30px_rgba(68,64,60,0.08)] xl:sticky xl:top-4 xl:h-[calc(100dvh-2rem)] xl:overflow-auto">
      <section>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-sm tracking-normal">Context Packet</h2>
            <p className="mt-1 font-mono text-[11px] text-stone-500">
              GET /api/visualization/examples/{example?.id ?? "unknown"}/contexts/{context.ply}
            </p>
          </div>
          <Badge tone={verification.passed ? "green" : "red"}>
            <ShieldCheck className="mr-1.5 size-3.5" />
            {verification.passed ? "verified" : "blocked"}
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Metric label="quality" value={formatLabel(evidence.quality.label)} />
          <Metric label="significance" value={formatLabel(evidence.significance.label)} />
          <Metric label="beauty" value={formatLabel(evidence.beauty.label)} />
          <Metric label="ply" value={String(evidence.position.ply)} />
        </div>
      </section>

      <nav className="grid grid-cols-3 rounded-md bg-stone-100 p-1">
        {INSPECTOR_TABS.map((tab) => (
          <Button
            aria-pressed={activeTab === tab.id}
            className={activeTab === tab.id ? "bg-white shadow-sm hover:bg-white" : undefined}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            size="sm"
            variant="ghost"
          >
            <tab.icon className="size-4" />
            {tab.label}
          </Button>
        ))}
      </nav>

      {activeTab === "output" ? (
        <OutputInspector
          context={context}
          example={example}
          keyCandidate={keyCandidate}
          move={move}
        />
      ) : null}
      {activeTab === "evidence" ? (
        <EvidenceInspector context={context} keyCandidate={keyCandidate} />
      ) : null}
      {activeTab === "raw" ? <RawInspector rawJson={rawJson} /> : null}
    </aside>
  );
}

const INSPECTOR_TABS: {
  id: InspectorTab;
  label: string;
  icon: typeof Code2;
}[] = [
  { id: "output", label: "Output", icon: Code2 },
  { id: "evidence", label: "Evidence", icon: Database },
  { id: "raw", label: "Raw", icon: FileJson },
];

function OutputInspector({
  context,
  example,
  keyCandidate,
  move,
}: {
  context: VisualizationMoveContext;
  example: VisualizationExample | null;
  keyCandidate: CandidateMove | null;
  move: VisualizationMove | null;
}) {
  const { evidence, llm_context: llmContext, verification } = context.result;
  return (
    <div className="space-y-4">
      <SectionTitle icon={<Braces className="size-4" />} title="Rendered Field" />
      <PathValue path="result.llm_context.main_point" value={llmContext.main_point} />
      <PathValue path="result.evidence.main_point.concept" value={evidence.main_point.concept} />
      <PathValue path="result.evidence.main_point.claim" value={evidence.main_point.claim} />

      <section className="space-y-3">
        <SectionTitle icon={<Code2 className="size-4" />} title="Trace" />
        <div className="grid gap-2">
          <TraceDatum label="source" value={example?.source ?? "unknown"} />
          <TraceDatum label="endpoint" value={`/contexts/${context.ply}`} />
          <TraceDatum label="builder" value="MoveContextBuilder.build(...)" />
          <TraceDatum
            label="analysis"
            value={`${evidence.engine.engine_version} ${evidence.engine.analysis_budget.kind}=${String(
              evidence.engine.analysis_budget.value,
            )} multipv=${String(evidence.engine.analysis_budget.multipv)}`}
          />
          <TraceDatum label="human" value={humanEvidenceSource(evidence.candidates)} />
          <TraceDatum label="agenda" value="build_main_point(...)" />
          <TraceDatum label="frontend" value="ContextPanel -> result.llm_context.main_point" />
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<Gauge className="size-4" />} title="Why This Output" />
        <dl className="grid gap-2">
          <ContextDatum label="played move" value={move?.san ?? llmContext.played} />
          <ContextDatum
            label="quality label"
            value={`${formatLabel(evidence.quality.label)} (${formatNullableCp(
              evidence.quality.score_loss_vs_best_cp,
            )} loss vs best)`}
          />
          <ContextDatum
            label="selected key candidate"
            value={
              keyCandidate === null
                ? "none"
                : `${keyCandidate.san} / ${keyCandidate.uci} / ${formatLabel(
                    keyCandidate.practicality,
                  )}`
            }
          />
          <ContextDatum
            label="recommendation policy"
            value={formatLabel(llmContext.best_or_key_move?.recommendation_policy ?? "none")}
          />
          <ContextDatum
            label="verification"
            value={`${verification.verifier_version}: ${verification.passed ? "passed" : "failed"}`}
          />
        </dl>
      </section>
    </div>
  );
}

function EvidenceInspector({
  context,
  keyCandidate,
}: {
  context: VisualizationMoveContext;
  keyCandidate: CandidateMove | null;
}) {
  const { evidence, verification } = context.result;
  return (
    <div className="space-y-4">
      <section className="space-y-3">
        <SectionTitle icon={<Database className="size-4" />} title="Request" />
        <dl className="grid gap-2">
          <ContextDatum label="played_move" value={evidence.request.played_move ?? "none"} />
          <ContextDatum label="player_color" value={evidence.request.player_color} />
          <ContextDatum
            label="player_level"
            value={evidence.request.player_level.value.toString()}
          />
          <ContextDatum label="time_control" value={evidence.request.time_control ?? "none"} />
          <ContextDatum
            label="clock_before_seconds"
            value={String(evidence.request.clock_before_seconds ?? "none")}
          />
        </dl>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<Braces className="size-4" />} title="Position" />
        <dl className="grid gap-2">
          <ContextDatum label="fen_before" value={evidence.position.fen_before} mono />
          <ContextDatum label="fen_after" value={evidence.position.fen_after} mono />
          <ContextDatum label="side_to_move" value={evidence.position.side_to_move} />
          <ContextDatum
            label="legal_moves_uci"
            value={evidence.position.legal_moves_uci.join(" ")}
            mono
          />
        </dl>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<Gauge className="size-4" />} title="Engine Lines" />
        <div className="overflow-x-auto rounded-md bg-stone-100 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)]">
          <table className="w-full min-w-[520px] text-left text-xs">
            <thead className="text-stone-500">
              <tr>
                <Th>rank</Th>
                <Th>san</Th>
                <Th>uci</Th>
                <Th>score</Th>
                <Th>pv</Th>
              </tr>
            </thead>
            <tbody>
              {evidence.engine.top_lines.map((line) => (
                <EngineLineRow key={`${line.rank}-${line.move_uci}`} line={line} />
              ))}
              <EngineLineRow line={evidence.engine.played_line} played />
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<CheckCircle2 className="size-4" />} title="Candidates" />
        <div className="space-y-2">
          {evidence.candidates.map((candidate) => (
            <CandidateRow
              candidate={candidate}
              key={candidate.uci}
              selected={keyCandidate?.uci === candidate.uci}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<ShieldCheck className="size-4" />} title="Verification" />
        <IssueList
          emptyLabel="No verification failures or warnings."
          issues={[...verification.failures, ...verification.warnings]}
        />
      </section>
    </div>
  );
}

function RawInspector({ rawJson }: { rawJson: string }) {
  return (
    <section className="space-y-3">
      <SectionTitle icon={<FileJson className="size-4" />} title="ContextResult JSON" />
      <pre className="max-h-[calc(100dvh-16rem)] overflow-auto rounded-md bg-stone-950 p-3 font-mono text-[11px] leading-5 text-stone-100 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]">
        {rawJson}
      </pre>
    </section>
  );
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <h3 className="flex items-center gap-2 font-semibold text-sm tracking-normal text-stone-950">
      <span className="text-emerald-800">{icon}</span>
      {title}
    </h3>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-stone-100 px-3 py-2 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)]">
      <div className="font-mono text-[11px] text-stone-500">{label}</div>
      <div className="mt-1 truncate font-medium text-sm text-stone-950">{value}</div>
    </div>
  );
}

function PathValue({ path, value }: { path: string; value: string }) {
  return (
    <div className="rounded-md bg-stone-100 p-3 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)]">
      <div className="font-mono text-[11px] text-stone-500">{path}</div>
      <div className="mt-2 text-pretty text-sm leading-6 text-stone-950">{value}</div>
    </div>
  );
}

function TraceDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-2 rounded-md bg-stone-100 px-3 py-2 text-xs shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)]">
      <dt className="font-mono text-stone-500">{label}</dt>
      <dd className="truncate font-mono text-stone-900">{value}</dd>
    </div>
  );
}

function ContextDatum({
  label,
  mono = false,
  value,
}: {
  label: string;
  mono?: boolean;
  value: string;
}) {
  return (
    <div>
      <dt className="font-mono text-[11px] text-stone-500">{label}</dt>
      <dd
        className={
          mono
            ? "mt-1 break-words font-mono text-[11px] leading-5 text-stone-900"
            : "mt-1 text-pretty text-sm leading-5 text-stone-900"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function EngineLineRow({ line, played = false }: { line: EngineLine; played?: boolean }) {
  return (
    <tr className={played ? "bg-amber-100/80" : "border-stone-950/5 border-t"}>
      <Td>{played ? "played" : `#${line.rank ?? "-"}`}</Td>
      <Td strong>{line.move_san}</Td>
      <Td mono>{line.move_uci}</Td>
      <Td mono>{formatScore(line.score)}</Td>
      <Td>{line.pv_san.join(" ") || "none"}</Td>
    </tr>
  );
}

function CandidateRow({ candidate, selected }: { candidate: CandidateMove; selected: boolean }) {
  return (
    <div className="rounded-md bg-stone-100 p-3 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{candidate.san}</span>
            <span className="font-mono text-xs text-stone-500">{candidate.uci}</span>
            {selected ? <Badge tone="blue">selected key</Badge> : null}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {candidate.roles.map((role) => (
              <Badge key={role} tone="neutral">
                {formatLabel(role)}
              </Badge>
            ))}
          </div>
        </div>
        <span className="font-mono text-xs tabular-nums">{formatScore(candidate.score)}</span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <CompactDatum label="loss_cp" value={formatNullableCp(candidate.score_loss_vs_best_cp)} />
        <CompactDatum label="engine_rank" value={String(candidate.engine_rank ?? "none")} />
        <CompactDatum
          label="findability"
          value={formatLabel(candidate.time_adjusted_findability)}
        />
        <CompactDatum label="practicality" value={formatLabel(candidate.practicality)} />
        <CompactDatum
          label="player_prob"
          value={formatProbability(candidate.player_level_probability)}
        />
        <CompactDatum label="+400_prob" value={formatProbability(candidate.plus_400_probability)} />
        <CompactDatum label="policy" value={formatLabel(candidate.recommendation_policy)} wide />
      </dl>
    </div>
  );
}

function CompactDatum({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "col-span-2" : undefined}>
      <dt className="font-mono text-[11px] text-stone-500">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-[11px] text-stone-900">{value}</dd>
    </div>
  );
}

function IssueList({
  emptyLabel,
  issues,
}: {
  emptyLabel: string;
  issues: { code: string; message: string; path: string }[];
}) {
  if (issues.length === 0) {
    return (
      <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-950 shadow-[inset_0_0_0_1px_rgba(6,95,70,0.12)]">
        {emptyLabel}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {issues.map((issue) => (
        <div
          className="rounded-md bg-red-50 p-3 text-sm leading-5 text-red-950 shadow-[inset_0_0_0_1px_rgba(127,29,29,0.12)]"
          key={`${issue.path}-${issue.code}`}
        >
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4" />
            {issue.code}
          </div>
          <p className="mt-1">{issue.message}</p>
          <p className="mt-1 font-mono text-[11px] text-red-900">{issue.path}</p>
        </div>
      ))}
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="px-3 py-2 font-mono font-medium">{children}</th>;
}

function Td({
  children,
  mono = false,
  strong = false,
}: {
  children: ReactNode;
  mono?: boolean;
  strong?: boolean;
}) {
  return (
    <td
      className={[
        "px-3 py-2 align-top",
        mono ? "font-mono" : "",
        strong ? "font-semibold" : "",
      ].join(" ")}
    >
      {children}
    </td>
  );
}

function findKeyCandidate(context: VisualizationMoveContext): CandidateMove | null {
  const keyMove = context.result.llm_context.best_or_key_move?.move;
  if (keyMove === undefined) {
    return null;
  }
  return context.result.evidence.candidates.find((candidate) => candidate.san === keyMove) ?? null;
}

function formatScore(score: Score): string {
  if (score.kind === "mate") {
    return `${score.mate_for === "player" ? "+" : "-"}M${score.mate_in}`;
  }
  const value = score.value ?? 0;
  return `${value > 0 ? "+" : ""}${(value / 100).toFixed(2)}`;
}

function formatNullableCp(value: number | null): string {
  return value === null ? "none" : `${value}cp`;
}

function formatProbability(value: number | null): string {
  return value === null ? "none" : `${Math.round(value * 100)}%`;
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function humanEvidenceSource(candidates: CandidateMove[]): string {
  const source = candidates.find(
    (candidate) => candidate.findability_source !== "unknown",
  )?.findability_source;
  return source ?? "none";
}
