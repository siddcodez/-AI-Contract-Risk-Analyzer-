import { apiRequest } from "./client";
import {
  AnalysisStatusResponse,
  RiskCategory,
  RiskFindingListResponse,
  RiskSeverity,
  RiskSummaryResponse,
} from "@/types";

export interface ListFindingsParams {
  category?: RiskCategory;
  severity?: RiskSeverity;
  skip?: number;
  limit?: number;
}

export async function getAnalysisStatus(
  contractId: string
): Promise<AnalysisStatusResponse> {
  return apiRequest<AnalysisStatusResponse>(
    `/api/v1/contracts/${contractId}/analysis`,
    {
      method: "GET",
    }
  );
}

export async function triggerAnalysis(
  contractId: string
): Promise<AnalysisStatusResponse> {
  return apiRequest<AnalysisStatusResponse>(
    `/api/v1/contracts/${contractId}/analyze`,
    {
      method: "POST",
    }
  );
}

export async function listFindings(
  contractId: string,
  params: ListFindingsParams = {}
): Promise<RiskFindingListResponse> {
  const searchParams = new URLSearchParams();
  if (params.category) searchParams.set("category", params.category);
  if (params.severity) searchParams.set("severity", params.severity);
  if (params.skip !== undefined) searchParams.set("skip", params.skip.toString());
  if (params.limit !== undefined) searchParams.set("limit", params.limit.toString());

  const queryStr = searchParams.toString();
  const endpoint = `/api/v1/contracts/${contractId}/findings${queryStr ? `?${queryStr}` : ""}`;

  return apiRequest<RiskFindingListResponse>(endpoint, {
    method: "GET",
  });
}

export async function getFindingsSummary(
  contractId: string
): Promise<RiskSummaryResponse> {
  return apiRequest<RiskSummaryResponse>(
    `/api/v1/contracts/${contractId}/findings/summary`,
    {
      method: "GET",
    }
  );
}

export async function getMissingClauses(
  contractId: string,
  versionId?: string
): Promise<import("@/types").MissingClauseListResponse> {
  const queryStr = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return apiRequest<import("@/types").MissingClauseListResponse>(
    `/api/v1/contracts/${contractId}/missing-clauses${queryStr}`,
    {
      method: "GET",
    }
  );
}

export async function compareVersions(
  contractId: string,
  fromVersionId: string,
  toVersionId: string,
  refresh: boolean = false
): Promise<import("@/types").ContractComparisonResponse> {
  const params = new URLSearchParams({
    from_version_id: fromVersionId,
    to_version_id: toVersionId,
    refresh: refresh.toString(),
  });
  return apiRequest<import("@/types").ContractComparisonResponse>(
    `/api/v1/contracts/${contractId}/compare?${params.toString()}`,
    {
      method: "GET",
    }
  );
}

export async function submitFindingReview(
  contractId: string,
  findingId: string,
  action: "approved" | "rejected",
  comment?: string
): Promise<import("@/types").ReviewAction> {
  return apiRequest<import("@/types").ReviewAction>(
    `/api/v1/contracts/${contractId}/findings/${findingId}/review`,
    {
      method: "POST",
      body: JSON.stringify({ action, comment }),
    }
  );
}

export async function listFindingReviews(
  contractId: string,
  findingId: string
): Promise<import("@/types").ReviewActionListResponse> {
  return apiRequest<import("@/types").ReviewActionListResponse>(
    `/api/v1/contracts/${contractId}/findings/${findingId}/reviews`,
    {
      method: "GET",
    }
  );
}



