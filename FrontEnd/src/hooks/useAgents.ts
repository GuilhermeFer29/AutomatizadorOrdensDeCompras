import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Agent } from '@/types/api.types';
import { toast } from '@/components/ui/use-toast';

// Hook para listar agentes
export const useAgents = () => {
return useQuery<Agent[]>({
queryKey: ['agents'],
queryFn: async () => {
const response = await api.get('/api/agents');
return response.data;
},
refetchInterval: 30000, // Atualiza a cada 30 segundos
});
};

// Hook para pausar/ativar agente
export const useToggleAgent = () => {
const queryClient = useQueryClient();

return useMutation({
mutationFn: async ({ agentId, action }: { agentId: number; action: 'pause' | 'activate' }) => {
const response = await api.post(`/api/agents/${agentId}/${action}`);
return response.data;
},
onSuccess: () => {
queryClient.invalidateQueries({ queryKey: ['agents'] });
toast({
title: 'Sucesso',
description: 'Status do agente atualizado',
});
},
onError: () => {
toast({
title: 'Erro',
description: 'Falha ao atualizar status do agente',
variant: 'destructive',
});
},
});
};

// Hook para executar agente imediatamente
export const useRunAgent = () => {
const queryClient = useQueryClient();

return useMutation({
mutationFn: async (agentId: number) => {
const response = await api.post(`/api/agents/${agentId}/run`);
return response.data;
},
onSuccess: () => {
queryClient.invalidateQueries({ queryKey: ['agents'] });
toast({
title: 'Sucesso',
description: 'Agente executado com sucesso',
});
},
onError: () => {
toast({
title: 'Erro',
description: 'Falha ao executar agente',
variant: 'destructive',
});
},
});
};
