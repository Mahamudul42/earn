"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogIn, Eye, EyeOff } from "lucide-react";
import { StudyHeader } from "@/components/shell/StudyHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { saveSession } from "@/lib/auth";

export default function ResearcherLogin() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { access, refresh } = await api.login(username, password);
      saveSession(access, refresh);
      const user = await api.me(access);
      router.push(user.role === "rater" ? "/researcher/rate" : "/researcher");
    } catch {
      setError("Invalid username or password.");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <StudyHeader subtitle="Researcher dashboard" />
      <main className="mx-auto max-w-md px-4 py-12">
        <Card>
          <CardBody>
            <h1 className="text-lg font-semibold text-slate-900">
              Researcher sign in
            </h1>
            <form onSubmit={submit} className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-medium text-slate-700">
                  Username
                </label>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">
                  Password
                </label>
                <div className="relative mt-1">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 pr-10 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? <Spinner className="h-4 w-4 text-white" /> : <LogIn className="h-4 w-4" />}
                Sign in
              </Button>
            </form>
          </CardBody>
        </Card>
      </main>
    </div>
  );
}
