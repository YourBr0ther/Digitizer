export type JobStatus = "detected" | "ripping" | "complete" | "failed";
export type DriveStatusType = "empty" | "disc_detected" | "ripping";
export type CaptureStatus = "idle" | "recording";
export type AnalysisStatus = "analyzing" | "analyzed" | "splitting" | "split_complete";

export interface DiscInfo {
  title_count: number;
  main_title: number;
  duration: number;
}

export interface Job {
  id: string;
  source_type: string;
  disc_info: DiscInfo;
  status: JobStatus;
  progress: number;
  output_path: string | null;
  file_size: number | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  analysis_status: AnalysisStatus | null;
  scene_count: number | null;
}

export interface Scene {
  id: string;
  job_id: string;
  scene_index: number;
  start_time: number;
  end_time: number;
  duration: number;
  thumbnail_path: string | null;
  split_path: string | null;
}

export interface CaptureStatusResponse {
  status: CaptureStatus;
  job_id: string | null;
}

export interface CaptureStartResponse {
  job_id: string;
  source_type: string;
  status: string;
  output_path: string;
}

export interface Settings {
  output_path: string;
  naming_pattern: string;
  auto_eject: boolean;
  vhs_output_path?: string;
  encoding_preset?: string;
  crf_quality?: number;
  audio_bitrate?: string;
}

export interface DriveState {
  status: DriveStatusType;
}

export interface WSEvent {
  event: string;
  data: Record<string, unknown>;
}
