"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "@/lib/api/audit_logs";
import { useAuth } from "@/lib/auth/store";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import {
  Shield,
  FileText,
  User,
  Clock,
  Filter,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { AuditLog } from "@/types";

export default function AuditLogsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [actionFilter, setActionFilter] = useState<string>("");
  const [entityFilter, setEntityFilter] = useState<string>("");
  const [skip, setSkip] = useState<number>(0);
  const limit = 25;

  const {
    data: auditData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["audit-logs", actionFilter, entityFilter, skip],
    queryFn: () =>
      listAuditLogs({
        action: actionFilter || undefined,
        entity_type: entityFilter || undefined,
        skip,
        limit,
      }),
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div className="bg-surface-container-low border border-outline-variant rounded-xl p-8 text-center flex flex-col items-center gap-3">
        <Shield className="w-8 h-8 text-red-400" />
        <h2 className="text-base font-bold text-on-surface">Access Restricted</h2>
        <p className="text-xs text-on-surface-variant max-w-sm">
          Audit logs contain organization-level compliance and security events. Admin privileges are required to view this page.
        </p>
      </div>
    );
  }

  const logs: AuditLog[] = auditData?.items || [];
  const total = auditData?.total || 0;
  const totalPages = Math.ceil(total / limit) || 1;
  const currentPage = Math.floor(skip / limit) + 1;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant/30 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            <h1 className="text-2xl font-bold text-on-surface tracking-tight">
              Organization Audit Trail
            </h1>
          </div>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Immutable, append-only activity and compliance event logs.
          </p>
        </div>
      </div>

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load audit logs"}
          onRetry={() => refetch()}
        />
      )}

      {/* Filter Bar */}
      <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5 text-on-surface-variant font-semibold">
          <Filter className="w-3.5 h-3.5" />
          <span>Filters:</span>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setSkip(0);
          }}
          className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary"
        >
          <option value="">All Actions</option>
          <option value="CONTRACT_UPLOADED">CONTRACT_UPLOADED</option>
          <option value="PROCESSING_STARTED">PROCESSING_STARTED</option>
          <option value="PROCESSING_FAILED">PROCESSING_FAILED</option>
          <option value="CLAUSE_REVIEWED">CLAUSE_REVIEWED</option>
          <option value="CLAUSE_APPROVED">CLAUSE_APPROVED</option>
          <option value="CLAUSE_REJECTED">CLAUSE_REJECTED</option>
          <option value="PLAYBOOK_RULE_CREATED">PLAYBOOK_RULE_CREATED</option>
          <option value="REPORT_GENERATED">REPORT_GENERATED</option>
        </select>

        <select
          value={entityFilter}
          onChange={(e) => {
            setEntityFilter(e.target.value);
            setSkip(0);
          }}
          className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary"
        >
          <option value="">All Entities</option>
          <option value="contract">Contract</option>
          <option value="risk_finding">Risk Finding</option>
          <option value="playbook">Playbook</option>
          <option value="report">Report</option>
        </select>

        <span className="text-on-surface-variant ml-auto font-mono text-[11px]">
          Total Events: {total}
        </span>
      </div>

      {/* Logs Table */}
      <div className="bg-surface-container-low border border-outline-variant rounded-xl overflow-hidden shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-container-high/60 border-b border-outline-variant text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Entity</th>
                <th className="py-3 px-4">Safe Metadata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="py-3 px-4" colSpan={5}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-on-surface-variant italic">
                    No audit records matching your criteria.
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const isApproved = log.action.includes("APPROVED");
                  const isRejected = log.action.includes("REJECTED") || log.action.includes("FAILED");

                  return (
                    <tr key={log.id} className="hover:bg-surface-container-high/30 transition-colors">
                      <td className="py-3 px-4 text-on-surface font-mono text-[11px] whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-on-surface font-medium">
                        {log.user_email || "System / Worker"}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`font-mono font-bold text-[10px] uppercase px-2 py-0.5 rounded ${
                            isApproved
                              ? "bg-emerald-500/15 text-emerald-400"
                              : isRejected
                              ? "bg-red-500/15 text-red-400"
                              : "bg-primary/10 text-primary"
                          }`}
                        >
                          {log.action}
                        </span>
                      </td>
                      <td className="py-3 px-4 capitalize font-mono text-on-surface-variant">
                        {log.entity_type}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-on-surface-variant max-w-md truncate">
                        {JSON.stringify(log.metadata_json || {})}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="bg-surface-container-high/40 border-t border-outline-variant p-3 flex items-center justify-between text-xs text-on-surface-variant">
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={skip === 0}
                onClick={() => setSkip(Math.max(0, skip - limit))}
                className="px-3 py-1 rounded bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-highest"
              >
                Previous
              </button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setSkip(skip + limit)}
                className="px-3 py-1 rounded bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-highest"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
