import axios, { AxiosInstance, AxiosError } from 'axios';

// Configuração da instância do Axios
const api: AxiosInstance = axios.create({
baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 30000,
headers: {
'Content-Type': 'application/json',
},
});

// Interceptor para adicionar token de autenticação (se necessário no futuro)
api.interceptors.request.use(
(config) => {
// const token = localStorage.getItem('authToken');
// if (token) {
// config.headers.Authorization = `Bearer ${token}`;
// }
return config;
},
(error) => Promise.reject(error)
);

// Interceptor para tratamento global de erros
api.interceptors.response.use(
(response) => response,
(error: AxiosError) => {
// Tratamento de erros comuns
if (error.response?.status === 401) {
// Token expirado ou inválido
console.error('Erro de autenticação');
} else if (error.response?.status === 500) {
console.error('Erro interno do servidor');
}
return Promise.reject(error);
}
);

export default api;
