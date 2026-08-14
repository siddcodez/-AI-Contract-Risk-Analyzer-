"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth/store";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import {
  User,
  Building2,
  Shield,
  Server,
  LogOut,
  Info,
  Layers,
  Database,
  Lock,
} from "lucide-react";

export default function SettingsPage() {
  const { user, logoutUser } = useAuth();
  const [activeTab, setActiveTab] = useState<
    "profile" | "organization" | "security" | "infrastructure"
  >("profile");

  const nameParts = user?.full_name?.split(" ") || ["User", ""];
  const firstName = nameParts[0] || "";
  const lastName = nameParts.slice(1).join(" ") || "";

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="border-b border-outline-variant/30 pb-4">
        <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
          Settings
        </h1>
        <p className="text-xs text-on-surface-variant mt-0.5">
          Manage your account profile, organization parameters, and system infrastructure.
        </p>
      </div>

      {/* 2-Column Settings Layout (Tabs + Content) */}
      <div className="flex flex-col md:flex-row gap-8">
        {/* Left Side Tabs */}
        <aside className="w-full md:w-52 shrink-0 flex md:flex-col gap-1 border-b md:border-b-0 md:border-r border-outline-variant/40 pb-4 md:pb-0 md:pr-4 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveTab("profile")}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "profile"
                ? "bg-surface-container-high text-primary border-l-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Profile</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("organization")}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "organization"
                ? "bg-surface-container-high text-primary border-l-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Organization</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("security")}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "security"
                ? "bg-surface-container-high text-primary border-l-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            <span>Security & Auth</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("infrastructure")}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "infrastructure"
                ? "bg-surface-container-high text-primary border-l-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Infrastructure</span>
          </button>
        </aside>

        {/* Right Main Content */}
        <section className="flex-1 flex flex-col gap-6 max-w-2xl">
          {activeTab === "profile" && (
            <>
              {/* Profile Card */}
              <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
                <h2 className="text-sm font-bold text-on-surface border-b border-outline-variant pb-2">
                  User Profile
                </h2>

                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-primary-container text-white flex items-center justify-center font-bold text-xl uppercase shadow-md border-2 border-outline-variant">
                    {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-on-surface">
                      {user?.full_name || "Enterprise User"}
                    </h3>
                    <p className="text-xs text-on-surface-variant">{user?.email}</p>
                    <span className="inline-block px-2 py-0.5 mt-1 rounded bg-surface-container-high text-primary text-[10px] font-semibold uppercase tracking-wider border border-outline-variant">
                      Role: {user?.role || "Reviewer"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Account Information Form (Read-Only) */}
              <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
                <div className="border-b border-outline-variant pb-2">
                  <h2 className="text-sm font-bold text-on-surface">
                    Account Information
                  </h2>
                  <p className="text-xs text-on-surface-variant mt-0.5">
                    Account attributes loaded from the authenticated backend session.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block text-on-surface-variant font-semibold mb-1">
                      First Name
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={firstName}
                      className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-on-surface opacity-90 cursor-default"
                    />
                  </div>

                  <div>
                    <label className="block text-on-surface-variant font-semibold mb-1">
                      Last Name
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={lastName}
                      className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-on-surface opacity-90 cursor-default"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-on-surface-variant font-semibold mb-1">
                      Email Address
                    </label>
                    <input
                      type="email"
                      readOnly
                      value={user?.email || ""}
                      className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-on-surface opacity-90 cursor-default"
                    />
                  </div>
                </div>

                <div className="flex items-start gap-2 bg-surface-container-high/60 p-3 rounded-lg border border-outline-variant/40 text-xs text-on-surface-variant mt-2">
                  <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <p>
                    Account settings and credentials are professionally managed via
                    tenant-isolated PostgreSQL records. Contact your organization administrator for modifications.
                  </p>
                </div>
              </div>
            </>
          )}

          {activeTab === "organization" && (
            <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
              <h2 className="text-sm font-bold text-on-surface border-b border-outline-variant pb-2">
                Organization & Tenant Profile
              </h2>

              <div className="flex flex-col gap-3 text-xs">
                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Organization Name
                  </span>
                  <span className="text-sm font-bold text-on-surface">
                    {user?.org_name || "Enterprise Workspace"}
                  </span>
                </div>

                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Tenant ID (org_id)
                  </span>
                  <span className="font-mono text-on-surface">
                    {user?.org_id || "N/A"}
                  </span>
                </div>

                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Tenant Isolation Standard
                  </span>
                  <span className="text-emerald-400 font-semibold">
                    PostgreSQL Row-Level Security (RLS) Enforced
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "security" && (
            <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
              <h2 className="text-sm font-bold text-on-surface border-b border-outline-variant pb-2">
                Security & Authentication
              </h2>

              <div className="flex flex-col gap-3 text-xs">
                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Token Scheme
                  </span>
                  <span className="font-mono text-on-surface">
                    OAuth2 Bearer JWT (HS256)
                  </span>
                </div>

                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Access Expiry
                  </span>
                  <span className="text-on-surface">
                    30 minutes sliding window
                  </span>
                </div>

                <div className="p-3 bg-surface-container-high/60 rounded-lg border border-outline-variant/40">
                  <span className="text-on-surface-variant block font-semibold mb-0.5">
                    Rate Limiting
                  </span>
                  <span className="text-emerald-400 font-semibold">
                    Token Bucket Algorithm via Redis
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "infrastructure" && (
            <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant shadow-[0_10px_30px_rgba(0,0,0,0.4)] flex flex-col gap-4">
              <h2 className="text-sm font-bold text-on-surface border-b border-outline-variant pb-2">
                Backend Infrastructure
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-surface-container-high/40 rounded-lg border border-outline-variant/30">
                  <span className="text-on-surface-variant font-semibold block mb-0.5">
                    API Framework
                  </span>
                  <span className="font-mono text-on-surface font-bold">FastAPI 0.115</span>
                </div>

                <div className="p-3 bg-surface-container-high/40 rounded-lg border border-outline-variant/30">
                  <span className="text-on-surface-variant font-semibold block mb-0.5">
                    Vector Search
                  </span>
                  <span className="font-mono text-on-surface font-bold">pgvector</span>
                </div>

                <div className="p-3 bg-surface-container-high/40 rounded-lg border border-outline-variant/30">
                  <span className="text-on-surface-variant font-semibold block mb-0.5">
                    Task Broker
                  </span>
                  <span className="font-mono text-on-surface font-bold">Celery + Redis</span>
                </div>

                <div className="p-3 bg-surface-container-high/40 rounded-lg border border-outline-variant/30">
                  <span className="text-on-surface-variant font-semibold block mb-0.5">
                    Object Storage
                  </span>
                  <span className="font-mono text-on-surface font-bold">MinIO S3</span>
                </div>
              </div>
            </div>
          )}

          {/* Sign out button at bottom */}
          <div className="flex justify-end pt-2">
            <Button
              variant="secondary"
              className="gap-2 text-xs font-semibold text-error hover:bg-error-container/20 border-error/30"
              onClick={logoutUser}
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out of ContractIQ</span>
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
