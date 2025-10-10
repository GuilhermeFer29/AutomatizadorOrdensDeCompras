Você está trabalhando em um projeto React + TypeScript + Tailwind CSS para um Sistema de Automação Inteligente de Ordens de Compra. A interface já está criada com componentes visuais (Dashboard, Agentes, Ordens, Catálogo), mas todos usam dados mockados.

Objetivo: Integrar completamente com uma API FastAPI local, implementando uma arquitetura robusta de comunicação entre frontend e backend.

Estrutura Atual do Projeto
frontend/
├── src/
│ ├── components/
│ │ ├── dashboard/
│ │ │ ├── KPICard.tsx
│ │ │ ├── PriceChart.tsx
│ │ │ └── AlertsTable.tsx
│ │ ├── layout/
│ │ │ ├── MainLayout.tsx
│ │ │ └── Sidebar.tsx
│ │ └── ui/ (shadcn components)
│ ├── pages/
│ │ ├── Dashboard.tsx
│ │ ├── Agents.tsx
│ │ ├── Orders.tsx
│ │ └── Catalog.tsx
│ ├── App.tsx
│ ├── main.tsx
│ └── index.css
├── package.json
└── vite.config.ts
Dependências já instaladas:

@tanstack/react-query (para gerenciamento de estado assíncrono)
react-router-dom (navegação)
recharts (gráficos)
zod (validação de schemas)
lucide-react (ícones)
🎯 ETAPA 1: Configuração Base da Integração
1.1 - Criar arquivo de variáveis de ambiente
Arquivo: .env.local (na raiz do projeto)

VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=30000
Explicação:

VITE*API_BASE_URL: URL base da API FastAPI (ajuste conforme necessário)
VITE_API_TIMEOUT: Timeout para requisições (30 segundos)
Variáveis com prefixo VITE* são expostas no frontend pelo Vite
1.2 - Criar serviço de API centralizado
Arquivo: src/services/api.ts

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
Instruções:

Instale o axios: npm install axios
Este serviço será usado por todos os hooks customizados
Adicione lógica de autenticação quando necessário
1.3 - Criar tipos TypeScript para as entidades
Arquivo: src/types/api.types.ts

// ============= Dashboard Types =============
export interface DashboardKPIs {
economy: number;
automatedOrders: number;
stockLevel: string;
modelAccuracy: number;
}

export interface PricePoint {
date: string;
price: number;
prediction?: number;
}

export interface Alert {
id: number;
product: string;
alert: string;
stock: number;
severity: 'success' | 'warning' | 'error';
}

// ============= Product Types =============
export interface Product {
id: number;
sku: string;
name: string;
supplier: string;
price: number;
stock: number;
}

export interface ProductWithHistory extends Product {
priceHistory: PricePoint[];
}

// ============= Agent Types =============
export type AgentStatus = 'active' | 'inactive';

export interface Agent {
id: number;
name: string;
status: AgentStatus;
lastRun: string;
description: string;
}

// ============= Order Types =============
export type OrderStatus = 'approved' | 'pending' | 'cancelled';
export type OrderOrigin = 'Automática' | 'Manual';

export interface Order {
id: string;
product: string;
quantity: number;
value: number;
status: OrderStatus;
origin: OrderOrigin;
date: string;
}

// ============= API Response Wrappers =============
export interface ApiResponse<T> {
data: T;
message?: string;
}

export interface PaginatedResponse<T> {
items: T[];
total: number;
page: number;
pageSize: number;
}
1.4 - Configurar React Query
Arquivo: src/lib/queryClient.ts

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
defaultOptions: {
queries: {
staleTime: 5 _ 60 _ 1000, // 5 minutos
gcTime: 10 _ 60 _ 1000, // 10 minutos (anteriormente cacheTime)
retry: 1,
refetchOnWindowFocus: false,
},
},
});
Atualizar: src/App.tsx

import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/queryClient";

const App = () => (
<QueryClientProvider client={queryClient}>
{/_ resto do código _/}
</QueryClientProvider>
);
🎯 ETAPA 2: Implementar Hooks Customizados com React Query
2.1 - Hooks para Dashboard
Arquivo: src/hooks/useDashboard.ts

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
2.2 - Hooks para Produtos
Arquivo: src/hooks/useProducts.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Product } from '@/types/api.types';
import { toast } from '@/hooks/use-toast';

