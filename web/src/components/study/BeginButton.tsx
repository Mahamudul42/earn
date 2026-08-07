"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";

export function BeginButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      // Pass a recruitment source / external id if present in the URL
      // (e.g. ?source=prolific&ref=PID) so it is recorded with the participant.
      const params =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search)
          : new URLSearchParams();
      // Optional preview controls for demos: ?condition=1|2|3 and ?newsletter=<slug>
      const conditionParam = params.get("condition");
      const session = await api.startSession(
        params.get("source") || "direct",
        params.get("ref") || "",
        conditionParam ? Number(conditionParam) : undefined,
        params.get("newsletter") || undefined,
      );
      router.push(`/study/${session.public_id}`);
    } catch {
      setError("Could not start the study. Please check your connection.");
      setBusy(false);
    }
  }

  return (
    <div>
      <Button onClick={begin} disabled={busy} className="px-6 py-3 text-base">
        {busy ? <Spinner className="h-4 w-4 text-white" /> : null}
        Begin the study
        {!busy && <ArrowRight className="h-4 w-4" />}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
