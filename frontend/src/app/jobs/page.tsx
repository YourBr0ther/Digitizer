"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Job } from "@/lib/types";
import { getJobs } from "@/lib/api";
import StatusBadge from "@/components/status-badge";
import {
  formatBytes,
  formatDate,
  formatDuration,
  filenameFromPath,
} from "@/lib/utils";

const PAGE_SIZE = 20;
const SOURCE_FILTERS = [
  { label: "All", value: undefined },
  { label: "DVD", value: "dvd" },
  { label: "VHS", value: "vhs" },
] as const;

function SourceBadge({ sourceType }: { sourceType: string }) {
  const isVHS = sourceType === "vhs";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border ${
        isVHS
          ? "bg-purple-500/15 text-purple-400 border-purple-500/30"
          : "bg-blue-500/15 text-blue-400 border-blue-500/30"
      }`}
    >
      {sourceType.toUpperCase()}
    </span>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined);
  const router = useRouter();

  const fetchJobs = useCallback(async (off: number, source?: string) => {
    setLoading(true);
    try {
      const data = await getJobs(PAGE_SIZE, off, source);
      setJobs(data);
      setHasMore(data.length === PAGE_SIZE);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs(offset, sourceFilter);
  }, [offset, sourceFilter, fetchJobs]);

  const handleFilterChange = (value: string | undefined) => {
    setSourceFilter(value);
    setOffset(0);
  };

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Job History</h1>

      <div className="flex gap-2">
        {SOURCE_FILTERS.map((filter) => (
          <button
            key={filter.label}
            onClick={() => handleFilterChange(filter.value)}
            className={`px-4 py-2 text-sm rounded border transition-colors ${
              sourceFilter === filter.value
                ? "border-[var(--accent)] bg-[var(--accent-dim)] text-[var(--accent)]"
                : "border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-hover)]"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Date
              </th>
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Filename
              </th>
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Source
              </th>
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Duration
              </th>
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Size
              </th>
              <th className="text-left px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] font-medium">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--muted)]">
                  Loading...
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--muted)]">
                  No jobs found
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => router.push(`/jobs/${job.id}`)}
                  className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-[var(--muted)]">
                    {formatDate(job.started_at)}
                  </td>
                  <td className="px-4 py-3 text-white">
                    {filenameFromPath(job.output_path)}
                  </td>
                  <td className="px-4 py-3">
                    <SourceBadge sourceType={job.source_type} />
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">
                    {formatDuration(job.disc_info?.duration ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">
                    {formatBytes(job.file_size)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={job.status} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <button
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0}
          className="px-4 py-2 text-sm rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] hover:bg-[var(--surface-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Previous
        </button>
        <span className="text-sm text-[var(--muted)]">
          Page {Math.floor(offset / PAGE_SIZE) + 1}
        </span>
        <button
          onClick={() => setOffset(offset + PAGE_SIZE)}
          disabled={!hasMore}
          className="px-4 py-2 text-sm rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] hover:bg-[var(--surface-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}
