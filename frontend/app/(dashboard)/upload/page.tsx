"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { uploadContract, getContractStatus } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorBanner } from "@/components/ui/error-banner";
import { cn, formatBytes } from "@/lib/utils";
import {
  Upload,
  FileText,
  Check,
  Loader2,
  Clock,
  ArrowRight,
  X,
  FileCheck,
} from "lucide-react";

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Post-upload processing tracking
  const [uploadedContractId, setUploadedContractId] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<
    "idle" | "uploading" | "queued" | "processing" | "completed" | "failed"
  >("idle");

  // Allowed file extensions
  const allowedExtensions = [".pdf", ".docx", ".txt"];

  const validateAndSetFile = (selectedFile: File) => {
    setError(null);
    const ext = "." + selectedFile.name.split(".").pop()?.toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setError("Only PDF, DOCX, or TXT documents are supported.");
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      setError("File size exceeds the 50MB limit.");
      return;
    }
    setFile(selectedFile);
    if (!title) {
      // Default title from file name without extension
      const defaultTitle = selectedFile.name.replace(/\.[^/.]+$/, "");
      setTitle(defaultTitle);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setProcessingStatus("uploading");

    try {
      const response = await uploadContract(file, title.trim() || undefined);
      setUploadedContractId(response.contract_id);
      setProcessingStatus("processing");
    } catch (err: unknown) {
      setProcessingStatus("failed");
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during contract upload.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  // Poll processing status if a contract is currently processing
  useEffect(() => {
    if (!uploadedContractId || processingStatus === "completed" || processingStatus === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await getContractStatus(uploadedContractId);
        if (res.contract_status === "completed") {
          setProcessingStatus("completed");
          clearInterval(interval);
        } else if (res.contract_status === "failed") {
          setProcessingStatus("failed");
          setError(res.error_message || "Document processing failed");
          clearInterval(interval);
        } else if (res.contract_status === "processing") {
          setProcessingStatus("processing");
        }
      } catch {
        // Continue polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [uploadedContractId, processingStatus]);

  // Determine stage progression for visual timeline
  const getStepState = (stepIndex: number) => {
    if (processingStatus === "completed") return "done";
    if (processingStatus === "failed") return stepIndex <= 1 ? "done" : "idle";
    if (processingStatus === "processing") {
      if (stepIndex <= 2) return "done";
      if (stepIndex === 3) return "active";
      return "idle";
    }
    if (processingStatus === "uploading" || processingStatus === "queued") {
      if (stepIndex === 1) return "active";
      return "idle";
    }
    return "idle";
  };

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
          Upload Contract
        </h1>
        <p className="text-sm text-on-surface-variant mt-1">
          Upload legal documents for AI-powered clause extraction and risk analysis.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Upload Box Card */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant p-6 shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-5">
        <div>
          <h2 className="text-lg font-semibold text-primary">Select Document</h2>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Drag and drop your contract, or click to browse files
          </p>
        </div>

        {/* Dropzone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "min-h-[200px] border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-6 gap-3 cursor-pointer transition-all",
            isDragging
              ? "border-primary bg-surface-container-high"
              : "border-outline-variant hover:border-primary hover:bg-surface-container-high/50"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="w-12 h-12 rounded-xl bg-surface-container-high flex items-center justify-center border border-outline-variant text-on-surface-variant">
            <Upload className="w-6 h-6 text-primary" />
          </div>

          <div className="text-center">
            <p className="text-sm font-semibold text-on-surface">
              {file ? file.name : "Drag files here or click to browse"}
            </p>
            <p className="text-xs text-on-surface-variant mt-1">
              PDF, DOCX, or TXT (max 50MB)
            </p>
          </div>
        </div>

        {/* Selected file preview & title input */}
        {file && (
          <div className="flex flex-col gap-3 pt-2">
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-high border border-outline-variant">
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="w-5 h-5 text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-on-surface truncate">
                    {file.name}
                  </p>
                  <p className="text-xs text-on-surface-variant font-mono">
                    {formatBytes(file.size)}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="p-1 rounded-md text-on-surface-variant hover:text-on-surface hover:bg-surface-bright"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant mb-1.5">
                Contract Title (Optional)
              </label>
              <Input
                placeholder="e.g. Master Services Agreement 2024"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Upload Action */}
        <Button
          type="button"
          variant="primary"
          className="w-full h-11 text-sm font-bold mt-2"
          disabled={!file || isUploading || processingStatus === "processing"}
          isLoading={isUploading}
          onClick={handleUpload}
        >
          {processingStatus === "completed"
            ? "Upload Another Contract"
            : isUploading
            ? "Uploading..."
            : "Upload Contract"}
        </Button>
      </div>

      {/* Processing Timeline (Matching Stitch) */}
      {(processingStatus !== "idle" || uploadedContractId) && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Asynchronous Processing Pipeline
            </p>
            {processingStatus === "completed" && uploadedContractId && (
              <Link href={`/contracts/${uploadedContractId}`}>
                <Button variant="primary" size="sm" className="gap-1.5 h-8">
                  <span>View Contract</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </Link>
            )}
          </div>

          <div className="bg-surface-container-low rounded-xl border border-outline-variant p-6 shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
            <ul className="flex flex-col gap-4 relative">
              {/* Step 1 */}
              <li className="flex items-center gap-3 relative z-10">
                <div
                  className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                    getStepState(1) === "done"
                      ? "bg-emerald-950/80 border border-emerald-500 text-emerald-400"
                      : getStepState(1) === "active"
                      ? "bg-primary-container/20 border border-primary text-primary"
                      : "border border-outline-variant text-on-surface-variant"
                  )}
                >
                  {getStepState(1) === "done" ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : getStepState(1) === "active" ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Clock className="w-3 h-3" />
                  )}
                </div>
                <span
                  className={cn(
                    "text-sm font-medium",
                    getStepState(1) === "done"
                      ? "text-on-surface"
                      : getStepState(1) === "active"
                      ? "text-primary font-semibold"
                      : "text-on-surface-variant"
                  )}
                >
                  Document uploaded & validated (M2)
                </span>
              </li>

              {/* Step 2 */}
              <li className="flex items-center gap-3 relative z-10">
                <div
                  className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                    getStepState(2) === "done"
                      ? "bg-emerald-950/80 border border-emerald-500 text-emerald-400"
                      : getStepState(2) === "active"
                      ? "bg-primary-container/20 border border-primary text-primary"
                      : "border border-outline-variant text-on-surface-variant"
                  )}
                >
                  {getStepState(2) === "done" ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : getStepState(2) === "active" ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Clock className="w-3 h-3" />
                  )}
                </div>
                <span
                  className={cn(
                    "text-sm font-medium",
                    getStepState(2) === "done"
                      ? "text-on-surface"
                      : getStepState(2) === "active"
                      ? "text-primary font-semibold"
                      : "text-on-surface-variant"
                  )}
                >
                  Text extracted & segmented into chunks (M3)
                </span>
              </li>

              {/* Step 3 */}
              <li className="flex items-center gap-3 relative z-10">
                <div
                  className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                    getStepState(3) === "done"
                      ? "bg-emerald-950/80 border border-emerald-500 text-emerald-400"
                      : getStepState(3) === "active"
                      ? "bg-primary-container/20 border border-primary text-primary"
                      : "border border-outline-variant text-on-surface-variant"
                  )}
                >
                  {getStepState(3) === "done" ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : getStepState(3) === "active" ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Clock className="w-3 h-3" />
                  )}
                </div>
                <span
                  className={cn(
                    "text-sm font-medium",
                    getStepState(3) === "done"
                      ? "text-on-surface"
                      : getStepState(3) === "active"
                      ? "text-primary font-semibold"
                      : "text-on-surface-variant"
                  )}
                >
                  pgvector embeddings indexing & risk analysis ready (M4/M5)
                </span>
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
