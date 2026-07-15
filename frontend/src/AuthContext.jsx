import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from './api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem('f1_token');
    if (token) {
      api.getMe()
        .then(u => setUser(u))
        .catch(() => { localStorage.removeItem('f1_token'); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.login({ email, password });
    localStorage.setItem('f1_token', res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const register = useCallback(async (formData) => {
    const res = await api.register(formData);
    localStorage.setItem('f1_token', res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('f1_token');
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (data) => {
    const updated = await api.updateMe(data);
    setUser(updated);
    return updated;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
