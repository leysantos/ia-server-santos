"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/services/api";
import type { AuthUser, ModulePermissionsMap } from "@/types/api";
import { canNavigateModule } from "@/lib/system-modules";

interface AuthContextValue {
  user: AuthUser | null;
  authEnabled: boolean;
  loading: boolean;
  isAdmin: boolean;
  modulePermissions: ModulePermissionsMap | undefined;
  canAccessModule: (moduleId: string) => { allowed: boolean; visible: boolean; blocked: boolean };
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const PUBLIC_PATHS = ["/login"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const status = await api.authStatus();
      setAuthEnabled(status.auth_enabled);
      if (!status.auth_enabled) {
        setUser(null);
        return;
      }
      const token = localStorage.getItem("ia_auth_token");
      if (!token) {
        setUser(null);
        return;
      }
      const me = await api.authMe();
      setUser(me.user);
    } catch {
      setUser(null);
      localStorage.removeItem("ia_auth_token");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await refresh();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    if (loading) return;
    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
    if (authEnabled && !user && !isPublic) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    }
    if (authEnabled && user && pathname === "/login") {
      const params = new URLSearchParams(window.location.search);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : "/chat");
    }
  }, [loading, authEnabled, user, pathname, router]);

  const login = useCallback(
    async (username: string, password: string) => {
      const result = await api.authLogin(username, password);
      localStorage.setItem("ia_auth_token", result.access_token);
      setUser(result.user);
      setAuthEnabled(true);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem("ia_auth_token");
    setUser(null);
    router.replace("/login");
  }, [router]);

  const isAdmin = user?.role === "admin";
  const modulePermissions = user?.module_permissions;

  const canAccessModule = useCallback(
    (moduleId: string) => canNavigateModule(modulePermissions, moduleId, isAdmin),
    [modulePermissions, isAdmin]
  );

  const value = useMemo(
    () => ({
      user,
      authEnabled,
      loading,
      isAdmin,
      modulePermissions,
      canAccessModule,
      login,
      logout,
      refresh,
    }),
    [user, authEnabled, loading, isAdmin, modulePermissions, canAccessModule, login, logout, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider");
  }
  return ctx;
}
