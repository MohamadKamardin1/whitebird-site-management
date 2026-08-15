/**
 * Coastal Ledger session context: transparent, role-aware access to White Bird bearer authentication.
 * The refresh token is session-scoped; production deployments should prefer an HttpOnly BFF cookie when available.
 */

import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError, AuthUser, LoginResponse } from "@/lib/api";

const REFRESH_KEY = "whitebird.refresh-token";
type AuthStatus = "checking" | "authenticated" | "guest";
interface AuthContextValue { status: AuthStatus; user: AuthUser | null; permissions: Record<string, unknown> | null; signIn: (email: string, password: string) => Promise<void>; signOut: () => Promise<void>; refreshSession: () => Promise<void>; }
const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const readStoredRefreshToken = () => sessionStorage.getItem(REFRESH_KEY);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [permissions, setPermissions] = useState<Record<string, unknown> | null>(null);
  const clearSession = useCallback(() => { sessionStorage.removeItem(REFRESH_KEY); api.setAccessToken(null); setUser(null); setPermissions(null); setStatus("guest"); }, []);
  const loadCurrentUser = useCallback(async () => { const [currentUser, currentPermissions] = await Promise.all([api.get<AuthUser>("/auth/me"), api.get<Record<string, unknown>>("/auth/me/permissions")]); setUser(currentUser); setPermissions(currentPermissions); setStatus("authenticated"); }, []);
  const refreshSession = useCallback(async () => { const refreshToken = readStoredRefreshToken(); if (!refreshToken) { clearSession(); return; } try { const refreshed = await api.request<{ access_token: string }>("/auth/refresh", { method: "POST", body: { refresh_token: refreshToken }, skipAuth: true }); api.setAccessToken(refreshed.access_token); await loadCurrentUser(); } catch { clearSession(); } }, [clearSession, loadCurrentUser]);
  useEffect(() => { void refreshSession(); }, [refreshSession]);
  const signIn = useCallback(async (email: string, password: string) => { const result = await api.request<LoginResponse>("/auth/login", { method: "POST", body: { email, password, token_name: "White Bird Operations" }, skipAuth: true }); api.setAccessToken(result.access_token); sessionStorage.setItem(REFRESH_KEY, result.refresh_token); setUser(result.user); try { setPermissions(await api.get<Record<string, unknown>>("/auth/me/permissions")); } catch (error) { if (error instanceof ApiError && error.status === 401) throw error; setPermissions(null); } setStatus("authenticated"); }, []);
  const signOut = useCallback(async () => { const refreshToken = readStoredRefreshToken(); try { if (refreshToken) await api.request("/auth/logout", { method: "POST", body: { refresh_token: refreshToken }, skipAuth: true }); } finally { clearSession(); } }, [clearSession]);
  const value = useMemo(() => ({ status, user, permissions, signIn, signOut, refreshSession }), [status, user, permissions, signIn, signOut, refreshSession]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error("useAuth must be used within AuthProvider"); return context; }
