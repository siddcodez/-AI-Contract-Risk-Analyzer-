import React from "react";
import { cn } from "@/lib/utils";
import { LucideIcon, FileText } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon = FileText,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 md:p-12 text-center rounded-xl bg-surface-container-low border border-outline-variant",
        className
      )}
    >
      <div className="w-12 h-12 rounded-xl bg-surface-container-high flex items-center justify-center border border-outline-variant mb-4 text-on-surface-variant">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-lg font-semibold text-on-surface mb-1">{title}</h3>
      <p className="text-sm text-on-surface-variant max-w-md mb-6">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
