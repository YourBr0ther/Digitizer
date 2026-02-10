import { Job, Scene, Settings, DriveState, CaptureStatusResponse, CaptureStartResponse } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getDriveStatus(): Promise<DriveState> {
  return request<DriveState>("/api/drive");
}

export async function getJobs(
  limit = 10,
  offset = 0,
  sourceType?: string
): Promise<Job[]> {
  let url = `/api/jobs?limit=${limit}&offset=${offset}`;
  if (sourceType) {
    url += `&source_type=${sourceType}`;
  }
  return request<Job[]>(url);
}

export async function getJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${id}`);
}

export async function deleteJob(id: string): Promise<void> {
  await request<{ deleted: boolean }>(`/api/jobs/${id}`, {
    method: "DELETE",
  });
}

export async function getSettings(): Promise<Settings> {
  return request<Settings>("/api/settings");
}

export async function updateSettings(
  settings: Partial<Settings>
): Promise<Settings> {
  return request<Settings>("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export async function getCaptureStatus(): Promise<CaptureStatusResponse> {
  return request<CaptureStatusResponse>("/api/capture/status");
}

export async function startCapture(): Promise<CaptureStartResponse> {
  return request<CaptureStartResponse>("/api/capture/start", {
    method: "POST",
  });
}

export async function stopCapture(): Promise<Job> {
  return request<Job>("/api/capture/stop", {
    method: "POST",
  });
}

export async function analyzeScenes(jobId: string): Promise<{ status: string; job_id: string }> {
  return request<{ status: string; job_id: string }>(`/api/jobs/${jobId}/analyze`, {
    method: "POST",
  });
}

export async function getScenes(jobId: string): Promise<Scene[]> {
  return request<Scene[]>(`/api/jobs/${jobId}/scenes`);
}

export async function updateScenes(
  jobId: string,
  scenes: { scene_index: number; start_time: number; end_time: number }[]
): Promise<Scene[]> {
  return request<Scene[]>(`/api/jobs/${jobId}/scenes`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scenes),
  });
}

export async function splitScenes(jobId: string): Promise<{ status: string; job_id: string; scene_count: number }> {
  return request<{ status: string; job_id: string; scene_count: number }>(`/api/jobs/${jobId}/split`, {
    method: "POST",
  });
}

export function getThumbnailUrl(jobId: string, filename: string): string {
  return `${BASE_URL}/api/thumbs/${jobId}/${filename}`;
}
