"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  ClipboardList,
  Download,
  LogOut,
  Newspaper,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import { FullPageLoader } from "@/components/ui/Spinner";
import type { UserInfo } from "@/lib/types";

const NAV = [
  { href: "/researcher", label: "Overview", icon: BarChart3, managerOnly: true },
  { href: "/researcher/rate", label: "Blind rating", icon: ClipboardList, managerOnly: false },
  { href: "/researcher/raters", label: "Raters", icon: Users, managerOnly: true },
];

export function ResearcherShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/researcher/login");
      return;
    }
    let cancelled = false;
    api.me(token)
      .then((currentUser) => {
        if (cancelled) return;
        setUser(currentUser);
        if (currentUser.role === "rater" && pathname !== "/researcher/rate") {
          router.replace("/researcher/rate");
          return;
        }
        setReady(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  async function downloadExport() {
    const token = getToken();
    const res = await fetch(api.exportUrl(), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "earn_export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!ready) return <FullPageLoader label="Loading dashboard…" />;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-3">
          <div className="flex items-center gap-2 text-slate-900">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Newspaper className="h-4 w-4" />
            </div>
            <span className="font-semibold">EARN Dashboard</span>
          </div>
          <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto lg:order-none lg:ml-4 lg:w-auto">
            {NAV.filter((item) => !item.managerOnly || user?.role === "manager").map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium ${
                    active
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {user?.role === "manager" && (
              <button
                onClick={downloadExport}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
              >
                <Download className="h-4 w-4" />
                Export CSV
              </button>
            )}
            <button
              onClick={() => {
                clearToken();
                router.replace("/researcher/login");
              }}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
    </div>
  );
}
