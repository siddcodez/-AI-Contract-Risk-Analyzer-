"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { searchContractChunks } from "@/lib/api/search";
import { getContractDetails } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { ContractSearchResponse } from "@/types";
import {
  ArrowLeft,
  Search,
  SlidersHorizontal,
  Sparkles,
  FileText,
  Percent,
} from "lucide-react";

export default function SemanticSearchPage() {
  const params = useParams();
  const contractId = params.id as string;

  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.2);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [searchResult, setSearchResult] = useState<ContractSearchResponse | null>(
    null
  );

  // Contract Details
  const { data: contract } = useQuery({
    queryKey: ["contract", contractId],
    queryFn: () => getContractDetails(contractId),
    enabled: !!contractId,
  });

  const searchMutation = useMutation({
    mutationFn: (searchQuery: string) =>
      searchContractChunks(contractId, {
        query: searchQuery,
        top_k: topK,
        min_score: minScore,
      }),
    onSuccess: (data) => {
      setSearchResult(data);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate(query.trim());
  };

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-outline-variant/30 pb-4">
        <Link href={`/contracts/${contractId}`}>
          <Button variant="secondary" size="sm" className="h-9 w-9 p-0">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-on-surface tracking-tight">
            Semantic Vector Search
          </h1>
          <p className="text-xs text-on-surface-variant mt-0.5">
            pgvector similarity search across indexed clauses for:{" "}
            <span className="text-on-surface font-medium">
              {contract?.title || contract?.file_name || contractId}
            </span>
          </p>
        </div>
      </div>

      {searchMutation.isError && (
        <ErrorBanner
          message={
            searchMutation.error instanceof Error
              ? searchMutation.error.message
              : "Search failed. Make sure the contract chunks have been indexed."
          }
        />
      )}

      {/* Search Input Box */}
      <form
        onSubmit={handleSearch}
        className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4"
      >
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="e.g. limitation of liability, payment terms, termination for convenience..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="bg-surface-container-high border border-outline-variant rounded-lg pl-9 pr-3 py-2.5 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary w-full"
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            className="h-10 px-6 gap-2 text-sm font-semibold shrink-0"
            disabled={!query.trim() || searchMutation.isPending}
            isLoading={searchMutation.isPending}
          >
            <Sparkles className="w-4 h-4" />
            <span>Search</span>
          </Button>
        </div>

        {/* Advanced Filters Toggle */}
        <div className="flex items-center justify-between pt-2 text-xs border-t border-outline-variant/30">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>{showAdvanced ? "Hide Options" : "Search Parameters"}</span>
          </button>

          <span className="text-on-surface-variant">
            Embeddings: 1536-dim • Cosine Similarity
          </span>
        </div>

        {/* Advanced Parameters Drawer */}
        {showAdvanced && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-outline-variant/30 text-xs">
            <div>
              <label className="block text-on-surface-variant font-semibold mb-1">
                Top Results (K): {topK}
              </label>
              <input
                type="range"
                min="1"
                max="20"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>
            <div>
              <label className="block text-on-surface-variant font-semibold mb-1">
                Minimum Score Threshold: {minScore.toFixed(2)}
              </label>
              <input
                type="range"
                min="0.0"
                max="0.9"
                step="0.05"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>
          </div>
        )}
      </form>

      {/* Results Section */}
      <div className="flex flex-col gap-4">
        {searchMutation.isPending ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="bg-surface-container-low border border-outline-variant rounded-xl p-5 flex flex-col gap-3"
            >
              <div className="flex justify-between items-center">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-5 w-16" />
              </div>
              <Skeleton className="h-16 w-full mt-2" />
            </div>
          ))
        ) : searchResult ? (
          searchResult.items.length === 0 ? (
            <EmptyState
              icon={Search}
              title="No Matching Chunks Found"
              description={`No clauses matched your query "${searchResult.query}" with a similarity score >= ${minScore.toFixed(2)}.`}
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMinScore(0.1)}
                >
                  Lower Score Threshold
                </Button>
              }
            />
          ) : (
            <>
              <div className="flex items-center justify-between text-xs text-on-surface-variant px-1">
                <span>
                  Found <strong>{searchResult.total_results}</strong> relevant clause chunks for &ldquo;{searchResult.query}&rdquo;
                </span>
                <span>Sorted by pgvector similarity</span>
              </div>

              {searchResult.items.map((item, index) => (
                <div
                  key={item.chunk_id}
                  className="bg-surface-container-low border border-outline-variant rounded-xl p-5 shadow-sm flex flex-col gap-3 hover:border-outline transition-colors"
                >
                  <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-primary bg-primary-container/20 px-2 py-0.5 rounded border border-primary/30">
                        #{index + 1}
                      </span>
                      <span className="text-xs text-on-surface-variant font-mono">
                        Chunk Index {item.chunk_index}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                      <Percent className="w-3 h-3" />
                      <span>{(item.similarity_score * 100).toFixed(1)}% Match</span>
                    </div>
                  </div>

                  <p className="text-xs text-on-surface font-mono leading-relaxed bg-surface-container-high/60 p-3.5 rounded-lg border border-outline-variant/40">
                    {item.content}
                  </p>
                </div>
              ))}
            </>
          )
        ) : (
          <EmptyState
            icon={Search}
            title="Semantic Clause Search"
            description="Type keywords or natural language questions to search through contract clauses using pgvector embeddings."
          />
        )}
      </div>
    </div>
  );
}
