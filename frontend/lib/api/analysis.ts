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
