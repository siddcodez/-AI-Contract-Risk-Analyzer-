import { ApiErrorResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  data?: ApiErrorResponse;
  requestId?: string;

  constructor(message: string, status: number, data?: ApiErrorResponse) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.requestId = data?.request_id;
  }
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("contractiq_token");
}

export function setAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("contractiq_token", token);
  }
}

export function removeAuthToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("contractiq_token");
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // If not sending FormData, set JSON content type by default
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(
      "Unable to connect to server. Please check your network connection.",
      0
    );
  }

  if (response.status === 401) {
    removeAuthToken();
    if (
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/signup")
    ) {
      window.location.href = "/login";
    }
  }

  if (!response.ok) {
    let errorData: ApiErrorResponse | undefined;
    let errorMessage = `Request failed with status ${response.status}`;

    try {
      errorData = await response.json();
      if (errorData) {
        if (typeof errorData.detail === "string") {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
          errorMessage = errorData.detail.map((d) => d.msg).join(", ");
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }
      }
    } catch {
      // JSON parse failed, use fallback message
    }

    if (response.status === 403) {
      errorMessage = errorMessage || "You do not have permission to perform this action.";
    } else if (response.status === 404) {
      errorMessage = errorMessage || "The requested resource was not found.";
    } else if (response.status === 429) {
      errorMessage = "Rate limit exceeded. Please wait a moment before trying again.";
    } else if (response.status >= 500) {
      errorMessage = "An internal server error occurred. Please try again later.";
    }

    throw new ApiError(errorMessage, response.status, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
