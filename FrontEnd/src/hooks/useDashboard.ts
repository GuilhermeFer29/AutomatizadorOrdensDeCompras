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
