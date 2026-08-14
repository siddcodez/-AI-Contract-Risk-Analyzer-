"use client";

import React from "react";
import { useAuth } from "@/lib/auth/store";
import { Bell, ChevronDown, Building2 } from "lucide-react";

export function TopNav() {
  const { user } = useAuth();

  return (
    <header className="h-16 w-full border-b border-outline-variant bg-surface flex justify-between items-center px-4 md:px-8 z-20 sticky top-0">
      {/* Mobile brand title */}
      <div className="md:hidden flex items-center gap-2">
        <div className="w-6 h-6 rounded bg-primary-container flex items-center justify-center text-white">
          <Building2 className="w-3.5 h-3.5" />
        </div>
        <span className="text-base font-bold text-primary tracking-tight">
          ContractIQ
        </span>
      </div>

      {/* Desktop Organization Badge/Selector */}
      <div className="hidden md:flex items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-semibold text-on-surface">
          <Building2 className="w-3.5 h-3.5 text-primary" />
          <span>{user?.org_name || "Enterprise Workspace"}</span>
          <ChevronDown className="w-3.5 h-3.5 text-on-surface-variant" />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-surface-container-high text-on-surface-variant transition-colors relative"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-primary" />
        </button>

        <div className="w-8 h-8 rounded-full bg-surface-container-highest border border-outline-variant flex items-center justify-center text-xs font-bold text-primary uppercase overflow-hidden">
          {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
        </div>
      </div>
    </header>
  );
}
