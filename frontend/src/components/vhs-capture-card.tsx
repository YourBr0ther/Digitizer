"use client";

import { useState } from "react";
import { useDigitizer } from "@/context/digitizer-context";
import { startCapture, stopCapture } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

function formatElapsed(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export default function VHSCaptureCard() {
  const { captureStatus, captureElapsed, captureFileSize } = useDigitizer();
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startCapture();
    } catch {
      // ignore - status will update via WebSocket
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopCapture();
    } catch {
      // ignore - status will update via WebSocket
    } finally {
      setLoading(false);
    }
  };

  const isRecording = captureStatus === "recording";

  return (
    <div
      className={`rounded-lg border bg-[var(--surface)] p-6 ${
        isRecording ? "border-red-500/30" : "border-[var(--border)]"
      }`}
    >
      <div className="text-xs uppercase tracking-wider text-[var(--muted)] mb-4">
        VHS Capture
      </div>

      {isRecording ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-recording-pulse absolute inline-flex h-full w-full rounded-full bg-red-500" />
            </span>
            <span className="text-sm font-semibold uppercase tracking-wider text-red-400">
              Recording
            </span>
          </div>

          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-[var(--muted)]">Elapsed</span>
              <span className="text-white font-mono">
                {formatElapsed(captureElapsed)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-[var(--muted)]">File Size</span>
              <span className="text-white font-mono">
                {formatBytes(captureFileSize)}
              </span>
            </div>
          </div>

          <button
            onClick={handleStop}
            disabled={loading}
            className="w-full py-3 rounded text-sm font-semibold bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 disabled:opacity-50 transition-colors"
          >
            {loading ? "Stopping..." : "Stop Capture"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3">
              <span className="inline-flex h-full w-full rounded-full bg-[var(--success)]" />
            </span>
            <span className="text-sm text-[var(--muted)]">
              Ready to Capture
            </span>
          </div>

          <button
            onClick={handleStart}
            disabled={loading}
            className="w-full py-3 rounded text-sm font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50 transition-colors"
          >
            {loading ? "Starting..." : "Start Capture"}
          </button>
        </div>
      )}
    </div>
  );
}
