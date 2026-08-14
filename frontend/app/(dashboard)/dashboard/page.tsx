"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listContracts } from "@/lib/api/contracts";
import { useAuth } from "@/lib/auth/store";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatRelativeTime } from "@/lib/utils";
import {
  Upload,
  FileText,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["contracts", { limit: 5 }],
    queryFn: () => listContracts({ skip: 0, limit: 10 }),
  });

  const contracts = data?.contracts || [];
  const totalContracts = data?.total ?? 0;
  const processingCount = contracts.filter(
    (c) => c.status === "processing" || c.status === "pending"
  ).length;
  const completedCount = contracts.filter((c) => c.status === "completed").length;
  const failedCount = contracts.filter((c) => c.status === "failed").length;

  return (
    <div className="flex flex-col gap-8">
      {/* Header Section */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-outline-variant/30 pb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
            Good morning, {user?.full_name?.split(" ")[0] || "there"}
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Here is the latest overview of your enterprise contract risk portfolio.
          </p>
        </div>
        <Link href="/upload">
          <Button variant="primary" className="gap-2 w-full md:w-auto h-11">
            <Upload className="w-4 h-4" />
            <span>Upload Contract</span>
          </Button>
        </Link>
      </header>

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load contracts data"}
          onRetry={() => refetch()}
        />
      )}

      {/* Stats Bento Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat 1: Total Contracts */}
        <div className="bg-surface-container-low rounded-xl p-5 border border-outline-variant shadow-sm flex flex-col gap-3 relative overflow-hidden group">
          <div className="flex justify-between items-start z-10">
            <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center border border-outline-variant text-primary">
              <FileText className="w-5 h-5" />
            </div>
            <span className="text-xs font-semibold text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded">
              Active
            </span>
          </div>
          <div className="z-10 mt-2">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Total Contracts
            </p>
            {isLoading ? (
              <Skeleton className="h-9 w-16 mt-1" />
            ) : (
              <p className="text-3xl font-bold text-on-surface mt-1">
                {totalContracts}
              </p>
            )}
          </div>
          <div className="w-full h-6 mt-1 opacity-70">
            <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 30">
              <path
                d="M0 25 Q 15 20, 30 25 T 60 15 T 80 20 T 100 10"
                fill="none"
                stroke="#d2bbff"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>
        </div>

        {/* Stat 2: Processing */}
        <div className="bg-surface-container-low rounded-xl p-5 border border-outline-variant shadow-sm flex flex-col gap-3 relative overflow-hidden group">
          <div className="flex justify-between items-start z-10">
            <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center border border-outline-variant text-tertiary">
              <RefreshCw className="w-5 h-5 animate-spin-slow" />
            </div>
          </div>
          <div className="z-10 mt-2 flex-1 flex flex-col justify-center">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Processing
            </p>
            {isLoading ? (
              <Skeleton className="h-9 w-16 mt-1" />
            ) : (
              <p className="text-3xl font-bold text-on-surface mt-1">
                {processingCount}
              </p>
            )}
          </div>
          <div className="w-full bg-surface-container-high h-1.5 rounded-full overflow-hidden mt-1">
            <div className="bg-tertiary h-full w-2/3 rounded-full animate-pulse" />
          </div>
        </div>

        {/* Stat 3: Completed Analyses */}
        <div className="bg-surface-container-low rounded-xl p-5 border border-outline-variant shadow-sm flex flex-col gap-3 relative overflow-hidden group">
          <div className="flex justify-between items-start z-10">
            <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center border border-outline-variant text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <span className="text-xs font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
              Ready
            </span>
          </div>
          <div className="z-10 mt-2">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Completed
            </p>
            {isLoading ? (
              <Skeleton className="h-9 w-16 mt-1" />
            ) : (
              <p className="text-3xl font-bold text-on-surface mt-1">
                {completedCount}
              </p>
            )}
          </div>
          <div className="w-full h-6 mt-1 opacity-70">
            <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 30">
              <path
                d="M0 20 Q 20 25, 40 15 T 70 20 T 90 10 T 100 5"
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>
        </div>

        {/* Stat 4: Failed / Action Required */}
        <div className="bg-surface-container-low rounded-xl p-5 border border-outline-variant shadow-sm flex flex-col gap-3 relative overflow-hidden group">
          <div className="flex justify-between items-start z-10">
            <div className="w-10 h-10 rounded-lg bg-error-container/20 flex items-center justify-center border border-error/30 text-error">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <span className="text-xs font-semibold text-error bg-error-container/30 px-2 py-0.5 rounded border border-error/20">
              Issues
            </span>
          </div>
          <div className="z-10 mt-2">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Failed Jobs
            </p>
            {isLoading ? (
              <Skeleton className="h-9 w-16 mt-1" />
            ) : (
              <p className="text-3xl font-bold text-error mt-1">
                {failedCount}
              </p>
            )}
          </div>
          <div className="w-full h-6 mt-1 opacity-70">
            <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 30">
              <path
                d="M0 25 Q 20 25, 40 15 T 70 20 T 90 5 T 100 10"
                fill="none"
                stroke="#ffb4ab"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>
        </div>
      </section>

      {/* Recent Contracts Section */}
      <section className="bg-surface-container-low rounded-xl border border-outline-variant shadow-sm overflow-hidden flex flex-col">
        <div className="p-5 border-b border-outline-variant flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-on-surface">Recent Contracts</h2>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Live records from multi-tenant PostgreSQL storage
            </p>
          </div>
          <Link
            href="/contracts"
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto w-full">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-outline-variant/50 bg-surface-container-highest/30">
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Contract
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Status
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant hidden sm:table-cell">
                  Type
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant hidden md:table-cell">
                  Uploaded
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant text-right">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30 text-sm text-on-surface">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="p-4">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <Skeleton className="w-6 h-6 rounded" />
                        <Skeleton className="h-4 w-48" />
                      </div>
                    </td>
                    <td className="p-4">
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </td>
                    <td className="p-4 hidden sm:table-cell">
                      <Skeleton className="h-4 w-16" />
                    </td>
                    <td className="p-4 hidden md:table-cell">
                      <Skeleton className="h-4 w-24" />
                    </td>
                    <td className="p-4 text-right">
                      <Skeleton className="h-8 w-16 ml-auto" />
                    </td>
                  </tr>
                ))
              ) : contracts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8">
                    <EmptyState
                      title="No contracts uploaded yet"
                      description="Upload your first vendor agreement, NDA, or service contract to run automated risk analysis."
                      action={
                        <Link href="/upload">
                          <Button variant="primary" size="sm" className="gap-1.5">
                            <Upload className="w-4 h-4" />
                            <span>Upload Contract</span>
                          </Button>
                        </Link>
                      }
                    />
                  </td>
                </tr>
              ) : (
                contracts.slice(0, 5).map((contract) => (
                  <tr
                    key={contract.id}
                    className="hover:bg-surface-container-high/50 transition-colors group"
                  >
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-on-surface-variant group-hover:text-primary transition-colors shrink-0" />
                        <Link
                          href={`/contracts/${contract.id}`}
                          className="font-medium text-on-surface hover:text-primary transition-colors truncate max-w-xs md:max-w-md block"
                        >
                          {contract.title || contract.file_name}
                        </Link>
                      </div>
                    </td>
                    <td className="p-4">
                      <StatusBadge status={contract.status} />
                    </td>
                    <td className="p-4 hidden sm:table-cell text-xs font-mono text-on-surface-variant">
                      {contract.content_type?.split("/")[1]?.toUpperCase() || "DOC"}
                    </td>
                    <td className="p-4 hidden md:table-cell text-xs text-on-surface-variant">
                      {formatRelativeTime(contract.created_at)}
                    </td>
                    <td className="p-4 text-right">
                      <Link href={`/contracts/${contract.id}`}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 gap-1 text-xs"
                        >
                          <span>Review</span>
                          <ExternalLink className="w-3 h-3" />
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Analytics & Risk Breakdown Overview */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Risk Distribution Breakdown */}
        <div className="bg-surface-container-low rounded-xl border border-outline-variant shadow-sm p-5 flex flex-col gap-4">
          <div className="border-b border-outline-variant/30 pb-3">
            <h3 className="text-base font-semibold text-on-surface">
              Risk Engine Architecture
            </h3>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Deterministic rule evaluation across 15 standard risk categories
            </p>
          </div>
          <div className="flex flex-col gap-3 text-xs">
            <div className="flex items-center gap-3">
              <span className="w-20 font-semibold text-error text-right">
                Critical
              </span>
              <div className="flex-1 bg-surface-container-high h-2 rounded-full overflow-hidden">
                <div className="bg-[#dc2626] h-full rounded-full w-3/4" />
              </div>
              <span className="w-16 text-on-surface-variant">Uncapped Liab.</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-20 font-semibold text-[#ea580c] text-right">
                High
              </span>
              <div className="flex-1 bg-surface-container-high h-2 rounded-full overflow-hidden">
                <div className="bg-[#ea580c] h-full rounded-full w-1/2" />
              </div>
              <span className="w-16 text-on-surface-variant">Indemnification</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-20 font-semibold text-[#eab308] text-right">
                Medium
              </span>
              <div className="flex-1 bg-surface-container-high h-2 rounded-full overflow-hidden">
                <div className="bg-[#eab308] h-full rounded-full w-2/3" />
              </div>
              <span className="w-16 text-on-surface-variant">Auto-Renewal</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-20 font-semibold text-[#16a34a] text-right">
                Low
              </span>
              <div className="flex-1 bg-surface-container-high h-2 rounded-full overflow-hidden">
                <div className="bg-[#16a34a] h-full rounded-full w-1/3" />
              </div>
              <span className="w-16 text-on-surface-variant">Governing Law</span>
            </div>
          </div>
        </div>

        {/* AI & Pipeline Status */}
        <div className="bg-surface-container-low rounded-xl border border-outline-variant shadow-sm p-5 flex flex-col gap-4">
          <div className="border-b border-outline-variant/30 pb-3">
            <h3 className="text-base font-semibold text-on-surface">
              Asynchronous Processing Pipeline
            </h3>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Celery worker jobs with pgvector similarity indexing
            </p>
          </div>
          <ul className="flex flex-col gap-2.5 text-xs text-on-surface">
            <li className="flex items-center gap-3 p-2 rounded-lg bg-surface-container-high/40">
              <div className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
              <div className="flex-1 font-medium">Text Extraction & Chunking</div>
              <div className="text-on-surface-variant font-mono">1000 char / 200 overlap</div>
            </li>
            <li className="flex items-center gap-3 p-2 rounded-lg bg-surface-container-high/40">
              <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
              <div className="flex-1 font-medium">pgvector Embeddings Index</div>
              <div className="text-on-surface-variant font-mono">1536 dim / cosine</div>
            </li>
            <li className="flex items-center gap-3 p-2 rounded-lg bg-surface-container-high/40">
              <div className="w-2 h-2 rounded-full bg-tertiary shrink-0" />
              <div className="flex-1 font-medium">Playbook & Risk Evaluation</div>
              <div className="text-on-surface-variant font-mono">Rule engine</div>
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
