"use client";

import { createContext, useContext, useEffect, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { nexovaApi } from "@/lib/nexova-api";
import type { SessionSnapshot, UserProfile } from "@/types/auth";

interface AuthContextValue extends SessionSnapshot {
  setAccessToken: (token: string) => void;
  updateProfile: (profile: UserProfile) => void;
  validateSession: () => Promise<SessionSnapshot>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const serverSession: SessionSnapshot = {
  status: "loading",
  user: null,
  error: null,
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const session = useSyncExternalStore(
    (listener) => nexovaApi.subscribe(() => listener()),
    () => nexovaApi.getSession(),
    () => serverSession,
  );

  useEffect(() => {
    void nexovaApi.validateSession();
  }, []);

  const value: AuthContextValue = {
    ...session,
    setAccessToken: (token) => nexovaApi.setAccessToken(token),
    updateProfile: (profile) => nexovaApi.updateProfile(profile),
    validateSession: () => nexovaApi.validateSession(),
    logout: () => nexovaApi.logout(),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}