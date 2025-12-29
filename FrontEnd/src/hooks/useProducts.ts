import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Product } from '@/types/api.types';
import { toast } from '@/components/ui/use-toast';

// Tipos para criar e atualizar produtos (matching backend schemas)
interface ProductCreate {
    sku: string;
    name: string;  // Backend usa 'name' não 'nome'
    price: number;
    stock: number;
}

interface ProductUpdate {
    name?: string;
    price?: number;
    stock?: number;
}

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
        mutationFn: async (newProduct: ProductCreate) => {
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
        mutationFn: async ({ id, data }: { id: number; data: ProductUpdate }) => {
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
