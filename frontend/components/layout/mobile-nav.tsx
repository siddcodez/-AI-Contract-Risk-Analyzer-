"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Search,
  BarChart3,
  Settings,
} from "lucide-react";

export function MobileNav() {
  const pathname = usePathname();

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
      active: pathname.startsWith("/contracts") && !pathname.includes("/search") && !pathname.includes("/analysis"),
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
    <nav className="md:hidden fixed bottom-0 left-0 w-full h-16 bg-surface-container-low border-t border-outline-variant shadow-[0_-4px_10px_rgba(0,0,0,0.3)] flex justify-around items-center z-40 px-2">
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <Link
            key={item.name}
            href={item.href}
            className={cn(
              "flex flex-col items-center justify-center w-full h-full text-xs transition-colors",
              item.active
                ? "text-primary font-semibold"
                : "text-on-surface-variant hover:text-on-surface"
            )}
          >
            <Icon className="w-5 h-5 mb-1" />
            <span className="text-[10px]">{item.name}</span>
          </Link>
        );
      })}
    </nav>
  );
}
