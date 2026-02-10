import { Job, Settings, DriveState } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  offset = 0
): Promise<Job[]> {
  return request<Job[]>(`/api/jobs?limit=${limit}&offset=${offset}`);
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
