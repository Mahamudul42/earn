"use client";

import { useEffect, useState } from "react";
import { ResearcherShell } from "@/components/shell/ResearcherShell";
import { Card, CardBody } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Overview } from "@/lib/types";

export default function Dashboard() {
  return (
    <ResearcherShell>
      <DashboardBody />
    </ResearcherShell>
  );
}

function DashboardBody() {
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    const token = getToken();
    if (token) api.overview(token).then(setData).catch(() => undefined);
  }, []);

  if (!data)
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <Spinner /> Loading overview…
      </div>
    );

  const stats = [
    { label: "Participants", value: data.total_participants },
    { label: "Completed", value: data.completed },
    { label: "Final responses", value: data.responses_with_final_text },
    { label: "Responses rated", value: data.responses_rated },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Study overview</h1>
        <p className="text-sm text-slate-500">
          Enrollment and rating progress across the three elicitation conditions.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardBody>
              <p className="text-sm text-slate-500">{s.label}</p>
              <p className="mt-1 text-3xl font-bold text-slate-900">{s.value}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            By condition
          </h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-2">Condition</th>
                <th className="py-2">Assigned</th>
                <th className="py-2">Completed</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.per_condition).map(([key, c]) => (
                <tr key={key} className="border-t border-slate-100">
                  <td className="py-2 font-medium text-slate-800">
                    {key}. {c.label}
                  </td>
                  <td className="py-2">{c.n}</td>
                  <td className="py-2">{c.completed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Balance across (condition × newsletter)
          </h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.cells.length === 0 && (
              <p className="text-sm text-slate-400">No participants yet.</p>
            )}
            {data.cells.map((cell) => (
              <div
                key={`${cell.condition}-${cell.newsletter__slug}`}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <span className="text-slate-600">
                  C{cell.condition} · {cell.newsletter__slug}
                </span>
                <span className="font-semibold text-slate-900">{cell.n}</span>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
