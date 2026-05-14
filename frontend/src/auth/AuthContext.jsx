import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import api, { clearAuthState, logoutSession } from "../api/client";
import { defaultDashboardPath, hasPermission } from "./permissions";
import { applyAdminTheme, defaultThemeSettings } from "../theme";
import { applyBrowserBranding, resetBrowserBranding } from "../utils/branding";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [workshopProfile, setWorkshopProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadWorkshopProfile() {
    try {
      const { data } = await api.get("/workshop/company-profile/");
      setWorkshopProfile(data);
      applyAdminTheme(data);
      applyBrowserBranding(data);
      return data;
    } catch {
      setWorkshopProfile(null);
      applyAdminTheme(defaultThemeSettings);
      resetBrowserBranding();
      return null;
    }
  }

  async function loadPublicBranding() {
    try {
      const { data } = await api.get("/workshop/public/landing/");
      applyBrowserBranding(data);
      return data;
    } catch {
      resetBrowserBranding();
      return null;
    }
  }

  async function loadUser() {
    setLoading(true);
    try {
      const [me] = await Promise.all([api.get("/me/"), loadWorkshopProfile()]);
      setUser(me.data);
      return me.data;
    } catch {
      clearAuthState("Não foi possível validar sua sessão. Entre novamente.", { notify: false });
      setUser(null);
      setWorkshopProfile(null);
      applyAdminTheme(defaultThemeSettings);
      await loadPublicBranding();
      return null;
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUser();

    function handleSessionEnded() {
      setUser(null);
      setWorkshopProfile(null);
      applyAdminTheme(defaultThemeSettings);
      resetBrowserBranding();
      setLoading(false);
    }

    window.addEventListener("auth:session-ended", handleSessionEnded);
    return () => window.removeEventListener("auth:session-ended", handleSessionEnded);
  }, []);

  async function login(username, password) {
    clearAuthState("Preparando novo login.", { notify: false });
    setUser(null);
    setWorkshopProfile(null);
    applyAdminTheme(defaultThemeSettings);
    await loadPublicBranding();

    await api.post("/token/", { username, password });

    try {
      const [me] = await Promise.all([api.get("/me/"), loadWorkshopProfile()]);
      setUser(me.data);
      return me.data;
    } catch {
      clearAuthState("Não foi possível carregar o usuário autenticado.", { notify: false });
      setUser(null);
      setWorkshopProfile(null);
      applyAdminTheme(defaultThemeSettings);
      resetBrowserBranding();
      throw new Error("Login realizado, mas não foi possível carregar os dados do usuário. Verifique se o backend está rodando e tente novamente.");
    }
  }

  async function logout() {
    await logoutSession();
    setUser(null);
    setWorkshopProfile(null);
    applyAdminTheme(defaultThemeSettings);
    await loadPublicBranding();
  }

  const value = useMemo(
    () => ({
      user,
      workshopProfile,
      loading,
      login,
      logout,
      refreshWorkshopProfile: loadWorkshopProfile,
      hasPermission: (permission) => hasPermission(user, permission),
      defaultDashboardPath: () => defaultDashboardPath(user),
    }),
    [user, workshopProfile, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
