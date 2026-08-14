import React from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./button";

interface ErrorBannerProps {
  title?: string;
  message: string;
  requestId?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorBanner({
  title = "Error",
  message,
  requestId,
  onRetry,
  className,
}: ErrorBannerProps) {
  return (
    <div
      className={cn(
        "rounded-xl bg-error-container/20 border border-error/30 p-4 text-on-surface flex items-start gap-3",
        className
      )}
    >
      <AlertTriangle className="w-5 h-5 text-error shrink-0 mt-0.5" />
      <div className="flex-1 text-sm">
        <h4 className="font-semibold text-error mb-0.5">{title}</h4>
        <p className="text-on-surface-variant">{message}</p>
        {requestId && (
          <p className="mt-1 text-xs font-mono text-on-surface-variant/70">
            Request ID: {requestId}
          </p>
        )}
      </div>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          className="shrink-0 h-8 gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </Button>
      )}
    </div>
  );
}
