"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, KeyRound, UserPlus } from "lucide-react";
import { ResearcherShell } from "@/components/shell/ResearcherShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { UserInfo } from "@/lib/types";

function generatedPassword() {
  return `Earn-${crypto.randomUUID().replaceAll("-", "").slice(0, 14)}!7aA`;
}

export default function RatersPage() {
  return (
    <ResearcherShell>
      <RaterAccounts />
    </ResearcherShell>
  );
}

function RaterAccounts() {
  const [raters, setRaters] = useState<UserInfo[]>([]);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [createdCredential, setCreatedCredential] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    try {
      setRaters(await api.raters(token));
      setError(null);
    } catch {
      setError("Rater accounts could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    api.raters(token)
      .then((rows) => {
        if (!cancelled) setRaters(rows);
      })
      .catch(() => {
        if (!cancelled) setError("Rater accounts could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token || !username || !password) return;
    setBusy(true);
    setError(null);
    try {
      await api.createRater(token, { username, email, password });
      setCreatedCredential(`Username: ${username}\nTemporary password: ${password}`);
      setUsername("");
      setEmail("");
      setPassword("");
      await load();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? "Could not create the account. Check username uniqueness and password strength."
          : "Could not create the account.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function setActive(rater: UserInfo, isActive: boolean) {
    const token = getToken();
    if (!token) return;
    await api.updateRater(token, rater.id, { is_active: isActive });
    await load();
  }

  async function resetPassword(rater: UserInfo) {
    const next = window.prompt(
      `Enter a new password for ${rater.username} (minimum 12 characters):`,
      generatedPassword(),
    );
    if (!next) return;
    const token = getToken();
    if (!token) return;
    try {
      await api.updateRater(token, rater.id, { password: next });
      setCreatedCredential(`Username: ${rater.username}\nNew password: ${next}`);
    } catch {
      setError("Password reset failed. Use a stronger password of at least 12 characters.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Human rater accounts</h1>
        <p className="text-sm text-slate-500">
          Give every rater a separate account. Ratings are stored with that username, and
          each rater sees only the condition-blind rating queue.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <Card>
          <CardBody>
            <h2 className="font-semibold text-slate-900">Create rater</h2>
            <form onSubmit={create} className="mt-4 space-y-3">
              <label className="block text-sm text-slate-700">
                Username
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="off"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="block text-sm text-slate-700">
                Email (optional)
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="block text-sm text-slate-700">
                Temporary password
                <div className="mt-1 flex gap-2">
                  <input
                    type="text"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    minLength={12}
                    required
                    className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs"
                  />
                  <Button type="button" variant="secondary" className="px-3" onClick={() => setPassword(generatedPassword())}>
                    Generate
                  </Button>
                </div>
              </label>
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? <Spinner className="h-4 w-4 text-white" /> : <UserPlus className="h-4 w-4" />}
                Create account
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="font-semibold text-slate-900">Raters and progress</h2>
            {loading ? <Spinner className="mt-4" /> : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-slate-500"><th className="py-2">Rater</th><th>Ratings</th><th>Last login</th><th>Status</th><th>Actions</th></tr></thead>
                  <tbody>{raters.map((rater) => (
                    <tr key={rater.id} className="border-t border-slate-100">
                      <td className="py-3"><p className="font-medium text-slate-800">{rater.username}</p><p className="text-xs text-slate-400">{rater.email || "No email"}</p></td>
                      <td className="font-semibold">{rater.rating_count}</td>
                      <td className="text-xs text-slate-500">{rater.last_login ? new Date(rater.last_login).toLocaleString() : "Never"}</td>
                      <td><Badge className={rater.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}>{rater.is_active ? "Active" : "Inactive"}</Badge></td>
                      <td><div className="flex gap-1">
                        <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => void resetPassword(rater)}><KeyRound className="h-3.5 w-3.5" /> Reset password</Button>
                        <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => void setActive(rater, !rater.is_active)}>{rater.is_active ? "Deactivate" : "Activate"}</Button>
                      </div></td>
                    </tr>
                  ))}</tbody>
                </table>
                {!raters.length && <p className="py-6 text-sm text-slate-500">No human rater accounts yet.</p>}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {createdCredential && (
        <Card className="border-amber-200 bg-amber-50">
          <CardBody className="flex flex-wrap items-center gap-3 py-4">
            <pre className="whitespace-pre-wrap text-sm text-amber-900">{createdCredential}</pre>
            <Button variant="secondary" className="ml-auto" onClick={() => void navigator.clipboard.writeText(createdCredential)}><Copy className="h-4 w-4" /> Copy credentials</Button>
            <p className="w-full text-xs text-amber-800">Share these credentials securely. They are not shown again after leaving this page.</p>
          </CardBody>
        </Card>
      )}
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    </div>
  );
}
