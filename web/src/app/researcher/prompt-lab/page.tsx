"use client";

import { useCallback, useEffect, useState } from "react";
import { Play, Download, Cpu, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { ResearcherShell } from "@/components/shell/ResearcherShell";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";

type Row = { sample: string; response: string; ok: boolean; error?: string };
type Status = {
  provider: string;
  model: string;
  ok: boolean;
  error: string | null;
  has_key: boolean;
  configured: Record<string, boolean>;
};

export default function PromptLabPage() {
  return (
    <ResearcherShell>
      <PromptLab />
    </ResearcherShell>
  );
}

function PromptLab() {
  const [prompt, setPrompt] = useState("");
  const [samplesText, setSamplesText] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [runMeta, setRunMeta] = useState<{ provider: string; model: string } | null>(null);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [checking, setChecking] = useState(true);

  const checkStatus = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setChecking(true);
    try {
      setStatus(await api.promptLabStatus(token));
    } catch {
      setStatus(null);
    } finally {
      setChecking(false);
    }
  }, []);

  // Load the current prompt and model status after the client has authenticated.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;

    api
      .promptLabDefault(token)
      .then((data) => {
        if (!cancelled) setPrompt(data.system_prompt);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the current system prompt.");
      });
    api
      .promptLabStatus(token)
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const loadSamples = useCallback(async (source: "collected" | "study") => {
    const token = getToken();
    if (!token) return;
    setLoadingSamples(true);
    setError(null);
    try {
      const d = await api.promptLabSamples(token, source, 30);
      if (!d.samples.length) {
        setError(
          source === "study"
            ? "No study responses collected yet."
            : "No collected samples found.",
        );
      }
      setSamplesText(d.samples.join("\n"));
    } finally {
      setLoadingSamples(false);
    }
  }, []);

  async function run() {
    const token = getToken();
    if (!token) return;
    const samples = samplesText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!prompt.trim() || samples.length === 0) {
      setError("Add a system prompt and at least one sample.");
      return;
    }
    setRunning(true);
    setError(null);
    setRows([]);
    setRunMeta(null);
    try {
      const d = await api.promptLabRun(token, prompt, samples);
      setRows(d.results);
      setRunMeta({ provider: d.provider, model: d.model });
    } catch {
      setError("Run failed. The model API may be unreachable — try fewer samples.");
    } finally {
      setRunning(false);
    }
  }

  function exportCsv() {
    const esc = (s: string) => `"${(s ?? "").replace(/"/g, '""')}"`;
    const csv = [
      "sample,response,ok,error,provider,model",
      ...rows.map(
        (r) =>
          `${esc(r.sample)},${esc(r.response)},${r.ok},${esc(r.error ?? "")},` +
          `${esc(runMeta?.provider ?? "")},${esc(runMeta?.model ?? "")}`,
      ),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "prompt_lab_results.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const sampleCount = samplesText.split("\n").filter((s) => s.trim()).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Prompt lab</h1>
        <p className="text-sm text-slate-500">
          Try a Condition-3 system prompt against real feedback samples and compare
          the model&apos;s responses. Edit the prompt, load samples, and run.
        </p>
      </div>

      {/* Which provider/model actually answers requests right now. */}
      <Card>
        <CardBody className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="flex items-center gap-2 font-medium text-slate-700">
            <Cpu className="h-4 w-4 text-slate-400" />
            Active provider
          </span>
          {status ? (
            <>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">
                {status.provider} · {status.model}
              </span>
              {status.ok ? (
                <span className="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 className="h-4 w-4" /> live
                </span>
              ) : (
                <span className="flex items-center gap-1 text-red-600">
                  <XCircle className="h-4 w-4" />
                  {status.has_key ? "not responding" : "no API key"}
                </span>
              )}
              {!status.ok && status.error && (
                <span className="text-xs text-slate-400">{status.error}</span>
              )}
            </>
          ) : (
            <span className="text-slate-400">{checking ? "checking…" : "unknown"}</span>
          )}
          <Button
            variant="secondary"
            onClick={checkStatus}
            disabled={checking}
            className="ml-auto"
          >
            {checking ? <Spinner className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
            Recheck
          </Button>
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardBody className="space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              System prompt
            </h2>
            <Textarea
              rows={16}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="font-mono text-xs"
            />
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                Samples ({sampleCount})
              </h2>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() => loadSamples("collected")}
                  disabled={loadingSamples}
                >
                  {loadingSamples && <Spinner className="h-4 w-4" />}
                  Load collected
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => loadSamples("study")}
                  disabled={loadingSamples}
                >
                  Load study responses
                </Button>
              </div>
            </div>
            <p className="text-xs text-slate-400">One feedback sample per line.</p>
            <Textarea
              rows={13}
              value={samplesText}
              onChange={(e) => setSamplesText(e.target.value)}
              placeholder="Paste feedback samples, one per line — or load a set above."
              className="text-xs"
            />
          </CardBody>
        </Card>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex items-center gap-3">
        <Button onClick={run} disabled={running}>
          {running ? <Spinner className="h-4 w-4 text-white" /> : <Play className="h-4 w-4" />}
          Run ({Math.min(sampleCount, 25)} sample{sampleCount === 1 ? "" : "s"})
        </Button>
        {rows.length > 0 && (
          <Button variant="secondary" onClick={exportCsv}>
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
        )}
        {running && (
          <span className="text-xs text-slate-400">
            Running sequentially — this can take a little while.
          </span>
        )}
      </div>

      {rows.length > 0 && (
        <Card>
          <CardBody className="space-y-4">
            {runMeta && (
              <p className="text-xs text-slate-500">
                Answered by{" "}
                <span className="font-mono text-slate-700">
                  {runMeta.provider} · {runMeta.model}
                </span>
              </p>
            )}
            {rows.map((r, i) => (
              <div key={i} className="border-b border-slate-100 pb-3 last:border-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Sample {i + 1}
                </p>
                <p className="mt-1 text-sm text-slate-700">{r.sample}</p>
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-brand-500">
                  Response
                </p>
                <p
                  className={`mt-1 text-sm ${r.ok ? "text-slate-800" : "text-red-600"}`}
                >
                  {r.ok ? r.response : `Error: ${r.error}`}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
