"use client";

import { cn } from "@/lib/cn";

interface Props {
  label: string;
  name: string;
  value: number | null;
  onChange: (value: number) => void;
  /** Agree/disagree anchors (used when optionLabels is not provided). */
  lowLabel?: string;
  highLabel?: string;
  points?: number;
  /**
   * Scale-estimation option labels (one per point, e.g.
   * ["Not at all","Only a little","Somewhat","Mostly","Completely"]). When set,
   * each point renders its label instead of a number. The stored value is the
   * 1-based position.
   */
  optionLabels?: string[];
}

export function Likert({
  label,
  name,
  value,
  onChange,
  lowLabel = "Strongly disagree",
  highLabel = "Strongly agree",
  points = 5,
  optionLabels,
}: Props) {
  if (optionLabels && optionLabels.length) {
    return (
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-800">{label}</legend>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
          {optionLabels.map((opt, i) => {
            const n = i + 1;
            return (
              <button
                key={n}
                type="button"
                aria-pressed={value === n}
                onClick={() => onChange(n)}
                className={cn(
                  "rounded-lg border px-2 py-2 text-xs font-medium transition-colors",
                  value === n
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-slate-300 bg-white text-slate-600 hover:border-brand-400",
                )}
              >
                {opt}
              </button>
            );
          })}
        </div>
        <input type="hidden" name={name} value={value ?? ""} />
      </fieldset>
    );
  }

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-slate-800">{label}</legend>
      <div className="flex items-center gap-2">
        {Array.from({ length: points }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={value === n}
            onClick={() => onChange(n)}
            className={cn(
              "h-10 w-10 rounded-full border text-sm font-medium transition-colors",
              value === n
                ? "border-brand-600 bg-brand-600 text-white"
                : "border-slate-300 bg-white text-slate-600 hover:border-brand-400",
            )}
          >
            {n}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-xs text-slate-400">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
      <input type="hidden" name={name} value={value ?? ""} />
    </fieldset>
  );
}
