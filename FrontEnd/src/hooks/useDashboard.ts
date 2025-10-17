import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';
import { DashboardKPIs, Alert, PricePoint } from '@/types/api.types';

// Hook para buscar KPIs do dashboard
export const useDashboardKPIs = () => {
return useQuery<DashboardKPIs>({
queryKey: ['dashboard', 'kpis'],
queryFn: async () => {
const response = await api.get('/api/dashboard/kpis');
return response.data;
},
});
};

// Hook para buscar alertas
export const useDashboardAlerts = () => {
return useQuery<Alert[]>({
queryKey: ['dashboard', 'alerts'],
queryFn: async () => {
const response = await api.get('/api/dashboard/alerts');
return response.data;
},
});
};

// Hook para buscar histórico de preços de um produto
export const useProductPriceHistory = (productId: number | null) => {
return useQuery<PricePoint[]>({
queryKey: ['products', productId, 'price-history'],
queryFn: async () => {
if (!productId) return [];
const response = await api.get(`/api/products/${productId}/price-history`);
return response.data;
},
enabled: !!productId, // Só executa se productId existir
});
};

// Hook para buscar lista de produtos do catálogo
export const useProducts = () => {
return useQuery({
queryKey: ['products'],
queryFn: async () => {
const response = await api.get('/api/products');
return response.data;
},
});
};

// Hook para buscar previsões de preço de um produto por SKU
export const useProductPredictions = (sku: string | null, daysAhead: number = 14) => {
return useQuery({
queryKey: ['ml', 'predictions', sku, daysAhead],
queryFn: async () => {
if (!sku) return null;
const response = await api.get(`/ml/predict/${sku}`, {
params: { days_ahead: daysAhead }
});
return response.data;
},
enabled: !!sku,
retry: false, // Não retenta em caso de erro (evita múltiplas chamadas)
staleTime: 1000 * 60 * 5, // Cache por 5 minutos
});
};

// Hook para buscar modelos ML treinados
export const useMLModels = () => {
return useQuery({
queryKey: ['ml', 'models'],
queryFn: async () => {
const response = await api.get('/ml/models');
return response.data;
},
});
};
