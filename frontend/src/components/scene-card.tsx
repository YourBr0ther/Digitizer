"use client";

import { useState } from "react";
import { Scene } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";
import { getThumbnailUrl } from "@/lib/api";

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  isFirst: boolean;
  isLast: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onAdjust: (startTime: number, endTime: number) => void;
}

export default function SceneCard({
  scene,
  isSelected,
  isFirst,
  isLast,
  onSelect,
  onDelete,
  onAdjust,
}: SceneCardProps) {
  const [editing, setEditing] = useState(false);
  const [editStart, setEditStart] = useState(String(scene.start_time));
  const [editEnd, setEditEnd] = useState(String(scene.end_time));

  const thumbnailFilename = scene.thumbnail_path
    ? scene.thumbnail_path.split("/").pop() || ""
    : "";
  const thumbUrl = thumbnailFilename
    ? getThumbnailUrl(scene.job_id, thumbnailFilename)
    : null;

  const handleSaveAdjust = () => {
    const start = parseFloat(editStart);
    const end = parseFloat(editEnd);
    if (!isNaN(start) && !isNaN(end) && start < end) {
      onAdjust(start, end);
      setEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditStart(String(scene.start_time));
    setEditEnd(String(scene.end_time));
    setEditing(false);
  };

  return (
    <div
      className={`rounded-lg border bg-[var(--surface)] overflow-hidden transition-all cursor-pointer ${
        isSelected
          ? "border-purple-500/60 ring-1 ring-purple-500/30"
          : "border-[var(--border)] hover:border-purple-500/30"
      }`}
      onClick={onSelect}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-[var(--background)] overflow-hidden">
        {thumbUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbUrl}
            alt={`Scene ${scene.scene_index}`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" className="text-[var(--muted)]">
              <rect x="4" y="6" width="24" height="20" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M13 13l6 3.5-6 3.5V13z" fill="currentColor" />
            </svg>
          </div>
        )}
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 text-[10px] font-medium text-purple-300">
          Scene {scene.scene_index}
        </div>
        <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-white/80">
          {formatTimestamp(scene.duration)}
        </div>
      </div>

      {/* Info */}
      <div className="p-3 space-y-2">
        {editing ? (
          <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">
                  Start
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={editStart}
                  onChange={(e) => setEditStart(e.target.value)}
                  className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--background)] text-white text-xs font-mono focus:outline-none focus:border-purple-500 transition-colors"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">
                  End
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={editEnd}
                  onChange={(e) => setEditEnd(e.target.value)}
                  className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--background)] text-white text-xs font-mono focus:outline-none focus:border-purple-500 transition-colors"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSaveAdjust}
                className="flex-1 py-1 text-xs rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-colors"
              >
                Save
              </button>
              <button
                onClick={handleCancelEdit}
                className="flex-1 py-1 text-xs rounded bg-[var(--background)] text-[var(--muted)] border border-[var(--border)] hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[var(--muted)]">
                {formatTimestamp(scene.start_time)} &mdash; {formatTimestamp(scene.end_time)}
              </span>
            </div>

            <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => {
                  setEditStart(String(scene.start_time));
                  setEditEnd(String(scene.end_time));
                  setEditing(true);
                }}
                className="flex-1 py-1 text-xs rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 hover:bg-purple-500/20 transition-colors"
              >
                Adjust
              </button>
              {!isFirst && !isLast && (
                <button
                  onClick={onDelete}
                  className="flex-1 py-1 text-xs rounded bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                >
                  Delete
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
