"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Job } from "@/lib/types";
import { getJobs } from "@/lib/api";
import { useDigitizer } from "@/context/digitizer-context";
import StatusBadge from "./status-badge";
import { formatBytes, formatDate, filenameFromPath } from "@/lib/utils";

export default function RecentJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const { lastCompletedJob, lastFailedJob } = useDigitizer();

  useEffect(() => {
    getJobs(10, 0)
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [lastCompletedJob, lastFailedJob]);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="text-xs uppercase tracking-wider text-[var(--muted)] mb-4">
        Recent Jobs
      </div>
      {loading ? (
        <div className="text-sm text-[var(--muted)]">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="text-sm text-[var(--muted)]">No jobs yet</div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className="flex items-center justify-between p-3 rounded border border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">
                  {filenameFromPath(job.output_path)}
                </div>
                <div className="text-xs text-[var(--muted)]">
                  {formatDate(job.started_at)}
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4">
                {job.file_size !== null && (
                  <span className="text-xs text-[var(--muted)]">
                    {formatBytes(job.file_size)}
                  </span>
                )}
                <StatusBadge status={job.status} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
