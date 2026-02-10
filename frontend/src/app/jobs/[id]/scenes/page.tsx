"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Job, Scene } from "@/lib/types";
import { getJob, getScenes, updateScenes, analyzeScenes, splitScenes } from "@/lib/api";
import { useDigitizer } from "@/context/digitizer-context";
import SceneTimeline from "@/components/scene-timeline";
import SceneCard from "@/components/scene-card";

export default function ScenesPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const { analysisProgress, splitProgress } = useDigitizer();

  const [job, setJob] = useState<Job | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  // Action states
  const [analyzing, setAnalyzing] = useState(false);
  const [splitting, setSplitting] = useState(false);
  const [splitDone, setSplitDone] = useState(false);
  const [sensitivity, setSensitivity] = useState(22);

  // Add cut state
  const [showAddCut, setShowAddCut] = useState(false);
  const [cutTimestamp, setCutTimestamp] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const [jobData, scenesData] = await Promise.all([
        getJob(jobId),
        getScenes(jobId),
      ]);
      setJob(jobData);
      setScenes(scenesData);
      if (jobData.analysis_status === "analyzing") setAnalyzing(true);
      if (jobData.analysis_status === "splitting") setSplitting(true);
      if (jobData.analysis_status === "split_complete") setSplitDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Refresh data when analysis or split completes
  useEffect(() => {
    if (analysisProgress === null && analyzing) {
      setAnalyzing(false);
      fetchData();
    }
  }, [analysisProgress, analyzing, fetchData]);

  useEffect(() => {
    if (splitProgress === null && splitting) {
      setSplitting(false);
      setSplitDone(true);
      fetchData();
    }
  }, [splitProgress, splitting, fetchData]);

  const handleReanalyze = async () => {
    setAnalyzing(true);
    setSplitDone(false);
    try {
      await analyzeScenes(jobId);
    } catch {
      setAnalyzing(false);
    }
  };

  const handleSplit = async () => {
    setSplitting(true);
    setSplitDone(false);
    try {
      await splitScenes(jobId);
    } catch {
      setSplitting(false);
    }
  };

  const handleDeleteScene = async (index: number) => {
    if (scenes.length <= 1) return;
    const newScenes = [...scenes];
    const removed = newScenes.splice(index, 1)[0];

    // Merge: extend the previous scene's end time or next scene's start time
    if (index > 0) {
      newScenes[index - 1] = {
        ...newScenes[index - 1],
        end_time: removed.end_time,
        duration: removed.end_time - newScenes[index - 1].start_time,
      };
    } else if (newScenes.length > 0) {
      newScenes[0] = {
        ...newScenes[0],
        start_time: removed.start_time,
        duration: newScenes[0].end_time - removed.start_time,
      };
    }

    // Re-index
    const payload = newScenes.map((s, i) => ({
      scene_index: i + 1,
      start_time: s.start_time,
      end_time: s.end_time,
    }));

    try {
      const updated = await updateScenes(jobId, payload);
      setScenes(updated);
      setSelectedIndex(null);
    } catch {
      // reload on failure
      fetchData();
    }
  };

  const handleAdjustScene = async (index: number, startTime: number, endTime: number) => {
    const newScenes = scenes.map((s, i) => {
      if (i === index) {
        return { ...s, start_time: startTime, end_time: endTime, duration: endTime - startTime };
      }
      return s;
    });

    const payload = newScenes.map((s, i) => ({
      scene_index: i + 1,
      start_time: s.start_time,
      end_time: s.end_time,
    }));

    try {
      const updated = await updateScenes(jobId, payload);
      setScenes(updated);
    } catch {
      fetchData();
    }
  };

  const handleAddCut = async () => {
    const ts = parseFloat(cutTimestamp);
    if (isNaN(ts) || !job) return;

    // Find the scene this timestamp falls within
    const sceneIdx = scenes.findIndex((s) => ts > s.start_time && ts < s.end_time);
    if (sceneIdx === -1) return;

    const scene = scenes[sceneIdx];
    const newScenes = [...scenes];
    newScenes.splice(
      sceneIdx,
      1,
      { ...scene, end_time: ts, duration: ts - scene.start_time },
      { ...scene, id: "new", start_time: ts, duration: scene.end_time - ts }
    );

    const payload = newScenes.map((s, i) => ({
      scene_index: i + 1,
      start_time: s.start_time,
      end_time: s.end_time,
    }));

    try {
      const updated = await updateScenes(jobId, payload);
      setScenes(updated);
      setCutTimestamp("");
      setShowAddCut(false);
    } catch {
      fetchData();
    }
  };

  const totalDuration = job?.disc_info.duration ?? 0;

  const currentAnalysisProgress =
    analysisProgress?.jobId === jobId ? analysisProgress.progress : null;
  const currentSplitProgress =
    splitProgress?.jobId === jobId ? splitProgress : null;

  if (loading) {
    return (
      <div className="max-w-5xl">
        <div className="text-[var(--muted)]">Loading scenes...</div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-5xl">
        <div className="text-red-400">{error || "Job not found"}</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push(`/jobs/${jobId}`)}
            className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-semibold text-white">Scene Review</h1>
          <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border bg-purple-500/15 text-purple-400 border-purple-500/30">
            {scenes.length} scenes
          </span>
        </div>
      </div>

      {/* Analysis progress overlay */}
      {analyzing && (
        <div className="rounded-lg border border-purple-500/30 bg-[var(--surface)] p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <span className="text-sm font-medium text-purple-300">Detecting scenes...</span>
          </div>
          <div className="w-full h-2 rounded-full bg-[var(--background)] overflow-hidden">
            <div
              className="h-full rounded-full bg-purple-500 animate-progress-stripe transition-all duration-500"
              style={{ width: `${currentAnalysisProgress ?? 0}%` }}
            />
          </div>
          <div className="text-xs text-[var(--muted)] mt-2">
            {currentAnalysisProgress ?? 0}% complete
          </div>
        </div>
      )}

      {/* Timeline */}
      {!analyzing && scenes.length > 0 && (
        <SceneTimeline
          scenes={scenes}
          totalDuration={totalDuration}
          selectedIndex={selectedIndex}
          onSelectScene={setSelectedIndex}
        />
      )}

      {/* Add Cut button */}
      {!analyzing && scenes.length > 0 && (
        <div className="flex items-center gap-3">
          {showAddCut ? (
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                min="0"
                placeholder="Timestamp (seconds)"
                value={cutTimestamp}
                onChange={(e) => setCutTimestamp(e.target.value)}
                className="px-3 py-1.5 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm font-mono focus:outline-none focus:border-purple-500 transition-colors w-48"
              />
              <button
                onClick={handleAddCut}
                disabled={!cutTimestamp}
                className="px-3 py-1.5 text-sm rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 disabled:opacity-40 transition-colors"
              >
                Add
              </button>
              <button
                onClick={() => { setShowAddCut(false); setCutTimestamp(""); }}
                className="px-3 py-1.5 text-sm rounded text-[var(--muted)] hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAddCut(true)}
              className="px-3 py-1.5 text-sm rounded border border-dashed border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors"
            >
              + Add Cut
            </button>
          )}
        </div>
      )}

      {/* Scene cards grid */}
      {!analyzing && scenes.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scenes.map((scene, i) => (
            <SceneCard
              key={scene.id}
              scene={scene}
              isSelected={selectedIndex === i}
              isFirst={i === 0}
              isLast={i === scenes.length - 1}
              onSelect={() => setSelectedIndex(i)}
              onDelete={() => handleDeleteScene(i)}
              onAdjust={(start, end) => handleAdjustScene(i, start, end)}
            />
          ))}
        </div>
      )}

      {/* No scenes state */}
      {!analyzing && scenes.length === 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
          <div className="text-[var(--muted)] mb-4">No scenes detected yet</div>
          <button
            onClick={handleReanalyze}
            className="px-4 py-2 text-sm rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-colors"
          >
            Analyze Scenes
          </button>
        </div>
      )}

      {/* Split progress */}
      {splitting && (
        <div className="rounded-lg border border-purple-500/30 bg-[var(--surface)] p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <span className="text-sm font-medium text-purple-300">
              Splitting scene {currentSplitProgress?.currentScene ?? "..."}...
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-[var(--background)] overflow-hidden">
            <div
              className="h-full rounded-full bg-purple-500 animate-progress-stripe transition-all duration-500"
              style={{ width: `${currentSplitProgress?.progress ?? 0}%` }}
            />
          </div>
          <div className="text-xs text-[var(--muted)] mt-2">
            {currentSplitProgress?.progress ?? 0}% complete
          </div>
        </div>
      )}

      {/* Split done message */}
      {splitDone && !splitting && (
        <div className="rounded-lg border border-emerald-500/30 bg-[var(--surface)] p-4 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-sm text-emerald-300">
            {scenes.length} scenes split successfully
          </span>
        </div>
      )}

      {/* Action bar */}
      {!analyzing && scenes.length > 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            {/* Re-analyze with sensitivity */}
            <div className="flex items-center gap-3 flex-1">
              <button
                onClick={handleReanalyze}
                disabled={analyzing || splitting}
                className="px-4 py-2 text-sm rounded bg-[var(--background)] text-[var(--foreground)] border border-[var(--border)] hover:bg-[var(--surface-hover)] disabled:opacity-40 transition-colors whitespace-nowrap"
              >
                Re-analyze
              </button>
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="text-xs text-[var(--muted)] whitespace-nowrap">Sensitivity:</span>
                <input
                  type="range"
                  min={15}
                  max={35}
                  value={sensitivity}
                  onChange={(e) => setSensitivity(Number(e.target.value))}
                  className="flex-1 accent-purple-500"
                />
                <span className="text-xs font-mono text-[var(--muted)] w-6 text-right">{sensitivity}</span>
              </div>
            </div>

            {/* Split all */}
            <button
              onClick={handleSplit}
              disabled={splitting || analyzing || scenes.length === 0}
              className="px-4 py-2 text-sm rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 disabled:opacity-40 transition-colors whitespace-nowrap"
            >
              {splitting ? "Splitting..." : "Split All"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
