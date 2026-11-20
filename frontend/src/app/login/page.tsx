"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Boxes, LockKeyhole, ShieldCheck, Warehouse } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-slate-950 px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(60rem 40rem at 10% -10%, rgb(79 70 229 / 0.45), transparent 60%), radial-gradient(50rem 35rem at 110% 110%, rgb(14 165 233 / 0.28), transparent 55%)",
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
              <Warehouse className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold tracking-wide">Inventory</p>
              <p className="text-xs text-slate-400">Stock &amp; Dispatch Planning</p>
            </div>
          </div>

          <h1 className="mt-20 max-w-md text-4xl leading-tight font-semibold tracking-tight">
            One clear view of stock, POs and dispatch.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-300">
            Track availability, plan dispatches on a calendar, compare stock against the schedule,
            and follow through from receipt to customer rejection.
          </p>
        </div>

        <div className="relative grid gap-4 sm:grid-cols-3">
          {[
            { icon: Boxes, label: "Live stock status" },
            { icon: ArrowRight, label: "Dispatch planning" },
            { icon: ShieldCheck, label: "Role-based access" },
          ].map(({ icon: Icon, label }) => (
            <div key={label} className="rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
              <Icon className="h-4 w-4 text-indigo-300" />
              <p className="mt-3 text-xs font-medium text-slate-200">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <Warehouse className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-slate-900">Inventory</p>
              <p className="text-xs text-slate-500">Stock &amp; Dispatch Planning</p>
            </div>
          </div>

          <div className="mb-7">
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500">Use the account provided by your administrator.</p>
          </div>

          {error && (
            <Alert tone="error" className="mb-5" onDismiss={() => setError(null)}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Username" htmlFor="username" required>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="e.g. admin"
              />
            </Field>
            <Field label="Password" htmlFor="password" required>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
              />
            </Field>

            <Button type="submit" size="lg" className="w-full justify-center" loading={submitting}>
              <LockKeyhole className="h-4 w-4" />
              Sign in
            </Button>
          </form>

          <p className="mt-8 text-center text-xs text-slate-400">
            Access is limited by role. Contact an administrator for a new account.
          </p>
        </div>
      </section>
    </div>
  );
}
