"use client";

import { useDigitizer } from "@/context/digitizer-context";
import { useEffect, useState } from "react";

export default function ActiveJobPanel() {
  const { activeJobId, activeJobProgress, driveStatus } = useDigitizer();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!activeJobId) {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [activeJobId]);

  if (!activeJobId && driveStatus !== "ripping") {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="text-xs uppercase tracking-wider text-[var(--muted)] mb-4">
          Active Job
        </div>
        <div className="text-sm text-[var(--muted)]">
          No active rip in progress
        </div>
      </div>
    );
  }

  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  const timeStr = h > 0
    ? `${h}h ${m}m ${s}s`
    : m > 0
    ? `${m}m ${s}s`
    : `${s}s`;

  return (
    <div className="rounded-lg border border-amber-500/30 bg-[var(--surface)] p-6">
      <div className="text-xs uppercase tracking-wider text-amber-400 mb-4">
        Active Job
      </div>
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-[var(--muted)]">Job ID</span>
          <span className="text-white font-mono text-xs">
            {activeJobId ? activeJobId.slice(0, 8) + "..." : "-"}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-[var(--muted)]">Progress</span>
          <span className="text-amber-400 font-semibold">
            {activeJobProgress}%
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-[var(--muted)]">Elapsed</span>
          <span className="text-white">{timeStr}</span>
        </div>
        <div className="w-full h-2 rounded-full bg-[var(--background)] overflow-hidden">
          <div
            className="h-full rounded-full bg-amber-500 animate-progress-stripe transition-all duration-500"
            style={{ width: `${activeJobProgress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
