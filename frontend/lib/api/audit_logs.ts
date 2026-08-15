import { apiRequest } from "./client";
import { AuditLogListResponse } from "@/types";

export interface ListAuditLogsParams {
  action?: string;
  entity_type?: string;
  skip?: number;
  limit?: number;
}

export async function listAuditLogs(
  params: ListAuditLogsParams = {}
): Promise<AuditLogListResponse> {
  const { action, entity_type, skip = 0, limit = 50 } = params;
  const searchParams = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  if (action) searchParams.append("action", action);
  if (entity_type) searchParams.append("entity_type", entity_type);

  return apiRequest<AuditLogListResponse>(
    `/api/v1/audit-logs?${searchParams.toString()}`,
    {
      method: "GET",
    }
  );
}
