"use client";

import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  MessageCircleQuestion,
  Lightbulb,
  CheckCircle2,
  SendHorizonal,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import type { ChatMessage, ConditionConfig } from "@/lib/types";

interface Props {
  publicId: string;
  config: ConditionConfig;
  onComplete: () => void;
}

/* Condition 3 runs as a short conversation: the assistant asks clarifying
   questions or gives brief tips until the feedback is actionable (action
   "ok"), then the participant reviews their own words and confirms the
   submission. The assistant never rewrites the participant's feedback. */
export function FeedbackStep({ publicId, config, onComplete }: Props) {
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<"writing" | "chat">("writing");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [finalText, setFinalText] = useState("");
  const [showFinalize, setShowFinalize] = useState(false);
  const [draftLoading, setDraftLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  // Once the participant edits the draft by hand, we stop refreshing it.
  const finalDirtyRef = useRef(false);

  const seconds = () =>
    startedAt.current === null
      ? 0
      : Math.round((Date.now() - startedAt.current) / 1000);
  const userMessages = (log: ChatMessage[]) =>
    log.filter((m) => m.role === "user").map((m) => m.content);
  const followUps = chat.filter((m) => m.role === "user").length - 1;
  const lastAction = [...chat].reverse().find((m) => m.role === "assistant")?.action;

  useEffect(() => {
    startedAt.current = Date.now();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chat, busy]);

  /* Ask the backend to consolidate everything the participant said into one
     submission-ready draft. Falls back to their raw messages if it fails. */
  async function refreshDraft(log: ChatMessage[]) {
    if (finalDirtyRef.current) return;
    setDraftLoading(true);
    try {
      const res = await api.finalDraft(publicId);
      if (!finalDirtyRef.current) setFinalText(res.draft);
    } catch {
      if (!finalDirtyRef.current) setFinalText(userMessages(log).join("\n"));
    } finally {
      setDraftLoading(false);
    }
  }

  function openFinalize(log: ChatMessage[]) {
    setShowFinalize(true);
    void refreshDraft(log);
  }

  async function handleInitialSubmit() {
    if (text.trim().length < 2) {
      setError("Please write a little feedback before continuing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.submitInitial(publicId, text.trim());
      if (config.interactive && result.action !== "none") {
        const log: ChatMessage[] = [
          { role: "user", content: text.trim() },
          {
            role: "assistant",
            content: result.message,
            action: result.action as ChatMessage["action"],
          },
        ];
        setChat(log);
        setPhase("chat");
        if (result.action === "ok") openFinalize(log);
      } else {
        await api.submitFinal(publicId, text.trim(), seconds(), 0);
        onComplete();
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSend() {
    const message = draft.trim();
    if (!message || busy) return;
    setBusy(true);
    setError(null);
    const optimistic: ChatMessage[] = [...chat, { role: "user", content: message }];
    setChat(optimistic);
    setDraft("");
    try {
      const result = await api.chatTurn(publicId, message);
      const log: ChatMessage[] = [
        ...optimistic,
        {
          role: "assistant",
          content: result.message,
          action: result.action as ChatMessage["action"],
        },
      ];
      setChat(log);
      if (result.action === "ok") openFinalize(log);
      else if (showFinalize) void refreshDraft(log);
    } catch {
      setChat(chat);
      setDraft(message);
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalSubmit() {
    if (finalText.trim().length < 2) {
      setError("Please write your final feedback before submitting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.submitFinal(publicId, finalText.trim(), seconds(), Math.max(followUps, 0));
      onComplete();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardBody className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{config.prompt}</h2>
          {config.base_explanation && (
            <p className="mt-1 text-sm text-slate-600">{config.base_explanation}</p>
          )}
          {config.intro && phase === "writing" && (
            <p className="mt-2 text-sm text-slate-500">{config.intro}</p>
          )}
        </div>

        {/* Condition 2: static instruction + guidance + example */}
        {config.instruction && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p>{config.instruction}</p>
            {config.guidance && <p className="mt-2">{config.guidance}</p>}
            {config.example && (
              <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Example
                </p>
                <p className="mt-1 italic text-slate-500">{config.example}</p>
              </div>
            )}
          </div>
        )}

        {phase === "writing" && (
          <>
            <Textarea
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Write your feedback here…"
              disabled={busy}
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end">
              <Button onClick={handleInitialSubmit} disabled={busy}>
                {busy && <Spinner className="h-4 w-4 text-white" />}
                {config.interactive ? "Check with the assistant" : "Submit feedback"}
              </Button>
            </div>
          </>
        )}

        {/* Condition 3: assistant conversation */}
        {phase === "chat" && (
          <>
            <div className="rounded-lg border border-brand-200 bg-brand-50/50">
              <div className="flex items-center gap-2 border-b border-brand-100 px-4 py-2.5 text-sm font-semibold text-brand-700">
                <Sparkles className="h-4 w-4" />
                Feedback assistant
                <span className="ml-auto text-[11px] font-normal text-brand-500">
                  It helps you sharpen your feedback.
                </span>
              </div>

              <div className="max-h-96 space-y-3 overflow-y-auto px-4 py-4">
                {chat.map((m, i) =>
                  m.role === "user" ? (
                    <div key={i} className="flex justify-end">
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm text-white">
                        {m.content}
                      </div>
                    </div>
                  ) : (
                    <div key={i} className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-700 shadow-sm">
                        <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-brand-600">
                          {m.action === "ok" ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : m.action === "question" ? (
                            <MessageCircleQuestion className="h-3.5 w-3.5" />
                          ) : (
                            <Lightbulb className="h-3.5 w-3.5" />
                          )}
                          {m.action === "ok"
                            ? "Your feedback looks ready"
                            : m.action === "question"
                              ? "Question"
                              : "Suggestion"}
                        </div>
                        {m.content}
                      </div>
                    </div>
                  ),
                )}
                {busy && (
                  <div className="flex items-center gap-2 pl-1 text-xs text-slate-400">
                    <Spinner className="h-3.5 w-3.5" />
                    The assistant is reading your message…
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="border-t border-brand-100 p-3">
                <div className="flex items-end gap-2">
                  <Textarea
                    rows={2}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Reply to the assistant… (Enter to send)"
                    disabled={busy}
                    className="min-h-0 py-2"
                  />
                  <Button
                    onClick={handleSend}
                    disabled={busy || !draft.trim()}
                    aria-label="Send"
                    className="px-3"
                  >
                    <SendHorizonal className="h-4 w-4" />
                  </Button>
                </div>
                {!showFinalize && (
                  <button
                    type="button"
                    onClick={() => openFinalize(chat)}
                    className="mt-2 text-xs text-slate-500 underline hover:text-slate-700"
                  >
                    I&apos;m done — review and submit my feedback now
                  </button>
                )}
              </div>
            </div>

            {/* Confirm & submit: the participant's own words, editable. */}
            {showFinalize && (
              <div className="space-y-3 rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-green-800">
                  <CheckCircle2 className="h-4 w-4" />
                  {lastAction === "ok"
                    ? "Your feedback is ready — review and submit"
                    : "Review and submit your feedback"}
                </div>
                <p className="text-xs text-green-700">
                  Here is your complete feedback, put together from everything you
                  told the assistant. Edit it however you like, then submit. You
                  can also keep chatting above — it will be updated with what you
                  add.
                </p>
                {draftLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-white px-3.5 py-6 text-sm text-slate-500">
                    <Spinner className="h-4 w-4" />
                    Putting your feedback together…
                  </div>
                ) : (
                  <Textarea
                    rows={5}
                    value={finalText}
                    onChange={(e) => {
                      setFinalText(e.target.value);
                      finalDirtyRef.current = true;
                    }}
                    disabled={busy}
                    className="bg-white"
                  />
                )}
                <div className="flex justify-end">
                  <Button
                    onClick={handleFinalSubmit}
                    disabled={busy || draftLoading}
                  >
                    {busy && <Spinner className="h-4 w-4 text-white" />}
                    Confirm &amp; submit final feedback
                  </Button>
                </div>
              </div>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}
          </>
        )}
      </CardBody>
    </Card>
  );
}
