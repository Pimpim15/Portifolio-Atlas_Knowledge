import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '../utils/api';

type LoginPayload = {
  email: string;
  password: string;
};

type AuthenticatedUser = {
  id: string;
  email: string;
  roles: string[];
  organizations: string[];
};

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('atlas:access_token') || '');
  const refreshToken = ref(localStorage.getItem('atlas:refresh_token') || '');
  const user = ref<AuthenticatedUser | null>(null);

  const login = async (payload: LoginPayload) => {
    const { data } = await api.post('/auth/login', payload);
    accessToken.value = data.access;
    refreshToken.value = data.refresh;
    localStorage.setItem('atlas:access_token', data.access);
    localStorage.setItem('atlas:refresh_token', data.refresh);
    await fetchCurrentUser();
  };

  const logout = () => {
    accessToken.value = '';
    refreshToken.value = '';
    user.value = null;
    localStorage.removeItem('atlas:access_token');
    localStorage.removeItem('atlas:refresh_token');
  };

  const fetchCurrentUser = async () => {
    if (!accessToken.value) {
      user.value = null;
      return null;
    }

    try {
      const { data } = await api.get<AuthenticatedUser>('/users/me');
      user.value = data;
      return data;
    } catch (error) {
      logout();
      throw error;
    }
  };

  return {
    accessToken,
    refreshToken,
    login,
    logout,
    user,
    fetchCurrentUser,
  };
});
