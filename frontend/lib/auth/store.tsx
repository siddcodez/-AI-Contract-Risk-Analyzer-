"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { User } from "@/types";
import { getMe } from "@/lib/api/auth";
import { getAuthToken, setAuthToken, removeAuthToken } from "@/lib/api/client";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  loginUser: (token: string) => Promise<void>;
  logoutUser: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const logoutUser = useCallback(() => {
    removeAuthToken();
    setToken(null);
    setUser(null);
    setIsLoading(false);
    if (!pathname.startsWith("/login") && !pathname.startsWith("/signup")) {
      router.push("/login");
    }
  }, [pathname, router]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await getMe();
      setUser(userData);
    } catch {
      logoutUser();
    }
  }, [logoutUser]);

  const loginUser = useCallback(
    async (newToken: string) => {
      setAuthToken(newToken);
      setToken(newToken);
      try {
        const userData = await getMe();
        setUser(userData);
        router.push("/dashboard");
      } catch (err) {
        logoutUser();
        throw err;
      }
    },
    [logoutUser, router]
  );

  useEffect(() => {
    const savedToken = getAuthToken();
    if (savedToken) {
      setToken(savedToken);
      getMe()
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          logoutUser();
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [logoutUser]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!token && !!user,
        loginUser,
        logoutUser,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
