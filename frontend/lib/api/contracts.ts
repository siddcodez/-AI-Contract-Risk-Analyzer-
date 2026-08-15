import { apiRequest } from "./client";
import {
  Contract,
  ContractListResponse,
  ContractStatusResponse,
  ContractUploadResponse,
} from "@/types";

export interface ListContractsParams {
  skip?: number;
  limit?: number;
}

export async function listContracts(
  params: ListContractsParams = {}
): Promise<ContractListResponse> {
  const { skip = 0, limit = 20 } = params;
  const searchParams = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  return apiRequest<ContractListResponse>(
    `/api/v1/contracts/list?${searchParams.toString()}`,
    {
      method: "GET",
    }
  );
}

export async function getContractDetails(contractId: string): Promise<Contract> {
  return apiRequest<Contract>(`/api/v1/contracts/${contractId}/details`, {
    method: "GET",
  });
}

export async function getContractStatus(
  contractId: string
): Promise<ContractStatusResponse> {
  return apiRequest<ContractStatusResponse>(
    `/api/v1/contracts/${contractId}/status`,
    {
      method: "GET",
    }
  );
}

export async function uploadContract(
  file: File,
  title?: string
): Promise<ContractUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (title) {
    formData.append("title", title);
  }

  return apiRequest<ContractUploadResponse>("/api/v1/contracts/upload", {
    method: "POST",
    body: formData,
  });
}

export async function listContractVersions(
  contractId: string
): Promise<import("@/types").ContractVersion[]> {
  return apiRequest<import("@/types").ContractVersion[]>(
    `/api/v1/contracts/${contractId}/versions`,
    {
      method: "GET",
    }
  );
}

export interface ReportStatusResponse {
  id: string;
  contract_id: string;
  version_id: string;
  status: string;
  storage_key?: string | null;
  file_size?: number | null;
  error_message?: string | null;
  download_url?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export async function triggerReportGeneration(
  contractId: string,
  versionId?: string
): Promise<{ job_id: string; status: string }> {
  const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return apiRequest<{ job_id: string; status: string }>(
    `/api/v1/contracts/${contractId}/reports/generate${query}`,
    {
      method: "POST",
    }
  );
}

export async function getLatestReportStatus(
  contractId: string,
  versionId?: string
): Promise<ReportStatusResponse> {
  const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return apiRequest<ReportStatusResponse>(
    `/api/v1/contracts/${contractId}/reports/latest${query}`,
    {
      method: "GET",
    }
  );
}


