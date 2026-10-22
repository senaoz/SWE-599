import type { ReactNode } from "react";
import { ChevronDown } from "@untitledui/icons";
import { cx } from "@/utils/cx";

export const control =
  "h-9 rounded-lg bg-primary px-3 text-sm text-primary shadow-xs ring-1 ring-primary ring-inset placeholder:text-placeholder focus:outline-none focus:ring-2 focus:ring-brand";

/** A native select (keyboard and mobile pickers for free) with our own arrow, spaced from the edge. */
export function SelectField({
  label,
  value,
  onChange,
  className,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={cx("relative inline-flex", className)}>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cx(control, "w-full cursor-pointer appearance-none truncate pr-10")}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-fg-quaternary" />
    </span>
  );
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export type DatePreset = "any" | "week" | "month";

export const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: "any", label: "Any time" },
  { value: "week", label: "Past week" },
  { value: "month", label: "Past month" },
];

/** The first day a preset covers, as YYYY-MM-DD, or "" for any time. */
export function presetFromDate(preset: DatePreset): string {
  if (preset === "any") return "";
  const d = new Date();
  d.setDate(d.getDate() - (preset === "week" ? 7 : 30));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** The upper date bound to send: future-dated papers (often a journal's issue date) are hidden unless asked for. */
export function effectiveToDate(toDate: string, showFuture: boolean): string {
  if (showFuture) return toDate;
  const today = todayIso();
  return toDate && toDate < today ? toDate : today;
}
