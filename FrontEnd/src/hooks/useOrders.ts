import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Order, OrderStatus } from '@/types/api.types';
import { toast } from '@/components/ui/use-toast';

// Hook para listar ordens com filtros
export const useOrders = (filters?: {
status?: OrderStatus;
search?: string;
date?: string;
}) => {
return useQuery<Order[]>({
queryKey: ['orders', filters],
queryFn: async () => {
const response = await api.get('/api/orders', { params: filters });
return response.data;
},
});
};

// Hook para criar ordem
export const useCreateOrder = () => {
const queryClient = useQueryClient();

return useMutation({
mutationFn: async (newOrder: Omit<Order, 'id' | 'date'>) => {
const response = await api.post('/api/orders', newOrder);
return response.data;
},
onSuccess: () => {
queryClient.invalidateQueries({ queryKey: ['orders'] });
toast({
title: 'Sucesso',
description: 'Ordem criada com sucesso',
});
},
onError: () => {
toast({
title: 'Erro',
description: 'Falha ao criar ordem',
variant: 'destructive',
});
},
});
};
