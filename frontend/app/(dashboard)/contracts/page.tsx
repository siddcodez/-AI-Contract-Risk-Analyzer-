"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listContracts } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate, formatBytes } from "@/lib/utils";
import {
  Upload,
  FileText,
  Search,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

export default function ContractsPage() {
  const [page, setPage] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const pageSize = 10;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["contracts", { skip: page * pageSize, limit: pageSize }],
    queryFn: () => listContracts({ skip: page * pageSize, limit: pageSize }),
  });

  const contracts = data?.contracts || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const filteredContracts = contracts.filter((c) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.title.toLowerCase().includes(term) ||
      c.file_name.toLowerCase().includes(term) ||
      c.status.toLowerCase().includes(term)
    );
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
            Contracts
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Manage, review, and analyze your active legal documents.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative">
            <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search contracts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-surface-container-high border border-outline-variant rounded-lg pl-9 pr-3 py-2 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary w-56 md:w-64 transition-all"
            />
          </div>
          <Link href="/upload">
            <Button variant="primary" className="gap-2 h-10">
              <Upload className="w-4 h-4" />
              <span>Upload Contract</span>
            </Button>
          </Link>
        </div>
      </div>

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load contracts"}
          onRetry={() => refetch()}
        />
      )}

      {/* Contracts Table Card */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-outline-variant bg-surface-container-highest/30">
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Contract Name
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Size
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Uploaded
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant">
                  Status
                </th>
                <th className="p-4 text-xs font-semibold text-on-surface-variant text-right">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30 text-sm text-on-surface">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="p-4">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <Skeleton className="w-6 h-6 rounded" />
                        <Skeleton className="h-4 w-52" />
                      </div>
                    </td>
                    <td className="p-4">
                      <Skeleton className="h-4 w-16" />
                    </td>
                    <td className="p-4">
                      <Skeleton className="h-4 w-24" />
                    </td>
                    <td className="p-4">
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </td>
                    <td className="p-4 text-right">
                      <Skeleton className="h-8 w-20 ml-auto" />
                    </td>
                  </tr>
                ))
              ) : filteredContracts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-10">
                    <EmptyState
                      title={searchTerm ? "No matching contracts" : "No contracts found"}
                      description={
                        searchTerm
                          ? "Try adjusting your search query or clear the filter."
                          : "Upload contracts to start automated risk analysis and semantic search."
                      }
                      action={
                        searchTerm ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setSearchTerm("")}
                          >
                            Clear Search
                          </Button>
                        ) : (
                          <Link href="/upload">
                            <Button variant="primary" size="sm" className="gap-1.5">
                              <Upload className="w-4 h-4" />
                              <span>Upload Contract</span>
                            </Button>
                          </Link>
                        )
                      }
                    />
                  </td>
                </tr>
              ) : (
                filteredContracts.map((contract) => (
                  <tr
                    key={contract.id}
                    className="hover:bg-surface-container-high/50 transition-colors group"
                  >
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-on-surface-variant group-hover:text-primary transition-colors shrink-0" />
                        <div>
                          <Link
                            href={`/contracts/${contract.id}`}
                            className="font-semibold text-on-surface hover:text-primary transition-colors block"
                          >
                            {contract.title || contract.file_name}
                          </Link>
                          {contract.title && (
                            <span className="text-xs text-on-surface-variant font-mono">
                              {contract.file_name}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="p-4 text-xs font-mono text-on-surface-variant">
                      {formatBytes(contract.file_size)}
                    </td>
                    <td className="p-4 text-xs text-on-surface-variant">
                      {formatDate(contract.created_at)}
                    </td>
                    <td className="p-4">
                      <StatusBadge status={contract.status} />
                    </td>
                    <td className="p-4 text-right">
                      <Link href={`/contracts/${contract.id}`}>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-8 gap-1.5 text-xs"
                        >
                          <span>Open</span>
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

        {/* Pagination footer */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-variant">
            <span>
              Showing {page * pageSize + 1} to{" "}
              {Math.min((page + 1) * pageSize, total)} of {total} contracts
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="px-2 font-semibold text-on-surface">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                className="h-8 w-8 p-0"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
