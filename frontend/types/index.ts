export type UserRole = "admin" | "reviewer" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  org_id: string;
  org_name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type ContractStatus = "pending" | "processing" | "completed" | "failed";

export interface Contract {
  id: string;
  title: string;
  file_name: string;
  file_size: number;
  content_type: string;
  status: ContractStatus;
  org_id: string;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface ContractListResponse {
  contracts: Contract[];
  total: number;
  skip: number;
  limit: number;
}

export interface ContractStatusResponse {
  contract_id: string;
  contract_status: ContractStatus;
  job_id?: string | null;
  job_status?: string | null;
  error_message?: string | null;
}

export interface ContractUploadResponse {
  contract_id: string;
  job_id: string;
  status: string;
  file_name: string;
  file_size: number;
  content_type: string;
  created_at: string;
}

export type RiskSeverity = "low" | "medium" | "high" | "critical";

export type RiskCategory =
  | "termination"
  | "liability"
  | "indemnification"
  | "payment"
  | "confidentiality"
  | "intellectual_property"
  | "data_privacy"
  | "security"
  | "governing_law"
  | "dispute_resolution"
  | "renewal"
  | "compliance"
  | "sla"
  | "insurance"
  | "other";

export interface RiskFinding {
  id: string;
  contract_id: string;
  version_id: string;
  org_id: string;
  chunk_id?: string | null;
  category: RiskCategory;
  severity: RiskSeverity;
  title: string;
  description: string;
  evidence: string;
  recommendation: string;
  confidence: number;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RiskFindingListResponse {
  items: RiskFinding[];
  total: number;
  skip: number;
  limit: number;
}

export interface MissingClause {
  id: string;
  contract_id: string;
  version_id: string;
  clause_type: string;
  confidence: number;
  reason: string;
  status: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface MissingClauseListResponse {
  contract_id: string;
  version_id: string;
  items: MissingClause[];
  total: number;
}

export interface RiskSummaryResponse {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export type AnalysisJobStatus = "queued" | "processing" | "completed" | "failed";

export interface AnalysisStatusResponse {
  contract_id: string;
  analysis_job_id?: string | null;
  status: AnalysisJobStatus;
  findings_count: number;
  error_message?: string | null;
}

export interface ChunkSearchResultItem {
  chunk_id: string;
  contract_id: string;
  version_id: string;
  chunk_index: number;
  content: string;
  similarity_score: number;
}

export interface ContractSearchResponse {
  contract_id: string;
  query: string;
  total_results: number;
  items: ChunkSearchResultItem[];
}

export interface RAGContextResponse {
  contract_id: string;
  query: string;
  context_text: string;
  chunks_count: number;
  total_chars: number;
  items: ChunkSearchResultItem[];
}

export interface GroundedCitation {
  chunk_id: string;
  chunk_index: number;
  similarity_score: number;
  quote: string;
}

export interface AskContractRequest {
  query: string;
  top_k?: number;
  min_score?: number;
  version_id?: string;
}

export interface AskContractResponse {
  contract_id: string;
  query: string;
  answer: string;
  confidence: number;
  citations: GroundedCitation[];
  retrieval_count: number;
  model: string;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorResponse {
  detail?: string | ApiErrorDetail[];
  message?: string;
  request_id?: string;
}
