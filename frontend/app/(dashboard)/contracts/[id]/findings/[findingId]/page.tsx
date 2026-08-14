"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listFindings } from "@/lib/api/analysis";
import { getContractDetails } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  ArrowLeft,
  Lightbulb,
  FileSearch,
  CheckCircle2,
  Copy,
  Info,
} from "lucide-react";

export default function FindingDetailPage() {
  const params = useParams();
  const contractId = params.id as string;
  const findingId = params.findingId as string;
  const [copied, setCopied] = useState(false);

  // Contract Details
  const { data: contract } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  // Query findings to find the current one
  const { data: findingsData, isLoading, isError, error } = useQuery({
    queryKey: ["findings", contractId],
    queryFn: () => listFindings(contractId, { limit: 100 }),
    enabled: !!contractId,
  });

  const finding = findingsData?.items.find((f) => f.id === findingId);

  const copyRecommendation = () => {
    if (finding?.recommendation) {
      navigator.clipboard.writeText(finding.recommendation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isError) {
    return (
      <div className="py-6">
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load finding"}
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 py-6 max-w-4xl mx-auto">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (!finding) {
    return (
      <div className="py-12 max-w-xl mx-auto text-center flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-surface-container-high flex items-center justify-center text-on-surface-variant">
          <Info className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-on-surface">Finding Not Found</h2>
        <p className="text-sm text-on-surface-variant">
          The requested risk finding record could not be found for this contract.
        </p>
        <Link href={`/contracts/${contractId}/analysis`}>
          <Button variant="secondary" size="sm">
            Back to Analysis
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs text-on-surface-variant font-semibold">
        <Link
          href={`/contracts/${contractId}/analysis`}
          className="hover:text-primary transition-colors flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Analysis</span>
        </Link>
        <span className="text-outline">/</span>
        <span className="text-on-surface truncate max-w-xs">
          {contract?.title || contract?.file_name || contractId}
        </span>
      </div>

      {/* Header Section */}
      <header className="flex flex-col gap-3 border-b border-outline-variant/30 pb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <RiskBadge severity={finding.severity} />
          <span className="border border-primary-container text-primary-fixed-dim px-3 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider">
            {finding.category.toUpperCase().replace("_", " ")}
          </span>
          <span className="text-xs text-on-surface-variant ml-auto">
            Confidence:{" "}
            <strong className="text-on-surface">
              {(finding.confidence * 100).toFixed(0)}%
            </strong>
          </span>
        </div>

        <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
          {finding.title}
        </h1>
      </header>

      {/* Main Content Sections */}
      <div className="flex flex-col gap-6">
        {/* Section 1: Why this matters (Matching Stitch) */}
        <section className="bg-surface-container-low p-6 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.4)] border border-outline-variant/50 flex flex-col gap-3">
          <h2 className="text-base font-bold text-primary-fixed-dim flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-primary" />
            <span>Why this matters</span>
          </h2>
          <p className="text-sm text-on-surface-variant leading-relaxed">
            {finding.description}
          </p>
        </section>

        {/* Section 2: Evidence from Contract (Matching Stitch) */}
        <section className="bg-surface-container-low p-6 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.4)] border border-outline-variant/50 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-primary-fixed-dim flex items-center gap-2">
              <FileSearch className="w-4 h-4 text-primary" />
              <span>Evidence from Contract</span>
            </h2>
            {finding.chunk_id && (
              <span className="text-[10px] font-mono text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded">
                Chunk ID: {finding.chunk_id.slice(0, 8)}...
              </span>
            )}
          </div>

          <p className="text-xs text-on-surface-variant">
            Grounded clause segment extracted from the indexed document:
          </p>

          <div className="bg-surface-container-lowest border-l-4 border-primary-container p-4 rounded-r-lg font-mono text-xs text-on-surface/90 overflow-x-auto shadow-inner leading-relaxed">
            &ldquo;{finding.evidence}&rdquo;
          </div>
        </section>

        {/* Section 3: Recommended Action (Matching Stitch) */}
        <section className="bg-surface-container-low p-6 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.4)] border border-outline-variant/50 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Recommended Action & Redline</span>
            </h2>
            <Button
              variant="secondary"
              size="sm"
              onClick={copyRecommendation}
              className="h-8 gap-1.5 text-xs"
            >
              <Copy className="w-3.5 h-3.5" />
              <span>{copied ? "Copied!" : "Copy Proposed Text"}</span>
            </Button>
          </div>

          <div className="bg-surface-container-high/60 rounded-lg p-4 border border-outline-variant text-xs text-on-surface leading-relaxed font-mono">
            {finding.recommendation}
          </div>
        </section>
      </div>
    </div>
  );
}
