import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '../utils/api';

type LoginPayload = {
  email: string;
  password: string;
};

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('atlas:access_token') || '');
  const refreshToken = ref(localStorage.getItem('atlas:refresh_token') || '');

  const login = async (payload: LoginPayload) => {
    const { data } = await api.post('/auth/login', payload);
    accessToken.value = data.access;
    refreshToken.value = data.refresh;
    localStorage.setItem('atlas:access_token', data.access);
    localStorage.setItem('atlas:refresh_token', data.refresh);
  };

  const logout = () => {
    accessToken.value = '';
    refreshToken.value = '';
    localStorage.removeItem('atlas:access_token');
    localStorage.removeItem('atlas:refresh_token');
  };

  return {
    accessToken,
    refreshToken,
    login,
    logout,
  };
});
