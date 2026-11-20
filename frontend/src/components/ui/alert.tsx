import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { cn } from "@/lib/utils";

type Tone = "error" | "success" | "info";

const styles: Record<Tone, { wrapper: string; icon: typeof Info }> = {
  error: { wrapper: "bg-rose-50 text-rose-800 ring-rose-200", icon: AlertTriangle },
  success: { wrapper: "bg-emerald-50 text-emerald-800 ring-emerald-200", icon: CheckCircle2 },
  info: { wrapper: "bg-sky-50 text-sky-800 ring-sky-200", icon: Info },
};

export function Alert({
  tone = "info",
  children,
  onDismiss,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}) {
  const { wrapper, icon: Icon } = styles[tone];
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg px-3.5 py-2.5 text-sm ring-1 ring-inset",
        wrapper,
        className,
      )}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{children}</div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
          aria-label="Dismiss message"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
