import { useState } from "react";
import client from "../api/client";

export function useAuth() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));

  const login = async (email: string, password: string) => {
    const { data } = await client.post("/auth/login", { email, password });
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
  };

  const register = async (email: string, password: string) => {
    const { data } = await client.post("/auth/register", { email, password });
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
  };

  return { token, login, register, logout, isAuthenticated: !!token };
}
