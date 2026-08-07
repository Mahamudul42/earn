"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { StudyHeader } from "@/components/shell/StudyHeader";
import { NewsletterView } from "@/components/study/NewsletterView";
import { FeedbackStep } from "@/components/study/FeedbackStep";
import { SurveyStep } from "@/components/study/SurveyStep";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { FullPageLoader } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

type Step = "consent" | "newsletter" | "survey" | "done";

export default function StudyPage() {
  const { publicId } = useParams<{ publicId: string }>();
  const [session, setSession] = useState<Session | null>(null);
  const [step, setStep] = useState<Step>("consent");
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api
      .getSession(publicId)
      .then(setSession)
      .catch(() => setNotFound(true));
  }, [publicId]);

  if (notFound) {
    return (
      <div className="min-h-screen">
        <StudyHeader />
        <main className="mx-auto max-w-3xl px-4 py-16 text-center text-slate-500">
          This study link is no longer valid.
        </main>
      </div>
    );
  }

  if (!session) return <FullPageLoader label="Preparing your newsletter…" />;

  return (
    <div className="min-h-screen pb-16">
      <StudyHeader />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <ProgressBar step={step} />

        {step === "consent" && (
          <Card>
            <CardBody className="space-y-5">
              <h1 className="text-xl font-semibold text-slate-900">
                Before you begin
              </h1>
              <div className="whitespace-pre-line text-sm leading-relaxed text-slate-600">
                {session.consent_text}
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={async () => {
                    await api.consent(publicId);
                    setStep("newsletter");
                  }}
                >
                  I agree — show me the newsletter
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Newsletter and feedback live on the SAME page, like the POPROX
            newsletter's own feedback block. */}
        {step === "newsletter" && (
          <div className="space-y-6">
            <p className="text-center text-sm text-slate-500">
              Read this newsletter as a whole — you don&apos;t need to open any
              individual article. Your feedback is at the bottom.
            </p>

            <NewsletterView newsletter={session.newsletter} />

            <div className="mx-auto max-w-[740px]">
              <FeedbackStep
                publicId={publicId}
                config={session.condition_config}
                onComplete={() => setStep("survey")}
              />
            </div>
          </div>
        )}

        {step === "survey" && (
          <SurveyStep publicId={publicId} onComplete={() => setStep("done")} />
        )}

        {step === "done" && (
          <Card>
            <CardBody className="space-y-4 text-center">
              <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
              <h1 className="text-xl font-semibold text-slate-900">
                Thank you for taking part!
              </h1>
              <p className="text-sm text-slate-600">
                Your responses have been recorded. You may now close this window.
              </p>
              <p className="text-xs text-slate-400">
                Completion code:{" "}
                <span className="font-mono text-slate-600">{publicId}</span>
              </p>
            </CardBody>
          </Card>
        )}
      </main>
    </div>
  );
}

const STEPS: { key: Step; label: string }[] = [
  { key: "consent", label: "Consent" },
  { key: "newsletter", label: "Newsletter & feedback" },
  { key: "survey", label: "Survey" },
  { key: "done", label: "Done" },
];

function ProgressBar({ step }: { step: Step }) {
  const index = STEPS.findIndex((s) => s.key === step);
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex flex-1 flex-col items-center gap-1">
          <div
            className={`h-2 w-full rounded-full ${
              i <= index ? "bg-brand-600" : "bg-slate-200"
            }`}
          />
          <span
            className={`text-[10px] ${
              i <= index ? "text-brand-700" : "text-slate-400"
            }`}
          >
            {s.label}
          </span>
        </div>
      ))}
    </div>
  );
}
