"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth/store";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Search,
  BarChart3,
  Settings,
  LogOut,
  Building2,
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logoutUser } = useAuth();

  const navItems = [
    {
      name: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
      active: pathname === "/dashboard",
    },
    {
      name: "Contracts",
      href: "/contracts",
      icon: FileText,
      active: pathname.startsWith("/contracts") && !pathname.includes("/search") && !pathname.includes("/analysis") && !pathname.includes("/ask"),
    },
    {
      name: "Search",
      href: "/contracts",
      icon: Search,
      active: pathname.includes("/search"),
    },
    {
      name: "Analysis",
      href: "/contracts",
      icon: BarChart3,
      active: pathname.includes("/analysis"),
    },
    {
      name: "Settings",
      href: "/settings",
      icon: Settings,
      active: pathname === "/settings",
    },
  ];

  return (
    <aside className="hidden md:flex flex-col h-screen w-64 fixed left-0 top-0 border-r border-outline-variant bg-surface-container-low py-4 px-3 z-30">
      {/* Brand Header */}
      <div className="px-3 pb-6 pt-2 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center text-white shadow-sm">
          <Building2 className="w-4 h-4" />
        </div>
        <div>
          <h1 className="text-base font-bold text-primary tracking-tight">
            ContractIQ
          </h1>
          <p className="text-xs text-on-surface-variant">Enterprise Risk</p>
        </div>
      </div>

      {/* Navigation items */}
      <nav className="flex-1 flex flex-col gap-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all group",
                item.active
                  ? "bg-secondary-container text-on-secondary-container font-semibold"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
              )}
            >
              <Icon
                className={cn(
                  "w-5 h-5 transition-colors",
                  item.active
                    ? "text-primary"
                    : "text-on-surface-variant group-hover:text-on-surface"
                )}
              />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer User Info */}
      <div className="mt-auto px-3 pt-4 border-t border-outline-variant/40 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-surface-container-highest flex items-center justify-center border border-outline-variant text-xs font-bold text-primary uppercase shrink-0">
            {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-on-surface truncate">
              {user?.full_name || "User"}
            </p>
            <p className="text-[10px] text-on-surface-variant truncate">
              {user?.org_name || user?.email || ""}
            </p>
          </div>
        </div>
        <button
          onClick={logoutUser}
          title="Sign out"
          className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
