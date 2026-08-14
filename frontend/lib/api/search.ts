import { apiRequest } from "./client";
import {
  AskContractRequest,
  AskContractResponse,
  ContractSearchResponse,
  RAGContextResponse,
} from "@/types";

export interface SearchChunksParams {
  query: string;
  top_k?: number;
  min_score?: number;
  version_id?: string;
}

export interface GetRAGContextParams {
  query: string;
  top_k?: number;
  min_score?: number;
  max_chunks?: number;
  max_chars?: number;
  version_id?: string;
}

export async function searchContractChunks(
  contractId: string,
  payload: SearchChunksParams
): Promise<ContractSearchResponse> {
  return apiRequest<ContractSearchResponse>(
    `/api/v1/contracts/${contractId}/search`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getRAGContext(
  contractId: string,
  payload: GetRAGContextParams
): Promise<RAGContextResponse> {
  return apiRequest<RAGContextResponse>(
    `/api/v1/contracts/${contractId}/retrieval`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function askContract(
  contractId: string,
  payload: AskContractRequest
): Promise<AskContractResponse> {
  return apiRequest<AskContractResponse>(
    `/api/v1/contracts/${contractId}/ask`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}
