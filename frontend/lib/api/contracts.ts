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
