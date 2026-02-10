"use client";

import DriveStatusCard from "@/components/drive-status-card";
import ActiveJobPanel from "@/components/active-job-panel";
import VHSCaptureCard from "@/components/vhs-capture-card";
import RecentJobs from "@/components/recent-jobs";

export default function Dashboard() {
  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <DriveStatusCard />
          <ActiveJobPanel />
        </div>
        <div>
          <VHSCaptureCard />
        </div>
      </div>
      <RecentJobs />
    </div>
  );
}
