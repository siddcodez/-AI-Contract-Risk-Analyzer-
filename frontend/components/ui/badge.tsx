import React from "react";
import { cn } from "@/lib/utils";
import { RiskSeverity, ContractStatus, AnalysisJobStatus } from "@/types";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Clock,
  XCircle,
  Loader2,
} from "lucide-react";

export interface RiskBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  severity: RiskSeverity;
  showIcon?: boolean;
}

export function RiskBadge({
  severity,
  showIcon = true,
  className,
  ...props
}: RiskBadgeProps) {
  const configs: Record<
    RiskSeverity,
    { label: string; icon: React.ReactNode; styles: string }
  > = {
    critical: {
      label: "Critical",
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      styles: "bg-[#dc2626]/15 text-[#dc2626] border-[#dc2626]/30",
    },
    high: {
      label: "High",
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      styles: "bg-[#ea580c]/15 text-[#ea580c] border-[#ea580c]/30",
    },
    medium: {
      label: "Medium",
      icon: <AlertCircle className="w-3.5 h-3.5" />,
      styles: "bg-[#eab308]/15 text-[#eab308] border-[#eab308]/30",
    },
    low: {
      label: "Low",
      icon: <Info className="w-3.5 h-3.5" />,
      styles: "bg-[#16a34a]/15 text-[#16a34a] border-[#16a34a]/30",
    },
  };

  const config = configs[severity] || configs.low;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border",
        config.styles,
        className
      )}
      {...props}
    >
      {showIcon && config.icon}
      <span>{config.label}</span>
    </div>
  );
}

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  status: ContractStatus | AnalysisJobStatus | string;
  showIcon?: boolean;
}

export function StatusBadge({
  status,
  showIcon = true,
  className,
  ...props
}: StatusBadgeProps) {
  const normalized = status.toLowerCase();

  if (normalized === "completed") {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 text-xs font-semibold uppercase tracking-wider",
          className
        )}
        {...props}
      >
        {showIcon && <CheckCircle2 className="w-3.5 h-3.5" />}
        <span>Completed</span>
      </div>
    );
  }

  if (normalized === "processing") {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-950/40 text-amber-400 border border-amber-800/40 text-xs font-semibold uppercase tracking-wider",
          className
        )}
        {...props}
      >
        {showIcon && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        <span>Processing</span>
      </div>
    );
  }

  if (normalized === "failed") {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-red-950/40 text-red-400 border border-red-800/40 text-xs font-semibold uppercase tracking-wider",
          className
        )}
        {...props}
      >
        {showIcon && <XCircle className="w-3.5 h-3.5" />}
        <span>Failed</span>
      </div>
    );
  }

  // queued or pending
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant border border-outline-variant text-xs font-semibold uppercase tracking-wider",
        className
      )}
      {...props}
    >
      {showIcon && <Clock className="w-3.5 h-3.5" />}
      <span>{status === "queued" ? "Queued" : "Pending"}</span>
    </div>
  );
}
