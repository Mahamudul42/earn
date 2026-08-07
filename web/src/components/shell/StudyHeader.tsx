import { Newspaper } from "lucide-react";

export function StudyHeader({ subtitle }: { subtitle?: string }) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center gap-3 px-4 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
          <Newspaper className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">EARN Study</p>
          <p className="text-xs text-slate-500">
            {subtitle ?? "Newsletter feedback research"}
          </p>
        </div>
      </div>
    </header>
  );
}