// Hook para listar produtos
export const useProducts = (searchTerm?: string) => {
return useQuery<Product[]>({
queryKey: ['products', searchTerm],
queryFn: async () => {
const params = searchTerm ? { search: searchTerm } : {};
const response = await api.get('/api/products', { params });
return response.data;
},
});
};

// Hook para buscar produto por ID
export const useProduct = (productId: number) => {
return useQuery<Product>({
queryKey: ['products', productId],
queryFn: async () => {
const response = await api.get(`/api/products/${productId}`);
return response.data;
},
});
};

// Hook para criar produto
export const useCreateProduct = () => {
const queryClient = useQueryClient();

return useMutation({
mutationFn: async (newProduct: Omit<Product, 'id'>) => {
const response = await api.post('/api/products', newProduct);
return response.data;
},
onSuccess: () => {
queryClient.invalidateQueries({ queryKey: ['products'] });
toast({
title: 'Sucesso',
description: 'Produto criado com sucesso',
});
},
onError: () => {
toast({
title: 'Erro',
description: 'Falha ao criar produto',
variant: 'destructive',
});
},
});
};

// Hook para atualizar produto
export const useUpdateProduct = () => {
const queryClient = useQueryClient();

return useMutation({
mutationFn: async ({ id, data }: { id: number; data: Partial<Product> }) => {
const response = await api.put(`/api/products/${id}`, data);
return response.data;
},
onSuccess: () => {
queryClient.invalidateQueries({ queryKey: ['products'] });
toast({
title: 'Sucesso',
description: 'Produto atualizado com sucesso',
});
},
onError: () => {
toast({
title: 'Erro',
description: 'Falha ao atualizar produto',
variant: 'destructive',
});
},
});
};
2.3 - Hooks para Agentes
Arquivo: src/hooks/useAgents.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Agent } from '@/types/api.types';
import { toast } from '@/hooks/use-toast';

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
2.4 - Hooks para Ordens
Arquivo: src/hooks/useOrders.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Order, OrderStatus } from '@/types/api.types';
import { toast } from '@/hooks/use-toast';

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
🎯 ETAPA 3: Integrar Hooks nos Componentes
3.1 - Atualizar Dashboard.tsx

import { useDashboardKPIs, useDashboardAlerts } from "@/hooks/useDashboard";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function Dashboard() {
const { data: kpiData, isLoading: kpiLoading, error: kpiError } = useDashboardKPIs();
const { data: alerts, isLoading: alertsLoading } = useDashboardAlerts();

if (kpiLoading) {
return <div className="space-y-6">
<Skeleton className="h-32 w-full" />
<Skeleton className="h-96 w-full" />
</div>;
}

if (kpiError) {
return <Alert variant="destructive">
<AlertDescription>
Erro ao carregar dados do dashboard. Verifique a conexão com a API.
</AlertDescription>
</Alert>;
}

return (
<div className="space-y-8">
{/_ Usar kpiData nos KPICards _/}
<KPICard
title="Economia Estimada"
value={`R$ ${kpiData?.economy.toFixed(2)}`}
// ...
/>
{/_ Resto do código _/}
</div>
);
}
3.2 - Atualizar Catalog.tsx

import { useState } from "react";
import { useProducts } from "@/hooks/useProducts";
import { Skeleton } from "@/components/ui/skeleton";

export default function Catalog() {
const [searchTerm, setSearchTerm] = useState("");
const { data: products, isLoading } = useProducts(searchTerm);

if (isLoading) {
return <Skeleton className="h-96 w-full" />;
}

return (
<div className="space-y-8">
<Input
placeholder="Buscar por nome ou SKU..."
value={searchTerm}
onChange={(e) => setSearchTerm(e.target.value)}
/>
<Table>
<TableBody>
{products?.map((product) => (
<TableRow key={product.id}>
{/_ Renderizar dados reais _/}
</TableRow>
))}
</TableBody>
</Table>
</div>
);
}
3.3 - Atualizar Agents.tsx

import { useAgents, useToggleAgent, useRunAgent } from "@/hooks/useAgents";

export default function Agents() {
const { data: agents, isLoading } = useAgents();
const toggleAgent = useToggleAgent();
const runAgent = useRunAgent();

const handleToggle = (agentId: number, currentStatus: AgentStatus) => {
const action = currentStatus === 'active' ? 'pause' : 'activate';
toggleAgent.mutate({ agentId, action });
};

const handleRunNow = (agentId: number) => {
runAgent.mutate(agentId);
};

// Resto do código com botões conectados às funções acima
}
3.4 - Atualizar Orders.tsx

