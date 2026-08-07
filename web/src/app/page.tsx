import Link from "next/link";
import { Clock, ShieldCheck } from "lucide-react";
import { StudyHeader } from "@/components/shell/StudyHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { BeginButton } from "@/components/study/BeginButton";

export default function Home() {
  return (
    <div className="min-h-screen">
      <StudyHeader />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <Card>
          <CardBody className="space-y-6">
            <div>
              <p className="text-sm font-medium text-brand-600">Research study</p>
              <h1 className="mt-1 font-serif text-3xl font-bold text-slate-900">
                How would you improve your news newsletter?
              </h1>
              <p className="mt-3 text-slate-600">
                You will read one short personalized news newsletter and write a
                few sentences about how you would like it improved for you. Then
                you will answer a brief survey. The whole task takes about{" "}
                <strong>5–8 minutes</strong>.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Feature icon={<Clock className="h-5 w-5" />} title="~5–8 minutes">
                One newsletter, a few sentences of feedback, a short survey.
              </Feature>
              <Feature
                icon={<ShieldCheck className="h-5 w-5" />}
                title="Voluntary"
              >
                Participation is voluntary and you may stop at any time.
              </Feature>
            </div>

            <BeginButton />
          </CardBody>
        </Card>

        <p className="mt-6 text-center text-xs text-slate-400">
          Researcher?{" "}
          <Link href="/researcher/login" className="text-brand-600 underline">
            Sign in to the dashboard
          </Link>
        </p>
      </main>
    </div>
  );
}

function Feature({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-2 text-brand-600">{icon}</div>
      <p className="mt-2 text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{children}</p>
    </div>
  );
}
