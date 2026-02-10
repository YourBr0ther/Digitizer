"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Job } from "@/lib/types";
import { getJob, deleteJob, analyzeScenes } from "@/lib/api";
import { useDigitizer } from "@/context/digitizer-context";
import StatusBadge from "@/components/status-badge";
import {
  formatBytes,
  formatDate,
  formatDuration,
  filenameFromPath,
} from "@/lib/utils";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzingLocal, setAnalyzingLocal] = useState(false);
  const { analysisProgress } = useDigitizer();

  const fetchJob = (id: string) => {
    getJob(id)
      .then(setJob)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchJob(params.id as string);
  }, [params.id]);

  // Refresh job when analysis completes
  useEffect(() => {
    if (analysisProgress === null && analyzingLocal && job) {
      setAnalyzingLocal(false);
      fetchJob(job.id);
    }
  }, [analysisProgress, analyzingLocal, job]);

  const handleAnalyze = async () => {
    if (!job) return;
    setAnalyzingLocal(true);
    try {
      await analyzeScenes(job.id);
    } catch {
      setAnalyzingLocal(false);
    }
  };

  const handleDelete = async () => {
    if (!job) return;
    if (!confirm("Delete this job record?")) return;
    try {
      await deleteJob(job.id);
      router.push("/jobs");
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl">
        <div className="text-[var(--muted)]">Loading...</div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-3xl">
        <div className="text-red-400">
          {error || "Job not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/jobs")}
            className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-semibold text-white">Job Detail</h1>
        </div>
        <button
          onClick={handleDelete}
          className="px-3 py-1.5 text-sm rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
        >
          Delete
        </button>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <StatusBadge status={job.status} />
          <span className="text-white font-semibold">
            {filenameFromPath(job.output_path)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <Field label="Job ID" value={job.id} mono />
          <Field label="Source Type" value={job.source_type.toUpperCase()} />
          <Field label="Started" value={formatDate(job.started_at)} />
          <Field label="Completed" value={formatDate(job.completed_at)} />
          <Field
            label="Duration"
            value={formatDuration(job.disc_info.duration)}
          />
          <Field label="File Size" value={formatBytes(job.file_size)} />
          <Field
            label="Title Count"
            value={String(job.disc_info.title_count)}
          />
          <Field
            label="Main Title"
            value={String(job.disc_info.main_title)}
          />
          <Field
            label="Progress"
            value={`${job.progress}%`}
          />
          <Field
            label="Output Path"
            value={job.output_path || "-"}
            mono
          />
        </div>

        {job.error && (
          <div className="mt-4">
            <div className="text-xs uppercase tracking-wider text-red-400 mb-2">
              Error Log
            </div>
            <pre className="p-4 rounded bg-[var(--background)] border border-red-500/30 text-red-300 text-xs font-mono whitespace-pre-wrap overflow-x-auto">
              {job.error}
            </pre>
          </div>
        )}
      </div>

      {/* Scene Analysis Section - VHS jobs only */}
      {job.source_type === "vhs" && job.status === "complete" && (
        <div className="rounded-lg border border-purple-500/20 bg-[var(--surface)] p-6 space-y-4">
          <div className="text-xs uppercase tracking-wider text-purple-400 mb-2">
            Scene Detection
          </div>

          {/* No analysis yet */}
          {!job.analysis_status && !analyzingLocal && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--muted)]">
                Analyze this capture to detect individual scenes
              </span>
              <button
                onClick={handleAnalyze}
                className="px-4 py-2 text-sm rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-colors"
              >
                Analyze Scenes
              </button>
            </div>
          )}

          {/* Analyzing */}
          {(job.analysis_status === "analyzing" || analyzingLocal) && (
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                <span className="text-sm text-purple-300">Detecting scenes...</span>
              </div>
              <div className="w-full h-2 rounded-full bg-[var(--background)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-purple-500 animate-progress-stripe transition-all duration-500"
                  style={{
                    width: `${
                      analysisProgress?.jobId === job.id
                        ? analysisProgress.progress
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Analyzed */}
          {(job.analysis_status === "analyzed" || job.analysis_status === "split_complete") &&
            !analyzingLocal && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border bg-purple-500/15 text-purple-400 border-purple-500/30">
                    {job.scene_count ?? 0} scenes{" "}
                    {job.analysis_status === "split_complete" ? "split" : "detected"}
                  </span>
                </div>
                <Link
                  href={`/jobs/${job.id}/scenes`}
                  className="px-4 py-2 text-sm rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-colors"
                >
                  Review Scenes
                </Link>
              </div>
            )}

          {/* Splitting */}
          {job.analysis_status === "splitting" && !analyzingLocal && (
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                <span className="text-sm text-purple-300">Splitting scenes...</span>
              </div>
              <div className="w-full h-2 rounded-full bg-[var(--background)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-purple-500 animate-progress-stripe transition-all duration-500"
                  style={{ width: "50%" }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-[var(--muted)] text-xs uppercase tracking-wider mb-1">
        {label}
      </div>
      <div
        className={`text-white ${
          mono ? "font-mono text-xs break-all" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
