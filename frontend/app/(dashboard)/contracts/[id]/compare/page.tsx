"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { compareVersions } from "@/lib/api/analysis";
import { getContractDetails, listContractVersions } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  ArrowLeft,
  ArrowRight,
  GitCompare,
  CheckCircle2,
  AlertTriangle,
  PlusCircle,
  MinusCircle,
  FileEdit,
  Sparkles,
  RefreshCw,
} from "lucide-react";
import { ClauseDiffItem } from "@/types";

export default function VersionComparisonPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const contractId = params.id as string;

  const urlFrom = searchParams.get("from");
  const urlTo = searchParams.get("to");

  // Contract details query
  const { data: contract } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  // Versions list query
  const { data: versions = [] } = useQuery({
    queryKey: ["contract-versions", contractId],
    queryFn: () => listContractVersions(contractId),
    enabled: !!contractId,
  });

  // Default selection: v1 to latest, or URL params
  const [fromVersionId, setFromVersionId] = useState<string>(
    urlFrom || (versions.length > 0 ? versions[0].id : "")
  );
  const [toVersionId, setToVersionId] = useState<string>(
    urlTo || (versions.length > 1 ? versions[versions.length - 1].id : "")
  );
  const [filterChange, setFilterChange] = useState<string>("all");
  const [refreshTrigger, setRefreshTrigger] = useState<boolean>(false);

  // Sync state once versions load
  React.useEffect(() => {
    if (versions.length > 0 && !fromVersionId) {
      setFromVersionId(versions[0].id);
    }
    if (versions.length > 1 && !toVersionId) {
      setToVersionId(versions[versions.length - 1].id);
    }
  }, [versions, fromVersionId, toVersionId]);

  // Comparison Query
  const {
    data: comparison,
    isLoading: isLoadingComparison,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["contract-comparison", contractId, fromVersionId, toVersionId, refreshTrigger],
    queryFn: () => compareVersions(contractId, fromVersionId, toVersionId, refreshTrigger),
    enabled: !!contractId && !!fromVersionId && !!toVersionId && fromVersionId !== toVersionId,
  });

  const diffItems: ClauseDiffItem[] = comparison?.diff_items || [];
  const filteredDiffs = diffItems.filter((d) =>
    filterChange === "all" ? true : d.change_type === filterChange
  );

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
            <div className="flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-primary" />
              <h1 className="text-2xl font-bold text-on-surface tracking-tight">
                Version Comparison & Diff
              </h1>
            </div>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Contract: {contract?.title || contract?.file_name || contractId}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            className="gap-1.5 text-xs font-semibold"
            onClick={() => {
              setRefreshTrigger(true);
              setTimeout(() => setRefreshTrigger(false), 500);
            }}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Recompute Diff</span>
          </Button>
        </div>
      </div>

      {/* Version Selector Bar */}
      <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex flex-col gap-1 w-full md:w-56">
            <label className="text-xs font-semibold text-on-surface-variant">Baseline Version (From)</label>
            <select
              value={fromVersionId}
              onChange={(e) => setFromVersionId(e.target.value)}
              className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-xs font-medium text-on-surface focus:outline-none focus:border-primary"
            >
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version_number} — {v.file_name}
                </option>
              ))}
            </select>
          </div>

          <div className="pt-5 hidden md:block">
            <ArrowRight className="w-4 h-4 text-on-surface-variant" />
          </div>

          <div className="flex flex-col gap-1 w-full md:w-56">
            <label className="text-xs font-semibold text-on-surface-variant">Compare Against (To)</label>
            <select
              value={toVersionId}
              onChange={(e) => setToVersionId(e.target.value)}
              className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-xs font-medium text-on-surface focus:outline-none focus:border-primary"
            >
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version_number} — {v.file_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {fromVersionId === toVersionId && (
          <p className="text-xs text-[#ea580c] font-medium flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />
            Please select two different versions to compare.
          </p>
        )}
      </div>

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load contract comparison."}
          onRetry={() => refetch()}
        />
      )}

      {/* Comparison Metrics Summary Card */}
      {comparison && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
              Risk Delta
            </span>
            <div className="flex items-baseline gap-2 mt-2">
              <span
                className={`text-2xl font-bold font-mono ${
                  comparison.risk_delta > 0
                    ? "text-[#dc2626]"
                    : comparison.risk_delta < 0
                    ? "text-[#10b981]"
                    : "text-on-surface"
                }`}
              >
                {comparison.risk_delta > 0 ? `+${comparison.risk_delta}` : comparison.risk_delta}
              </span>
              <span className="text-xs text-on-surface-variant">
                ({comparison.risk_score_from} → {comparison.risk_score_to})
              </span>
            </div>
          </div>

          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1">
              <PlusCircle className="w-3.5 h-3.5" /> Added Clauses
            </span>
            <span className="text-2xl font-bold font-mono text-emerald-400 mt-2">
              {comparison.clauses_added_count}
            </span>
          </div>

          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-[#dc2626] uppercase tracking-wider flex items-center gap-1">
              <MinusCircle className="w-3.5 h-3.5" /> Removed Clauses
            </span>
            <span className="text-2xl font-bold font-mono text-[#dc2626] mt-2">
              {comparison.clauses_removed_count}
            </span>
          </div>

          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-[#ea580c] uppercase tracking-wider flex items-center gap-1">
              <FileEdit className="w-3.5 h-3.5" /> Modified Clauses
            </span>
            <span className="text-2xl font-bold font-mono text-[#ea580c] mt-2">
              {comparison.clauses_modified_count}
            </span>
          </div>

          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col justify-between">
            <span className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> Unchanged
            </span>
            <span className="text-2xl font-bold font-mono text-on-surface mt-2">
              {comparison.clauses_unchanged_count}
            </span>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-outline-variant/30 pb-3 flex-wrap">
        <span className="text-xs font-semibold text-on-surface-variant mr-2">Filter Changes:</span>
        {(["all", "modified", "added", "removed", "unchanged"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilterChange(tab)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
              filterChange === tab
                ? "bg-primary text-on-primary"
                : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Clause Diff Items List */}
      <div className="flex flex-col gap-4">
        {isLoadingComparison ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full rounded-xl" />
          ))
        ) : filteredDiffs.length === 0 ? (
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-12 text-center text-on-surface-variant text-xs">
            No clause diffs matching this filter.
          </div>
        ) : (
          filteredDiffs.map((diff, index) => {
            const isAdded = diff.change_type === "added";
            const isRemoved = diff.change_type === "removed";
            const isModified = diff.change_type === "modified";

            return (
              <div
                key={index}
                className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4 hover:border-outline transition-colors"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md ${
                        isAdded
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : isRemoved
                          ? "bg-red-500/10 text-red-400 border border-red-500/20"
                          : isModified
                          ? "bg-[#ea580c]/10 text-[#ea580c] border border-[#ea580c]/20"
                          : "bg-surface-container-high text-on-surface-variant border border-outline-variant"
                      }`}
                    >
                      {diff.change_type}
                    </span>
                    <h3 className="text-base font-bold text-on-surface capitalize">
                      {diff.display_name}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 text-xs font-mono">
                    {diff.from_severity && (
                      <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        V{comparison?.from_version_number || 1}: {diff.from_severity}
                      </span>
                    )}
                    {diff.from_severity && diff.to_severity && <span>→</span>}
                    {diff.to_severity && (
                      <span className="px-2 py-0.5 rounded bg-surface-container-highest font-bold text-primary">
                        V{comparison?.to_version_number || 2}: {diff.to_severity}
                      </span>
                    )}
                  </div>
                </div>

                {/* Diff Comparison Side-by-Side or Stacked */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  {/* From Text */}
                  <div className="bg-surface-container-highest/40 border border-outline-variant/40 rounded-lg p-3 flex flex-col gap-1.5">
                    <span className="text-[11px] font-bold text-on-surface-variant uppercase">
                      Baseline (V{comparison?.from_version_number || 1})
                    </span>
                    {diff.from_text ? (
                      <p className="text-on-surface/90 leading-relaxed whitespace-pre-wrap">
                        {diff.from_text}
                      </p>
                    ) : (
                      <p className="text-on-surface-variant italic">[Clause not present in baseline]</p>
                    )}
                  </div>

                  {/* To Text */}
                  <div className="bg-surface-container-highest/40 border border-outline-variant/40 rounded-lg p-3 flex flex-col gap-1.5">
                    <span className="text-[11px] font-bold text-primary uppercase">
                      Revised (V{comparison?.to_version_number || 2})
                    </span>
                    {diff.to_text ? (
                      <p className="text-on-surface/90 leading-relaxed whitespace-pre-wrap">
                        {diff.to_text}
                      </p>
                    ) : (
                      <p className="text-on-surface-variant italic">[Clause removed in revised version]</p>
                    )}
                  </div>
                </div>

                {diff.ai_explanation && (
                  <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 flex items-start gap-2 text-xs">
                    <Sparkles className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-primary block mb-0.5">AI Summary of Changes</span>
                      <p className="text-on-surface-variant">{diff.ai_explanation}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {comparison?.disclaimer && (
        <p className="text-xs text-on-surface-variant italic text-center border-t border-outline-variant/30 pt-4">
          {comparison.disclaimer}
        </p>
      )}
    </div>
  );
}
