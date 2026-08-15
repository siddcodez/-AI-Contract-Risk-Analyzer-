"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getContractDetails, getContractStatus } from "@/lib/api/contracts";
import {
  getAnalysisStatus,
  getFindingsSummary,
  listFindings,
  triggerAnalysis,
  getMissingClauses,
} from "@/lib/api/analysis";
import { useAuth } from "@/lib/auth/store";
import { Button } from "@/components/ui/button";
import { StatusBadge, RiskBadge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { formatDate, formatBytes } from "@/lib/utils";
import {
  FileText,
  Search,
  Bot,
  RefreshCw,
  ArrowRight,
  AlertTriangle,
  Gavel,
  ShieldAlert,
  ClipboardCheck,
  ChevronRight,
  FileDown,
} from "lucide-react";

export default function ContractDetailPage() {
  const params = useParams();
  const contractId = params.id as string;
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isReviewerOrAdmin = user?.role === "admin" || user?.role === "reviewer";

  // 1. Contract Details Query
  const {
    data: contract,
    isLoading: isLoadingContract,
    isError: isErrorContract,
    error: errorContract,
  } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  // 2. Processing Status Query (smart polling while queued/processing)
  const { data: processingStatus } = useQuery({
    queryKey: ["contract-status", contractId],
    queryFn: () => getContractStatus(contractId),
    enabled: !!contractId,
    refetchInterval: (query) => {
      const status = query.state.data?.contract_status;
      return status === "processing" || status === "pending" ? 3000 : false;
    },
  });

  // 3. Analysis Status Query (smart polling while processing)
  const { data: analysisStatus, refetch: refetchAnalysis } = useQuery({
    queryKey: ["contract-analysis", contractId],
    queryFn: async () => {
      try {
        return await getAnalysisStatus(contractId);
      } catch (err: unknown) {
        if (err && typeof err === "object" && "status" in err && err.status === 404) {
          return null;
        }
        throw err;
      }
    },
    enabled: !!contractId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "queued" ? 3000 : false;
    },
  });

  // 4. Findings Summary Query
  const { data: findingsSummary } = useQuery({
    queryKey: ["findings-summary", contractId],
    queryFn: () => getFindingsSummary(contractId),
    enabled: !!contractId,
  });

  // 5. Recent Findings Preview Query
  const { data: findingsData, isLoading: isLoadingFindings } = useQuery({
    queryKey: ["findings-preview", contractId],
    queryFn: () => listFindings(contractId, { limit: 5 }),
    enabled: !!contractId,
  });

  // 6. Missing Clauses Preview Query
  const { data: missingData, isLoading: isLoadingMissing } = useQuery({
    queryKey: ["missing-clauses-preview", contractId],
    queryFn: () => getMissingClauses(contractId),
    enabled: !!contractId,
  });

  // Trigger Analysis Mutation
  const analyzeMutation = useMutation({
    mutationFn: () => triggerAnalysis(contractId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contract-analysis", contractId] });
      queryClient.invalidateQueries({ queryKey: ["findings-summary", contractId] });
      queryClient.invalidateQueries({ queryKey: ["findings-preview", contractId] });
      queryClient.invalidateQueries({ queryKey: ["missing-clauses-preview", contractId] });
      refetchAnalysis();
    },
  });

  const findings = findingsData?.items || [];
  const totalFindings = findingsSummary?.total ?? findingsData?.total ?? 0;
  const criticalCount = findingsSummary?.critical ?? 0;
  const highCount = findingsSummary?.high ?? 0;
  const mediumCount = findingsSummary?.medium ?? 0;
  const lowCount = findingsSummary?.low ?? 0;

  // Calculate Overall Risk label
  const overallRisk =
    criticalCount > 0
      ? "CRITICAL"
      : highCount > 0
      ? "HIGH"
      : mediumCount > 0
      ? "MEDIUM"
      : totalFindings > 0
      ? "LOW"
      : "LOW";

  const overallRiskColor =
    overallRisk === "CRITICAL"
      ? "text-[#dc2626]"
      : overallRisk === "HIGH"
      ? "text-[#ea580c]"
      : overallRisk === "MEDIUM"
      ? "text-[#eab308]"
      : "text-[#10b981]";

  if (isErrorContract) {
    return (
      <div className="py-6">
        <ErrorBanner
          title="Contract Not Found"
          message={
            errorContract instanceof Error
              ? errorContract.message
              : "Unable to retrieve contract details."
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Header Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant/30 pb-6">
        <div className="flex items-center gap-3 flex-wrap">
          {isLoadingContract ? (
            <Skeleton className="h-8 w-64" />
          ) : (
            <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
              {contract?.title || contract?.file_name}
            </h1>
          )}
          <StatusBadge
            status={
              processingStatus?.contract_status ||
              contract?.status ||
              "pending"
            }
          />
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Link href={`/contracts/${contractId}/search`}>
            <Button variant="secondary" className="gap-2 h-10 text-xs font-semibold">
              <Search className="w-3.5 h-3.5" />
              <span>Search Contract</span>
            </Button>
          </Link>

          <a
            href={`/api/v1/contracts/${contractId}/reports/download`}
            target="_blank"
            rel="noreferrer"
          >
            <Button variant="secondary" className="gap-2 h-10 text-xs font-semibold">
              <FileDown className="w-3.5 h-3.5 text-primary" />
              <span>Download PDF</span>
            </Button>
          </a>

          {isReviewerOrAdmin && (
            <Button
              variant="primary"
              className="gap-2 h-10 text-xs font-bold"
              disabled={
                contract?.status === "processing" ||
                analyzeMutation.isPending ||
                analysisStatus?.status === "processing"
              }
              isLoading={
                analyzeMutation.isPending || analysisStatus?.status === "processing"
              }
              onClick={() => analyzeMutation.mutate()}
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>
                {analysisStatus?.status === "completed"
                  ? "Re-analyze"
                  : "Run Risk Analysis"}
              </span>
            </Button>
          )}
        </div>
      </div>

      {/* Summary Cards Grid (4 Cards across, matching Stitch) */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Overall Risk */}
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col justify-between h-32">
          <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            Overall Risk
          </h3>
          <div className="flex items-end justify-between">
            <span className={`text-2xl font-bold ${overallRiskColor}`}>
              {overallRisk}
            </span>
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center ${
                overallRisk === "CRITICAL"
                  ? "bg-[#dc2626]/15 text-[#dc2626]"
                  : overallRisk === "HIGH"
                  ? "bg-[#ea580c]/15 text-[#ea580c]"
                  : overallRisk === "MEDIUM"
                  ? "bg-[#eab308]/15 text-[#eab308]"
                  : "bg-[#10b981]/15 text-[#10b981]"
              }`}
            >
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Card 2: Critical Findings */}
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col justify-between h-32">
          <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            Critical Findings
          </h3>
          <div className="flex items-end justify-between">
            <span className="text-2xl font-bold text-[#dc2626]">
              {criticalCount}
            </span>
            <div className="w-10 h-10 rounded-full bg-[#dc2626]/15 flex items-center justify-center text-[#dc2626]">
              <Gavel className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Card 3: High Findings */}
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col justify-between h-32">
          <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            High Findings
          </h3>
          <div className="flex items-end justify-between">
            <span className="text-2xl font-bold text-[#ea580c]">
              {highCount}
            </span>
            <div className="w-10 h-10 rounded-full bg-[#ea580c]/15 flex items-center justify-center text-[#ea580c]">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Card 4: Total Findings */}
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col justify-between h-32">
          <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            Total Findings
          </h3>
          <div className="flex items-end justify-between">
            <span className="text-2xl font-bold text-primary">
              {totalFindings}
            </span>
            <div className="w-10 h-10 rounded-full bg-primary-container/20 flex items-center justify-center text-primary">
              <ClipboardCheck className="w-5 h-5" />
            </div>
          </div>
        </div>
      </section>

      {/* 3-Column Layout (Matching Stitch) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Column 1: Contract Info (3 cols) */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-6 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-5">
            <h3 className="text-base font-bold text-on-surface border-b border-outline-variant pb-3">
              Contract Info
            </h3>

            <div className="flex flex-col gap-3 text-xs">
              <div>
                <span className="text-on-surface-variant block font-semibold mb-0.5">
                  File Type
                </span>
                <span className="font-mono text-on-surface font-semibold uppercase">
                  {contract?.content_type?.split("/")[1] || "PDF"}
                </span>
              </div>

              <div>
                <span className="text-on-surface-variant block font-semibold mb-0.5">
                  Size
                </span>
                <span className="font-mono text-on-surface">
                  {contract ? formatBytes(contract.file_size) : "..."}
                </span>
              </div>

              <div>
                <span className="text-on-surface-variant block font-semibold mb-0.5">
                  Uploaded
                </span>
                <span className="text-on-surface">
                  {contract?.created_at ? formatDate(contract.created_at) : "..."}
                </span>
              </div>

              <div>
                <span className="text-on-surface-variant block font-semibold mb-0.5">
                  Status
                </span>
                <span className="font-semibold text-emerald-400 capitalize">
                  {contract?.status || "Pending"}
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-outline-variant flex flex-col gap-2.5">
              <Link href={`/contracts/${contractId}/search`}>
                <Button
                  variant="secondary"
                  className="w-full text-xs font-semibold gap-2 justify-center"
                >
                  <Search className="w-3.5 h-3.5" />
                  <span>Search Within</span>
                </Button>
              </Link>

              <Link href={`/contracts/${contractId}/ask`}>
                <Button
                  variant="secondary"
                  className="w-full text-xs font-semibold gap-2 justify-center"
                >
                  <Bot className="w-3.5 h-3.5 text-primary" />
                  <span>Ask Document (RAG)</span>
                </Button>
              </Link>

              <Link href={`/contracts/${contractId}/compare`}>
                <Button
                  variant="secondary"
                  className="w-full text-xs font-semibold gap-2 justify-center"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-secondary" />
                  <span>Compare Versions</span>
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {/* Column 2: Risk Findings (6 cols) */}
        <div className="lg:col-span-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-on-surface">Risk Findings</h3>
            <Link
              href={`/contracts/${contractId}/analysis`}
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
            >
              <span>View All ({totalFindings})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {isLoadingFindings ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="bg-surface-container-low border border-outline-variant rounded-xl p-5 flex flex-col gap-3"
              >
                <div className="flex justify-between items-center">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-14 w-full rounded-lg" />
              </div>
            ))
          ) : findings.length === 0 ? (
            <div className="bg-surface-container-low border border-outline-variant rounded-xl p-8 text-center flex flex-col items-center gap-3">
              <ClipboardCheck className="w-8 h-8 text-on-surface-variant" />
              <p className="text-sm font-semibold text-on-surface">
                No risk findings detected
              </p>
              <p className="text-xs text-on-surface-variant max-w-sm">
                Run the risk analysis engine to scan this contract for liability,
                indemnification, termination, and data privacy risks.
              </p>
              {isReviewerOrAdmin && (
                <Button
                  variant="primary"
                  size="sm"
                  className="gap-1.5 mt-2"
                  isLoading={analyzeMutation.isPending}
                  onClick={() => analyzeMutation.mutate()}
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Run Risk Analysis</span>
                </Button>
              )}
            </div>
          ) : (
            findings.map((finding) => (
              <div
                key={finding.id}
                className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-3 hover:border-outline transition-colors"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-base font-semibold text-on-surface">
                      {finding.title}
                    </h4>
                    <span className="inline-block px-2 py-0.5 mt-1 rounded bg-surface-container-high text-on-surface-variant text-[11px] font-mono border border-outline-variant">
                      {finding.category.toUpperCase().replace("_", " ")}
                    </span>
                  </div>
                  <RiskBadge severity={finding.severity} />
                </div>

                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {finding.description}
                </p>

                {finding.evidence && (
                  <div className="bg-surface-container-highest/60 rounded-md p-3 border border-outline-variant/40 font-mono text-xs text-on-surface/90 overflow-x-auto">
                    &ldquo;{finding.evidence}&rdquo;
                  </div>
                )}

                <div className="flex justify-between items-center border-t border-outline-variant/40 pt-2.5 text-xs text-on-surface-variant">
                  <span>Confidence: {(finding.confidence * 100).toFixed(0)}%</span>
                  <Link
                    href={`/contracts/${contractId}/findings/${finding.id}`}
                    className="font-semibold text-primary hover:text-primary-fixed-dim transition-colors flex items-center gap-1"
                  >
                    <span>View Details</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Column 3: Analysis Summary & Recommendations (3 cols) */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-6 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-5">
            <h3 className="text-base font-bold text-on-surface border-b border-outline-variant pb-3">
              Analysis Summary
            </h3>

            {/* Segmented Risk Distribution Bar */}
            <div>
              <span className="text-xs font-semibold text-on-surface-variant block mb-2">
                Risk Distribution
              </span>
              <div className="flex h-3 rounded-full overflow-hidden bg-surface-container-high mb-2">
                {totalFindings > 0 ? (
                  <>
                    <div
                      className="bg-[#dc2626]"
                      style={{ width: `${(criticalCount / totalFindings) * 100}%` }}
                    />
                    <div
                      className="bg-[#ea580c]"
                      style={{ width: `${(highCount / totalFindings) * 100}%` }}
                    />
                    <div
                      className="bg-[#eab308]"
                      style={{ width: `${(mediumCount / totalFindings) * 100}%` }}
                    />
                    <div
                      className="bg-[#10b981]"
                      style={{ width: `${(lowCount / totalFindings) * 100}%` }}
                    />
                  </>
                ) : (
                  <div className="bg-surface-container-highest w-full" />
                )}
              </div>
              <div className="flex justify-between text-[10px] font-semibold text-on-surface-variant">
                <span className="text-[#dc2626]">Crit ({criticalCount})</span>
                <span className="text-[#ea580c]">High ({highCount})</span>
                <span className="text-[#eab308]">Med ({mediumCount})</span>
                <span className="text-[#10b981]">Low ({lowCount})</span>
              </div>
            </div>

            {/* Missing Clauses Card */}
            <div className="border-t border-outline-variant pt-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-[#ea580c]" />
                  <span className="text-xs font-bold text-on-surface">
                    Missing Clauses ({missingData?.total ?? 0})
                  </span>
                </div>
                <Link
                  href={`/contracts/${contractId}/analysis`}
                  className="text-[11px] font-semibold text-primary hover:underline"
                >
                  View
                </Link>
              </div>

              {isLoadingMissing ? (
                <Skeleton className="h-10 w-full rounded-lg" />
              ) : (missingData?.items.length ?? 0) === 0 ? (
                <p className="text-[11px] text-emerald-400 font-medium">
                  ✓ All standard expected clauses detected.
                </p>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {missingData?.items.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      className="bg-surface-container-high/40 border border-[#ea580c]/20 rounded-md px-2.5 py-1.5 flex items-center justify-between text-xs"
                    >
                      <span className="capitalize font-medium text-on-surface truncate">
                        {item.clause_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] font-mono font-semibold text-[#ea580c] bg-[#ea580c]/10 px-1.5 py-0.5 rounded">
                        {(item.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                  <p className="text-[10px] text-on-surface-variant italic mt-0.5">
                    Not legal advice. Deterministic baseline check.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
