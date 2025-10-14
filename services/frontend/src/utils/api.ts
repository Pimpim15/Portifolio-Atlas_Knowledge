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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('atlas:access_token');
      localStorage.removeItem('atlas:refresh_token');
    }
    return Promise.reject(error);
  },
);

export default api;
