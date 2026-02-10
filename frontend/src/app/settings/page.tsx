"use client";

import { useEffect, useState } from "react";
import { Settings } from "@/lib/types";
import { getSettings, updateSettings } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateSettings(settings);
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl">
        <div className="text-[var(--muted)]">Loading...</div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="max-w-2xl">
        <div className="text-red-400">Failed to load settings</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Settings</h1>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-6">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
          DVD Ripping
        </h2>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            Output Path
          </label>
          <input
            type="text"
            value={settings.output_path}
            onChange={(e) =>
              setSettings({ ...settings, output_path: e.target.value })
            }
            className="w-full px-3 py-2 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            Naming Format
          </label>
          <input
            type="text"
            value={settings.naming_pattern}
            onChange={(e) =>
              setSettings({ ...settings, naming_pattern: e.target.value })
            }
            className="w-full px-3 py-2 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
          <p className="mt-1 text-xs text-[var(--muted)]">
            Available tokens: YYYY, MM, DD, NNN (sequence number)
          </p>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-[var(--muted)]">
              Auto-Eject
            </div>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Automatically eject disc after ripping completes
            </p>
          </div>
          <button
            onClick={() =>
              setSettings({ ...settings, auto_eject: !settings.auto_eject })
            }
            className={`relative w-11 h-6 rounded-full transition-colors ${
              settings.auto_eject
                ? "bg-[var(--accent)]"
                : "bg-[var(--border)]"
            }`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                settings.auto_eject ? "left-[22px]" : "left-0.5"
              }`}
            />
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-6">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
          VHS Capture Settings
        </h2>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            VHS Output Path
          </label>
          <input
            type="text"
            value={settings.vhs_output_path ?? "/output/vhs"}
            onChange={(e) =>
              setSettings({ ...settings, vhs_output_path: e.target.value })
            }
            className="w-full px-3 py-2 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            Encoding Preset
          </label>
          <select
            value={settings.encoding_preset ?? "fast"}
            onChange={(e) =>
              setSettings({ ...settings, encoding_preset: e.target.value })
            }
            className="w-full px-3 py-2 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
          >
            <option value="fast">Fast</option>
            <option value="medium">Medium</option>
            <option value="slow">Slow</option>
          </select>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Faster presets encode quicker but produce larger files
          </p>
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            CRF Quality: {settings.crf_quality ?? 23}
          </label>
          <input
            type="range"
            min={18}
            max={28}
            value={settings.crf_quality ?? 23}
            onChange={(e) =>
              setSettings({ ...settings, crf_quality: Number(e.target.value) })
            }
            className="w-full accent-[var(--accent)]"
          />
          <div className="flex justify-between mt-1 text-xs text-[var(--muted)]">
            <span>18 (highest quality / largest)</span>
            <span>28 (lowest quality / smallest)</span>
          </div>
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-[var(--muted)] mb-2">
            Audio Bitrate
          </label>
          <select
            value={settings.audio_bitrate ?? "192k"}
            onChange={(e) =>
              setSettings({ ...settings, audio_bitrate: e.target.value })
            }
            className="w-full px-3 py-2 rounded border border-[var(--border)] bg-[var(--background)] text-white text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
          >
            <option value="128k">128 kbps</option>
            <option value="192k">192 kbps</option>
            <option value="256k">256 kbps</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 text-sm rounded bg-[var(--accent)] text-white hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
        {saved && (
          <span className="text-sm text-[var(--success)]">
            Settings saved
          </span>
        )}
      </div>
    </div>
  );
}
