"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listFindings, submitFindingReview, listFindingReviews } from "@/lib/api/analysis";
import { getContractDetails } from "@/lib/api/contracts";
import { useAuth } from "@/lib/auth/store";
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
  ShieldAlert,
  XCircle,
} from "lucide-react";

export default function FindingDetailPage() {
  const params = useParams();
  const contractId = params.id as string;
  const findingId = params.findingId as string;
  const [copied, setCopied] = useState(false);
  const { user } = useAuth();
  const isReviewerOrAdmin = user?.role === "admin" || user?.role === "reviewer";

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

        {/* Section 4: Human Review & Decision Workflow (Phase 11) */}
        <ReviewDecisionSection
          contractId={contractId}
          findingId={findingId}
          currentStatus={finding.status || "pending_review"}
          isReviewerOrAdmin={isReviewerOrAdmin}
        />
      </div>
    </div>
  );
}

function ReviewDecisionSection({
  contractId,
  findingId,
  currentStatus,
  isReviewerOrAdmin,
}: {
  contractId: string;
  findingId: string;
  currentStatus: string;
  isReviewerOrAdmin: boolean;
}) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState(currentStatus);

  const { data: reviewsData } = useQuery({
    queryKey: ["finding-reviews", contractId, findingId],
    queryFn: () => listFindingReviews(contractId, findingId),
    enabled: !!contractId && !!findingId,
  });

  const reviewMutation = useMutation({
    mutationFn: (action: "approved" | "rejected") =>
      submitFindingReview(contractId, findingId, action, comment || undefined),
    onSuccess: (newReview) => {
      setStatus(newReview.action);
      setComment("");
      queryClient.invalidateQueries({ queryKey: ["findings", contractId] });
      queryClient.invalidateQueries({ queryKey: ["finding-reviews", contractId, findingId] });
    },
  });

  const isApproved = status === "approved";
  const isRejected = status === "rejected";

  return (
    <section className="bg-surface-container-low p-6 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.4)] border border-outline-variant/50 flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-primary" />
          <span>Reviewer Decision & Signoff</span>
        </h2>
        <span
          className={`text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full ${
            isApproved
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : isRejected
              ? "bg-red-500/15 text-red-400 border border-red-500/30"
              : "bg-yellow-500/15 text-yellow-400 border border-yellow-500/30"
          }`}
        >
          {status.replace("_", " ")}
        </span>
      </div>

      {isReviewerOrAdmin ? (
        <div className="flex flex-col gap-3">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Add reviewer notes or mitigation justification (optional)..."
            rows={2}
            className="w-full bg-surface-container-high border border-outline-variant rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:border-primary resize-none"
          />

          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              isLoading={reviewMutation.isPending && reviewMutation.variables === "approved"}
              onClick={() => reviewMutation.mutate("approved")}
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Approve Finding</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              isLoading={reviewMutation.isPending && reviewMutation.variables === "rejected"}
              onClick={() => reviewMutation.mutate("rejected")}
              className="gap-1.5 border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs font-bold"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Reject / Dismiss</span>
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-on-surface-variant italic">
          You are viewing this contract in read-only mode. Reviewer or Admin role is required to submit signoffs.
        </p>
      )}

      {/* Review History Trail */}
      {reviewsData && reviewsData.items.length > 0 && (
        <div className="border-t border-outline-variant/40 pt-3 flex flex-col gap-2">
          <span className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">
            Review History ({reviewsData.total})
          </span>
          <div className="flex flex-col gap-2">
            {reviewsData.items.map((rev) => (
              <div
                key={rev.id}
                className="bg-surface-container-high/40 border border-outline-variant/30 rounded-lg p-2.5 flex flex-col gap-1 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold capitalize text-on-surface flex items-center gap-1.5">
                    {rev.action === "approved" ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-red-400" />
                    )}
                    {rev.action}
                  </span>
                  <span className="text-[10px] text-on-surface-variant font-mono">
                    {new Date(rev.created_at).toLocaleString()}
                  </span>
                </div>
                {rev.comment && (
                  <p className="text-on-surface-variant text-[11px] italic pl-5">
                    &ldquo;{rev.comment}&rdquo;
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