import { useState } from "react";
import { useOrders } from "@/hooks/useOrders";
import { OrderStatus } from "@/types/api.types";

export default function Orders() {
const [statusFilter, setStatusFilter] = useState<OrderStatus | undefined>();
const [searchTerm, setSearchTerm] = useState("");

const { data: orders, isLoading } = useOrders({
status: statusFilter,
search: searchTerm,
});

// Resto do código
}
🎯 ETAPA 4: Componentes de Loading e Erro
4.1 - Criar componente de Loading
Arquivo: src/components/ui/loading-spinner.tsx

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
className?: string;
size?: number;
}

export function LoadingSpinner({ className, size = 24 }: LoadingSpinnerProps) {
return (
<div className="flex items-center justify-center p-4">
<Loader2 className={cn("animate-spin text-primary", className)} size={size} />
</div>
);
}
4.2 - Criar componente de Erro
Arquivo: src/components/ui/error-message.tsx

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorMessageProps {
title?: string;
message: string;
onRetry?: () => void;
}

export function ErrorMessage({
title = "Erro",
message,
onRetry
}: ErrorMessageProps) {
return (
<Alert variant="destructive" className="my-4">
<AlertCircle className="h-4 w-4" />
<AlertTitle>{title}</AlertTitle>
<AlertDescription className="mt-2">
{message}
{onRetry && (
<Button 
            variant="outline" 
            size="sm" 
            className="mt-2"
            onClick={onRetry}
          >
Tentar Novamente
</Button>
)}
</AlertDescription>
</Alert>
);
}
🎯 ETAPA 5: Tratamento de Erros e Estados
5.1 - Adicionar padrão de Loading em todos os componentes

if (isLoading) {
return <LoadingSpinner />;
}

if (error) {
return <ErrorMessage
message="Falha ao carregar dados"
onRetry={() => refetch()}
/>;
}
5.2 - Adicionar Skeleton Screens
Use o componente Skeleton do shadcn/ui para criar placeholders durante o carregamento:

{isLoading ? (

  <div className="space-y-2">
    <Skeleton className="h-20 w-full" />
    <Skeleton className="h-20 w-full" />
    <Skeleton className="h-20 w-full" />
  </div>
) : (
  // Conteúdo real
)}
🎯 ETAPA 6: Testes de Integração
6.1 - Checklist de Testes
Antes de considerar a integração completa, teste:

✅ Dashboard

[ ] KPIs carregam corretamente
[ ] Gráfico de preços atualiza ao selecionar produto
[ ] Alertas são exibidos
[ ] Loading states funcionam
✅ Catálogo

[ ] Lista de produtos carrega
[ ] Busca funciona
[ ] Criar produto funciona
[ ] Editar produto funciona
✅ Agentes

[ ] Lista de agentes carrega
[ ] Pausar/Ativar funciona
[ ] Executar agora funciona
[ ] Status atualiza automaticamente
✅ Ordens

[ ] Lista de ordens carrega
[ ] Filtros funcionam
[ ] Criar ordem funciona
🎯 ETAPA 7: Otimizações Finais
7.1 - Adicionar React Query Devtools (apenas desenvolvimento)

import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const App = () => (
<QueryClientProvider client={queryClient}>
{/_ ... _/}
{import.meta.env.DEV && <ReactQueryDevtools />}
</QueryClientProvider>
);
7.2 - Adicionar variável de ambiente no .gitignore
Certifique-se de que .env.local está no .gitignore:

.env.local
📝 Checklist Final de Implementação
[ ] ✅ Instalar axios: npm install axios
[ ] ✅ Criar .env.local com URL da API
[ ] ✅ Criar src/services/api.ts
[ ] ✅ Criar src/types/api.types.ts
[ ] ✅ Criar src/lib/queryClient.ts
[ ] ✅ Criar hooks em src/hooks/:
[ ] useDashboard.ts
[ ] useProducts.ts
[ ] useAgents.ts
[ ] useOrders.ts
[ ] ✅ Atualizar todas as páginas para usar hooks
[ ] ✅ Adicionar componentes de Loading e Erro
[ ] ✅ Testar todas as funcionalidades
[ ] ✅ Adicionar React Query Devtools
[ ] ✅ Verificar que .env.local está no .gitignore
