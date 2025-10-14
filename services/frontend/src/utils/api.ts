import axios, { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';

const api = axios.create({
  baseURL: '/api',
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('atlas:access_token');
  if (token) {
    const headers = config.headers ?? new AxiosHeaders();
    headers.set('Authorization', `Bearer ${token}`);
    config.headers = headers;
  }
  return config;
});

export default api;
