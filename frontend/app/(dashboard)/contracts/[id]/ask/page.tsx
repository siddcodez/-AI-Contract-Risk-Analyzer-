"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { askContract } from "@/lib/api/search";
import { getContractDetails } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { AskContractResponse } from "@/types";
import {
  ArrowLeft,
  Bot,
  Sparkles,
  HelpCircle,
  Database,
  Quote,
  Copy,
  Check,
  ShieldAlert,
  Info,
  Layers,
} from "lucide-react";

export default function AskContractPage() {
  const params = useParams();
  const contractId = params.id as string;

  const [question, setQuestion] = useState("");
  const [askResult, setAskResult] = useState<AskContractResponse | null>(null);
  const [copied, setCopied] = useState(false);

  // Contract Details
  const { data: contract } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  const askMutation = useMutation({
    mutationFn: (queryText: string) =>
      askContract(contractId, {
        query: queryText,
        top_k: 8,
        min_score: 0.10,
      }),
    onSuccess: (data) => {
      setAskResult(data);
    },
  });

  const handleAsk = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim()) return;
    askMutation.mutate(question.trim());
  };

  const handleCopyAnswer = () => {
    if (askResult?.answer) {
      navigator.clipboard.writeText(askResult.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const sampleQuestions = [
    "Can the vendor increase the price without my approval?",
    "What are the termination and notice conditions?",
    "Is there an uncapped or high liability clause?",
    "What are the payment terms and invoicing timelines?",
    "Which state or country has governing jurisdiction?",
    "What are the confidentiality and NDA obligations?",
  ];

  const isInsufficientSupport =
    askResult?.answer?.toLowerCase().includes("couldn't find sufficient support") ||
    askResult?.confidence === 0;

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-outline-variant/30 pb-4">
        <Link href={`/contracts/${contractId}`}>
          <Button variant="secondary" size="sm" className="h-9 w-9 p-0">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-on-surface tracking-tight flex items-center gap-2">
            <span>Ask Your Contract</span>
            <span className="text-xs bg-primary/20 text-primary border border-primary/30 px-2 py-0.5 rounded font-normal">
              Grounded AI Q&A
            </span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Server-side grounded question answering for:{" "}
            <span className="text-on-surface font-medium">
              {contract?.title || contract?.file_name || contractId}
            </span>
          </p>
        </div>
      </div>

      {askMutation.isError && (
        <ErrorBanner
          message={
            askMutation.error instanceof Error
              ? askMutation.error.message
              : "Grounded Q&A generation failed. Please check your query or verify embeddings are indexed."
          }
        />
      )}

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Question Input & Quick Suggestions (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-primary" />
              <h2 className="text-sm font-semibold text-on-surface">
                Ask a Legal Question
              </h2>
            </div>

            <form onSubmit={handleAsk} className="flex flex-col gap-3">
              <textarea
                rows={4}
                placeholder="Ask any question about clauses, liabilities, renewal deadlines, price adjustments, or warranties..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full bg-surface-container-high border border-outline-variant rounded-lg p-3 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />

              <Button
                type="submit"
                variant="primary"
                className="h-10 gap-2 font-semibold text-xs justify-center"
                disabled={!question.trim() || askMutation.isPending}
                isLoading={askMutation.isPending}
              >
                <Sparkles className="w-4 h-4" />
                <span>Generate Grounded Answer</span>
              </Button>
            </form>

            {/* Popular Questions */}
            <div className="pt-3 border-t border-outline-variant/30 flex flex-col gap-2">
              <p className="text-xs font-semibold text-on-surface-variant flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Suggested Questions:</span>
              </p>
              <div className="flex flex-col gap-1.5">
                {sampleQuestions.map((q, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setQuestion(q);
                      askMutation.mutate(q);
                    }}
                    className="text-left text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high p-2 rounded-lg border border-outline-variant/40 transition-colors"
                  >
                    &bull; {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: AI Answer & Grounded Evidence (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {askMutation.isPending ? (
            <div className="bg-surface-container-low border border-outline-variant rounded-xl p-6 flex flex-col gap-4 shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary animate-spin" />
                  <span className="text-xs font-bold text-on-surface">
                    Retrieving context & generating answer...
                  </span>
                </div>
                <Skeleton className="h-5 w-24 rounded-full" />
              </div>
              <Skeleton className="h-20 w-full rounded-lg" />
              <div className="pt-4 border-t border-outline-variant/30 flex flex-col gap-3">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-16 w-full rounded-lg" />
              </div>
            </div>
          ) : askResult ? (
            <div className="flex flex-col gap-4">
              {/* Grounded AI Answer Card */}
              <div className="bg-surface-container-low border border-outline-variant rounded-xl p-6 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
                {/* Answer Card Header */}
                <div className="flex items-center justify-between flex-wrap gap-2 border-b border-outline-variant/40 pb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    <h3 className="text-sm font-bold text-on-surface">
                      Grounded Answer
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Support Confidence Badge */}
                    <div
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                        askResult.confidence >= 0.8
                          ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/40"
                          : askResult.confidence > 0.0
                          ? "bg-amber-950/40 text-amber-400 border-amber-800/40"
                          : "bg-surface-container-high text-on-surface-variant border-outline-variant"
                      }`}
                      title="Model confidence supported by retrieved contract context (not legal certainty)"
                    >
                      Support Confidence: {(askResult.confidence * 100).toFixed(0)}%
                    </div>

                    <button
                      type="button"
                      onClick={handleCopyAnswer}
                      className="text-xs text-on-surface-variant hover:text-on-surface bg-surface-container-high px-2 py-1 rounded border border-outline-variant/40 flex items-center gap-1 transition-colors"
                      title="Copy Answer Text"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Answer Content */}
                {isInsufficientSupport ? (
                  <div className="flex items-start gap-3 bg-amber-950/20 border border-amber-800/40 p-4 rounded-lg text-xs text-amber-200">
                    <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-amber-300">
                        Insufficient Evidence in Contract
                      </p>
                      <p className="mt-1 text-amber-200/90 leading-relaxed">
                        {askResult.answer}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-on-surface leading-relaxed font-sans bg-surface-container-high/40 p-4 rounded-lg border border-outline-variant/30">
                    {askResult.answer}
                  </div>
                )}

                {/* Model & Retrieval Metadata Footer */}
                <div className="flex items-center justify-between text-[10px] text-on-surface-variant/80 pt-2 border-t border-outline-variant/20">
                  <span>
                    Retrieved from {askResult.retrieval_count} context chunk
                    {askResult.retrieval_count !== 1 ? "s" : ""}
                  </span>
                  <span className="font-mono">Engine: {askResult.model}</span>
                </div>
              </div>

              {/* Supporting Evidence Citations Card */}
              {askResult.citations && askResult.citations.length > 0 && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs text-on-surface-variant font-semibold px-1">
                    <div className="flex items-center gap-1.5 text-primary">
                      <Database className="w-3.5 h-3.5" />
                      <span>Verified Contract Citations ({askResult.citations.length})</span>
                    </div>
                    <span className="text-[11px]">Verbatim clause evidence</span>
                  </div>

                  {askResult.citations.map((citation, idx) => (
                    <div
                      key={citation.chunk_id || idx}
                      className="bg-surface-container-low border border-outline-variant rounded-xl p-4 shadow-sm flex flex-col gap-2.5 hover:border-outline transition-colors"
                    >
                      <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-primary bg-primary-container/20 px-2 py-0.5 rounded border border-primary/30">
                            Citation #{idx + 1}
                          </span>
                          <span className="text-xs text-on-surface-variant font-mono">
                            Chunk {citation.chunk_index}
                          </span>
                        </div>

                        <span className="text-xs font-semibold text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                          {(citation.similarity_score * 100).toFixed(0)}% Relevance
                        </span>
                      </div>

                      <div className="bg-surface-container-high/60 rounded-lg p-3 border-l-2 border-primary font-mono text-xs text-on-surface/90 leading-relaxed">
                        &ldquo;{citation.quote}&rdquo;
                      </div>

                      <div className="text-[10px] text-on-surface-variant font-mono truncate">
                        Chunk ID: {citation.chunk_id}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              icon={Bot}
              title="Ask Contract Questions"
              description="Ask questions in the left panel to receive factual, LLM-generated answers strictly grounded in retrieved contract clauses."
            />
          )}
        </div>
      </div>
    </div>
  );
}
