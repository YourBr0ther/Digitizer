"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { CaptureStatus, DriveStatusType, Job } from "@/lib/types";

interface AnalysisProgress {
  jobId: string;
  progress: number;
}

interface SplitProgress {
  jobId: string;
  progress: number;
  currentScene: number;
}

interface DigitizerState {
  driveStatus: DriveStatusType;
  activeJobId: string | null;
  activeJobProgress: number;
  lastCompletedJob: Job | null;
  lastFailedJob: Job | null;
  connected: boolean;
  captureStatus: CaptureStatus;
  captureJobId: string | null;
  captureElapsed: number;
  captureFileSize: number;
  analysisProgress: AnalysisProgress | null;
  splitProgress: SplitProgress | null;
}

const initialState: DigitizerState = {
  driveStatus: "empty",
  activeJobId: null,
  activeJobProgress: 0,
  lastCompletedJob: null,
  lastFailedJob: null,
  connected: false,
  captureStatus: "idle",
  captureJobId: null,
  captureElapsed: 0,
  captureFileSize: 0,
  analysisProgress: null,
  splitProgress: null,
};

const DigitizerContext = createContext<DigitizerState>(initialState);

export function useDigitizer() {
  return useContext(DigitizerContext);
}

export function DigitizerProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DigitizerState>(initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectDelayRef = useRef(1000);

  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    const baseUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = baseUrl.replace(/^http/, "ws") + "/api/ws";

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectDelayRef.current = 1000;
      setState((prev) => ({ ...prev, connected: true }));
    };

    ws.onclose = () => {
      setState((prev) => ({ ...prev, connected: false }));
      if (!mountedRef.current) return;
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectDelayRef.current = Math.min(
          reconnectDelayRef.current * 2,
          30000
        );
        connect();
      }, reconnectDelayRef.current);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const { event: eventType, data } = msg;

        setState((prev) => {
          switch (eventType) {
            case "drive_status":
              return {
                ...prev,
                driveStatus: data.status as DriveStatusType,
              };
            case "capture_status":
              return {
                ...prev,
                captureStatus: data.status as CaptureStatus,
                ...(data.status === "idle"
                  ? { captureJobId: null, captureElapsed: 0, captureFileSize: 0 }
                  : {}),
              };
            case "job_progress":
              if (data.elapsed !== undefined) {
                return {
                  ...prev,
                  captureJobId: data.job_id as string,
                  captureElapsed: data.elapsed as number,
                  captureFileSize: data.file_size as number,
                };
              }
              return {
                ...prev,
                activeJobId: data.job_id as string,
                activeJobProgress: data.progress as number,
              };
            case "job_complete":
              return {
                ...prev,
                activeJobId: null,
                activeJobProgress: 0,
                lastCompletedJob: data as Job,
              };
            case "job_failed":
              return {
                ...prev,
                activeJobId: null,
                activeJobProgress: 0,
                lastFailedJob: data as Job,
              };
            case "analysis_progress":
              return {
                ...prev,
                analysisProgress: {
                  jobId: data.job_id as string,
                  progress: data.progress as number,
                },
              };
            case "analysis_complete":
              return {
                ...prev,
                analysisProgress: null,
              };
            case "split_progress":
              return {
                ...prev,
                splitProgress: {
                  jobId: data.job_id as string,
                  progress: data.progress as number,
                  currentScene: data.current_scene as number,
                },
              };
            case "split_complete":
              return {
                ...prev,
                splitProgress: null,
              };
            case "analysis_failed":
              return {
                ...prev,
                analysisProgress: null,
              };
            case "split_failed":
              return {
                ...prev,
                splitProgress: null,
              };
            default:
              return prev;
          }
        });
      } catch {
        // ignore malformed messages
      }
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return (
    <DigitizerContext.Provider value={state}>
      {children}
    </DigitizerContext.Provider>
  );
}
