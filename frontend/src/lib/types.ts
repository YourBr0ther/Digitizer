export type JobStatus = "detected" | "ripping" | "complete" | "failed";
export type DriveStatusType = "empty" | "disc_detected" | "ripping";

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
}

export interface Settings {
  output_path: string;
  naming_pattern: string;
  auto_eject: boolean;
}

export interface DriveState {
  status: DriveStatusType;
}

export interface WSEvent {
  event: string;
  data: Record<string, unknown>;
}
