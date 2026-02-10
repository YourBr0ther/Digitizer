"use client";

import { useDigitizer } from "@/context/digitizer-context";

export default function DriveStatusCard() {
  const { driveStatus, activeJobProgress } = useDigitizer();

  const config = {
    empty: {
      label: "No Disc",
      color: "var(--muted)",
      ringColor: "border-[var(--muted)]",
      bgPulse: false,
    },
    disc_detected: {
      label: "Disc Detected",
      color: "var(--accent)",
      ringColor: "border-[var(--accent)]",
      bgPulse: true,
    },
    ripping: {
      label: "Ripping...",
      color: "var(--warning)",
      ringColor: "border-amber-500",
      bgPulse: true,
    },
  };

  const c = config[driveStatus];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="text-xs uppercase tracking-wider text-[var(--muted)] mb-4">
        Drive Status
      </div>
      <div className="flex items-center gap-4">
        <div
          className={`w-16 h-16 rounded-full border-4 ${c.ringColor} flex items-center justify-center ${
            c.bgPulse ? "animate-pulse-bar" : ""
          }`}
        >
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle
              cx="14"
              cy="14"
              r="12"
              stroke={c.color}
              strokeWidth="2"
            />
            <circle cx="14" cy="14" r="4" fill={c.color} />
          </svg>
        </div>
        <div>
          <div className="text-xl font-semibold text-white">{c.label}</div>
          {driveStatus === "ripping" && (
            <div className="text-sm text-[var(--muted)] mt-1">
              Progress: {activeJobProgress}%
            </div>
          )}
        </div>
      </div>

      {driveStatus === "ripping" && (
        <div className="mt-4">
          <div className="w-full h-3 rounded-full bg-[var(--background)] overflow-hidden">
            <div
              className="h-full rounded-full bg-amber-500 animate-progress-stripe transition-all duration-500"
              style={{ width: `${activeJobProgress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
