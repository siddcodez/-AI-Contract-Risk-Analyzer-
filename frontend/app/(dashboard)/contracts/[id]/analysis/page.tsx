"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listFindings, triggerAnalysis, getMissingClauses } from "@/lib/api/analysis";
import { getContractDetails } from "@/lib/api/contracts";
import { useAuth } from "@/lib/auth/store";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { RiskCategory, RiskSeverity } from "@/types";
import {
  ArrowLeft,
  Play,
  Filter,
  CheckCircle,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  FileQuestion,
} from "lucide-react";

export default function AnalysisFindingsPage() {
  const params = useParams();
  const contractId = params.id as string;
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isReviewerOrAdmin = user?.role === "admin" || user?.role === "reviewer";

  const [severityFilter, setSeverityFilter] = useState<RiskSeverity | undefined>(
    undefined
  );
  const [categoryFilter, setCategoryFilter] = useState<RiskCategory | undefined>(
    undefined
  );

  // Contract details query for title
  const { data: contract } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  // Findings list query
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["findings", contractId, { severity: severityFilter, category: categoryFilter }],
    queryFn: () =>
      listFindings(contractId, {
        severity: severityFilter,
        category: categoryFilter,
        limit: 50,
      }),
    enabled: !!contractId,
  });

  // Missing clauses query
  const {
    data: missingData,
    isLoading: isLoadingMissing,
  } = useQuery({
    queryKey: ["missing-clauses", contractId],
    queryFn: () => getMissingClauses(contractId),
    enabled: !!contractId,
  });

  // Trigger analysis mutation
  const analyzeMutation = useMutation({
    mutationFn: () => triggerAnalysis(contractId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["findings", contractId] });
      queryClient.invalidateQueries({ queryKey: ["contract-analysis", contractId] });
      queryClient.invalidateQueries({ queryKey: ["missing-clauses", contractId] });
      refetch();
    },
  });

  const findings = data?.items || [];
  const missingClauses = missingData?.items || [];
  const total = data?.total || 0;

  const categories: RiskCategory[] = [
    "liability",
    "indemnification",
    "termination",
    "renewal",
    "intellectual_property",
    "data_privacy",
    "security",
    "payment",
    "confidentiality",
    "governing_law",
    "other",
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant/30 pb-6">
        <div className="flex items-center gap-3">
          <Link href={`/contracts/${contractId}`}>
            <Button variant="secondary" size="sm" className="h-9 w-9 p-0">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-on-surface tracking-tight">
              Risk Analysis Findings
            </h1>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Contract: {contract?.title || contract?.file_name || contractId}
            </p>
          </div>
        </div>

        {isReviewerOrAdmin && (
          <Button
            variant="primary"
            size="sm"
            className="gap-2 h-10 text-xs font-bold"
            isLoading={analyzeMutation.isPending}
            onClick={() => analyzeMutation.mutate()}
          >
            <Play className="w-3.5 h-3.5" />
            <span>Re-Run Risk Engine</span>
          </Button>
        )}
      </div>

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load findings"}
          onRetry={() => refetch()}
        />
      )}

      {/* Filter Bar */}
      <div className="bg-surface-container-low rounded-xl p-4 border border-outline-variant flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Severity Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-on-surface-variant font-semibold mr-1">Severity:</span>
          {(["all", "critical", "high", "medium", "low"] as const).map((sev) => {
            const isSelected = sev === "all" ? !severityFilter : severityFilter === sev;
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSeverityFilter(sev === "all" ? undefined : sev)}
                className={`px-3 py-1.5 rounded-lg font-semibold uppercase tracking-wider transition-colors ${
                  isSelected
                    ? "bg-primary-container text-white"
                    : "bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-bright border border-outline-variant"
                }`}
              >
                {sev}
              </button>
            );
          })}
        </div>

        {/* Category Dropdown */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-on-surface-variant" />
          <select
            value={categoryFilter || ""}
            onChange={(e) =>
              setCategoryFilter(
                (e.target.value as RiskCategory) || undefined
              )
            }
            className="bg-surface-container-high border border-outline-variant text-on-surface rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace("_", " ").toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Findings List */}
      <div className="flex flex-col gap-4">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="bg-surface-container-low border border-outline-variant rounded-xl p-6 flex flex-col gap-3"
            >
              <div className="flex justify-between items-center">
                <Skeleton className="h-6 w-64" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
              <Skeleton className="h-4 w-full mt-2" />
              <Skeleton className="h-16 w-full rounded-lg mt-2" />
            </div>
          ))
        ) : findings.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="No Risk Findings Detected"
            description="No risk anomalies matching your filter were detected by the rule analyzer."
            action={
              (severityFilter || categoryFilter) && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setSeverityFilter(undefined);
                    setCategoryFilter(undefined);
                  }}
                >
                  Clear Filters
                </Button>
              )
            }
          />
        ) : (
          findings.map((finding) => (
            <div
              key={finding.id}
              className="bg-surface-container-low border border-outline-variant rounded-xl p-6 shadow-sm flex flex-col gap-4 hover:border-outline transition-colors"
            >
              {/* Finding Top Row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-outline-variant/30 pb-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <RiskBadge severity={finding.severity} />
                  <span className="text-xs font-mono font-semibold text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded border border-outline-variant">
                    {finding.category.toUpperCase().replace("_", " ")}
                  </span>
                  <span className="text-xs text-on-surface-variant">
                    Confidence: {(finding.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                <Link href={`/contracts/${contractId}/findings/${finding.id}`}>
                  <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
                    <span>Full Analysis</span>
                    <ExternalLink className="w-3 h-3" />
                  </Button>
                </Link>
              </div>

              {/* Title & Description */}
              <div>
                <h3 className="text-base font-bold text-on-surface">
                  {finding.title}
                </h3>
                <p className="text-sm text-on-surface-variant mt-1 leading-relaxed">
                  {finding.description}
                </p>
              </div>

              {/* Evidence Quote */}
              {finding.evidence && (
                <div className="bg-surface-container-highest/60 rounded-lg p-3.5 border-l-2 border-primary font-mono text-xs text-on-surface-variant leading-relaxed">
                  <p className="font-sans text-[10px] font-semibold text-primary uppercase tracking-wider mb-1">
                    Verbatim Contract Evidence
                  </p>
                  &ldquo;{finding.evidence}&rdquo;
                </div>
              )}

              {/* Recommendation */}
              {finding.recommendation && (
                <div className="flex items-start gap-2 text-xs text-on-surface bg-surface-container-high/40 p-3 rounded-lg border border-outline-variant/40">
                  <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-emerald-400 mr-1">
                      Recommended Redline:
                    </span>
                    <span className="text-on-surface-variant">
                      {finding.recommendation}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      <div className="mt-4 flex flex-col gap-4 border-t border-outline-variant/40 pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#ea580c]" />
            <h2 className="text-xl font-bold text-on-surface">
              Missing Expected Clauses ({missingClauses.length})
            </h2>
          </div>
          <span className="text-[11px] font-medium text-on-surface-variant bg-surface-container-high px-2.5 py-1 rounded-md border border-outline-variant">
            Deterministic Absence Engine
          </span>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed">
          The following standard clauses are expected for this contract type but were not
          identified among classified clauses or text patterns.
          <span className="font-semibold text-primary ml-1">
            (Not legal advice. Identifies deterministic absence of standard baseline clauses.)
          </span>
        </p>

        {isLoadingMissing ? (
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 flex flex-col gap-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : missingClauses.length === 0 ? (
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
            <p className="text-xs text-on-surface font-medium">
              All baseline expected clauses for this contract type were identified.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {missingClauses.map((item) => (
              <div
                key={item.id}
                className="bg-surface-container-low border border-[#ea580c]/30 rounded-xl p-4 flex flex-col gap-2.5 shadow-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FileQuestion className="w-4 h-4 text-[#ea580c] shrink-0" />
                    <span className="text-sm font-bold text-on-surface capitalize">
                      {item.clause_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono font-semibold text-[#ea580c] bg-[#ea580c]/10 px-2 py-0.5 rounded border border-[#ea580c]/20">
                    {(item.confidence * 100).toFixed(0)}% Confidence
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {item.reason}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

