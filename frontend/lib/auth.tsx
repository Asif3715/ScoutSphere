"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useQueryClient } from "@tanstack/react-query";

import { setFlash } from "@/lib/flash";
import {
  SESSION_EXPIRED,
  apiFetch,
  refreshSession,
  setAccessToken,
  setActiveOrg,
  type TokenResponse,
  type User,
} from "@/lib/http";
import type { RegisterValues } from "@/lib/schemas";

export type Membership = {
  organization_id: string;
  organization_name: string;
  role: string;
  permissions: string[];
};

type AuthState = {
  user: User | null;
  memberships: Membership[];
  activeOrgId: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Creates the account only; the caller signs in afterwards so each step reports its own error. */
  register: (v: RegisterValues) => Promise<void>;
  logout: () => Promise<void>;
  /** Reloads user + memberships (after creating an org or accepting an invitation). */
  refreshProfile: (preferOrgId?: string) => Promise<void>;
  selectOrg: (id: string | null) => void;
  can: (permission: string) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();
  const activeRef = useRef<string | null>(null);

  const selectOrg = useCallback(
    (id: string | null) => {
      // Cached data belongs to the organization it was fetched for: drop it on a switch so
      // nothing from one organization is ever shown under another.
      if (activeRef.current !== id) queryClient.clear();
      activeRef.current = id;
      setActiveOrgId(id);
      setActiveOrg(id);
      try {
        if (id) sessionStorage.setItem("activeOrg", id);
        else sessionStorage.removeItem("activeOrg");
      } catch {}
    },
    [queryClient],
  );

  // The session ended while the app was open (refresh token expired or revoked elsewhere).
  useEffect(() => {
    const onExpired = () => {
      setAccessToken(null);
      setUser(null);
      setMemberships([]);
      selectOrg(null);
      queryClient.clear();
      setFlash({
        kind: "info",
        text: "Your session has ended. Please sign in again.",
      });
    };
    window.addEventListener(SESSION_EXPIRED, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED, onExpired);
  }, [queryClient, selectOrg]);

  const loadProfile = useCallback(
    async (preferOrgId?: string) => {
      const me = await apiFetch<{ user: User; memberships: Membership[] }>(
        "/auth/me",
      );
      setUser(me.user);
      setMemberships(me.memberships);
      let saved: string | null = null;
      try {
        saved = sessionStorage.getItem("activeOrg");
      } catch {}
      const pick = (id: string | null | undefined) =>
        me.memberships.find((m) => m.organization_id === id) ? id! : null;
      const valid =
        pick(preferOrgId) ??
        pick(saved) ??
        me.memberships[0]?.organization_id ??
        null;
      selectOrg(valid);
    },
    [selectOrg],
  );

  // On first load, try to restore the session from the refresh cookie.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await refreshSession();
      if (data && !cancelled) await loadProfile().catch(() => setUser(null));
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadProfile]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        json: { email, password },
        auth: false,
      });
      setAccessToken(data.access_token);
      queryClient.clear(); // nothing cached for a previous user survives a new sign-in
      await loadProfile();
    },
    [loadProfile, queryClient],
  );

  const register = useCallback(async (v: RegisterValues) => {
    await apiFetch("/auth/register", {
      method: "POST",
      auth: false,
      json: {
        email: v.email,
        password: v.password,
        full_name: v.full_name,
        account_type: v.account_type,
      },
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST", auth: false });
    } finally {
      setAccessToken(null);
      selectOrg(null);
      setUser(null);
      setMemberships([]);
      queryClient.clear();
    }
  }, [selectOrg, queryClient]);

  const can = useCallback(
    (permission: string) =>
      memberships
        .find((m) => m.organization_id === activeOrgId)
        ?.permissions.includes(permission) ?? false,
    [memberships, activeOrgId],
  );

  const value = useMemo(
    () => ({
      user,
      memberships,
      activeOrgId,
      loading,
      login,
      register,
      logout,
      refreshProfile: loadProfile,
      selectOrg,
      can,
    }),
    [
      user,
      memberships,
      activeOrgId,
      loading,
      login,
      register,
      logout,
      loadProfile,
      selectOrg,
      can,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
