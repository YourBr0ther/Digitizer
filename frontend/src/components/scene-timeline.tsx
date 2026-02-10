"use client";

import { useState } from "react";
import { Scene } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";

const SCENE_COLORS = [
  "bg-purple-500/40",
  "bg-purple-400/25",
  "bg-purple-600/40",
  "bg-purple-300/25",
  "bg-purple-500/30",
  "bg-purple-400/40",
];

interface SceneTimelineProps {
  scenes: Scene[];
  totalDuration: number;
  selectedIndex: number | null;
  onSelectScene: (index: number) => void;
}

export default function SceneTimeline({
  scenes,
  totalDuration,
  selectedIndex,
  onSelectScene,
}: SceneTimelineProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  if (totalDuration === 0 || scenes.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="text-xs uppercase tracking-wider text-[var(--muted)] mb-3">
          Timeline
        </div>
        <div className="h-10 rounded bg-[var(--background)] flex items-center justify-center">
          <span className="text-xs text-[var(--muted)]">No scenes to display</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-wider text-[var(--muted)]">
          Timeline
        </div>
        <div className="text-xs text-[var(--muted)]">
          {scenes.length} scenes &middot; {formatTimestamp(totalDuration)}
        </div>
      </div>

      <div className="relative">
        {/* Timeline bar */}
        <div className="flex h-10 rounded overflow-hidden bg-[var(--background)] relative">
          {scenes.map((scene, i) => {
            const widthPct = ((scene.end_time - scene.start_time) / totalDuration) * 100;
            const isSelected = selectedIndex === i;
            const isHovered = hoveredIndex === i;
            const colorClass = SCENE_COLORS[i % SCENE_COLORS.length];

            return (
              <div
                key={scene.id}
                className={`relative h-full cursor-pointer transition-all duration-150 ${colorClass} ${
                  isSelected ? "ring-2 ring-purple-400 ring-inset z-10" : ""
                } ${isHovered ? "brightness-125" : ""}`}
                style={{ width: `${widthPct}%`, minWidth: "2px" }}
                onClick={() => onSelectScene(i)}
                onMouseEnter={(e) => {
                  setHoveredIndex(i);
                  const rect = e.currentTarget.getBoundingClientRect();
                  setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
                }}
                onMouseLeave={() => {
                  setHoveredIndex(null);
                  setTooltipPos(null);
                }}
              >
                {/* Scene number label for wider segments */}
                {widthPct > 6 && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-[10px] font-medium text-white/70">
                      {scene.scene_index}
                    </span>
                  </div>
                )}
              </div>
            );
          })}

          {/* Cut markers at scene boundaries */}
          {scenes.slice(1).map((scene, i) => {
            const leftPct = (scene.start_time / totalDuration) * 100;
            return (
              <div
                key={`cut-${i}`}
                className="absolute top-0 bottom-0 w-px bg-purple-300/60 z-20 pointer-events-none"
                style={{ left: `${leftPct}%` }}
              >
                <div className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-purple-400" />
                <div className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-purple-400" />
              </div>
            );
          })}
        </div>

        {/* Time markers below */}
        <div className="flex justify-between mt-1.5">
          <span className="text-[10px] text-[var(--muted)] font-mono">0:00.0</span>
          <span className="text-[10px] text-[var(--muted)] font-mono">{formatTimestamp(totalDuration)}</span>
        </div>

        {/* Hover tooltip */}
        {hoveredIndex !== null && tooltipPos && (
          <div
            className="fixed z-50 px-3 py-2 rounded bg-[var(--background)] border border-purple-500/30 shadow-lg pointer-events-none"
            style={{
              left: tooltipPos.x,
              top: tooltipPos.y - 8,
              transform: "translate(-50%, -100%)",
            }}
          >
            <div className="text-xs font-medium text-purple-300">
              Scene {scenes[hoveredIndex].scene_index}
            </div>
            <div className="text-[10px] text-[var(--muted)] mt-0.5">
              {formatTimestamp(scenes[hoveredIndex].start_time)} &mdash;{" "}
              {formatTimestamp(scenes[hoveredIndex].end_time)}
            </div>
            <div className="text-[10px] text-[var(--muted)]">
              Duration: {formatTimestamp(scenes[hoveredIndex].duration)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
