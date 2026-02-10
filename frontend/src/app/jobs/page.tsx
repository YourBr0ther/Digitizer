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

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const router = useRouter();

  const fetchJobs = useCallback(async (off: number) => {
    setLoading(true);
    try {
      const data = await getJobs(PAGE_SIZE, off);
      setJobs(data);
      setHasMore(data.length === PAGE_SIZE);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs(offset);
  }, [offset, fetchJobs]);

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Job History</h1>

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
                  <td className="px-4 py-3 text-[var(--muted)] uppercase text-xs">
                    {job.source_type}
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">
                    {formatDuration(job.disc_info.duration)}
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
