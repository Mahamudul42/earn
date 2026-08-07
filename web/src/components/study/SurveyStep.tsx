"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Likert } from "@/components/ui/Likert";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import type { SurveyAnswers } from "@/lib/types";

interface Item {
  name: keyof SurveyAnswers;
  label: string;
  options: string[]; // 5 labels, index 0 -> stored value 1
}

const DEGREE = ["Not at all", "Only a little", "Somewhat", "Mostly", "Completely"];

// Four items, each a 1–5 magnitude ("scale-estimation") question. Each measures
// a distinct construct (effort, self-efficacy, seriousness check, perceived
// actionability); construct names are for analysis and not shown to participants.
const ITEMS: Item[] = [
  {
    name: "effort",
    label: "How much effort did it take to write your feedback?",
    options: ["Very little", "A little", "A moderate amount", "Quite a bit", "A lot"],
  },
  {
    name: "express",
    label: "How much were you able to express what you wanted?",
    options: DEGREE,
  },
  {
    name: "reflect",
    label: "How much does your feedback reflect what you actually want in your newsletter?",
    options: ["Not at all", "Not much", "Somewhat", "Mostly", "Completely"],
  },
  {
    name: "understand",
    label: "How much would someone reading your feedback understand what you want changed?",
    options: DEGREE,
  },
];

export function SurveyStep({
  publicId,
  onComplete,
}: {
  publicId: string;
  onComplete: () => void;
}) {
  const [answers, setAnswers] = useState<Partial<SurveyAnswers>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (name: keyof SurveyAnswers, value: number) =>
    setAnswers((prev) => ({ ...prev, [name]: value }));

  const complete = ITEMS.every((it) => answers[it.name] != null);

  async function submit() {
    if (!complete) {
      setError("Please answer every question.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.submitSurvey(publicId, answers as SurveyAnswers);
      onComplete();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardBody className="space-y-8">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            A few quick questions
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Please answer based on your experience completing this task.
          </p>
        </div>

        <div className="space-y-6">
          {ITEMS.map((it) => (
            <Likert
              key={it.name}
              name={it.name}
              label={it.label}
              value={answers[it.name] ?? null}
              onChange={(v) => set(it.name, v)}
              optionLabels={it.options}
            />
          ))}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end">
          <Button onClick={submit} disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />}
            Finish
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
