"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { ResearcherShell } from "@/components/shell/ResearcherShell";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { BlindFeedback } from "@/lib/types";

const DIMENSIONS = [
  {
    key: "target_specificity",
    label: "Target specificity",
    help: "Topic, entity, event, geography, source type, or section to act on.",
  },
  {
    key: "direction_operation",
    label: "Direction / operation",
    help: "Include, exclude, prioritize, de-prioritize, diversify, reduce repetition, reorder.",
  },
  {
    key: "collection_allocation",
    label: "Collection allocation",
    help: "Overall mix, variety, repetition, or use of limited slots across the whole newsletter.",
  },
  {
    key: "context_persistence",
    label: "Context / persistence",
    help: "When the preference applies, how long it lasts, or what exceptions matter.",
  },
  {
    key: "system_feasibility",
    label: "System feasibility",
    help: "Can it be met using the available article pool and supported operations?",
  },
] as const;

type DimKey = (typeof DIMENSIONS)[number]["key"];

const TARGET_LEVELS = [
  { value: "article", label: "Individual article" },
  { value: "section", label: "Section" },
  { value: "collection", label: "Whole collection" },
  { value: "unclear", label: "Unclear / mixed" },
];

const emptyScores = (): Record<DimKey, number | null> => ({
  target_specificity: null,
  direction_operation: null,
  collection_allocation: null,
  context_persistence: null,
  system_feasibility: null,
});

export default function RatePage() {
  return (
    <ResearcherShell>
      <RateBody />
    </ResearcherShell>
  );
}

function RateBody() {
  const [queue, setQueue] = useState<BlindFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [scores, setScores] = useState(emptyScores());
  const [targetLevel, setTargetLevel] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    try {
      const res = await api.ratingQueue(token);
      setQueue(res.results);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;

    api
      .ratingQueue(token)
      .then((response) => {
        if (!cancelled) setQueue(response.results);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const current = queue[0];
  const total = Object.values(scores).reduce<number>(
    (sum, v) => sum + (v ?? 0),
    0,
  );
  const allScored = DIMENSIONS.every((d) => scores[d.key] != null);

  function reset() {
    setScores(emptyScores());
    setTargetLevel("");
    setNotes("");
  }

  async function submit() {
    if (!current || !allScored) return;
    const token = getToken();
    if (!token) return;
    setBusy(true);
    try {
      await api.createRating(token, current.id, {
        ...scores,
        target_level: targetLevel,
        notes,
      });
      reset();
      setQueue((q) => q.slice(1));
      if (queue.length <= 1) await load();
    } finally {
      setBusy(false);
    }
  }

  if (loading)
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <Spinner /> Loading responses…
      </div>
    );

  if (!current)
    return (
      <Card>
        <CardBody className="flex flex-col items-center gap-3 py-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-500" />
          <p className="font-medium text-slate-800">
            You have rated every available response.
          </p>
          <p className="text-sm text-slate-500">New responses will appear here.</p>
        </CardBody>
      </Card>
    );

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Response under review */}
      <Card>
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-slate-500">
              Condition and automated scores are hidden to keep this assessment blind.
            </p>
            <span className="shrink-0 text-xs text-slate-400">{queue.length} in queue</span>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Final feedback
            </p>
            <p className="mt-1 rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-800">
              {current.final_text}
            </p>
          </div>

        </CardBody>
      </Card>

      {/* Rubric */}
      <Card>
        <CardBody className="space-y-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Actionability rubric
            </h2>
            <span className="text-sm text-slate-500">
              Total <span className="font-bold text-slate-900">{total}</span> / 10
            </span>
          </div>

          {DIMENSIONS.map((dim) => (
            <div key={dim.key}>
              <p className="text-sm font-medium text-slate-800">{dim.label}</p>
              <p className="text-xs text-slate-500">{dim.help}</p>
              <div className="mt-2 flex gap-2">
                {[0, 1, 2].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() =>
                      setScores((s) => ({ ...s, [dim.key]: n }))
                    }
                    className={cn(
                      "h-9 w-12 rounded-lg border text-sm font-semibold transition-colors",
                      scores[dim.key] === n
                        ? "border-brand-600 bg-brand-600 text-white"
                        : "border-slate-300 text-slate-600 hover:border-brand-400",
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <div>
            <p className="text-sm font-medium text-slate-800">Target level</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {TARGET_LEVELS.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setTargetLevel(t.value)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs font-medium",
                    targetLevel === t.value
                      ? "border-brand-600 bg-brand-50 text-brand-700"
                      : "border-slate-300 text-slate-600 hover:border-brand-400",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <Textarea
            rows={2}
            placeholder="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setQueue((q) => q.slice(1))}>
              Skip
            </Button>
            <Button onClick={submit} disabled={!allScored || !targetLevel || busy}>
              {busy && <Spinner className="h-4 w-4 text-white" />}
              Save rating
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
