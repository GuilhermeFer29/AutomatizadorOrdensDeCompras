/**
 * Testes para hooks de Produtos
 * 
 * Verifica se os hooks estão chamando as APIs corretamente.
 */

import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useProducts, useProduct, useCreateProduct, useUpdateProduct } from '@/hooks/useProducts'
import { ReactNode } from 'react'

// Wrapper com QueryClient para testes
const createWrapper = () => {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
                gcTime: 0,
            },
        },
    })
    return ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
}

describe('useProducts Hook', () => {
    it('deve buscar lista de produtos', async () => {
        const { result } = renderHook(() => useProducts(), {
            wrapper: createWrapper(),
        })

        // Aguardar a query completar
        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        // Verificar dados
        expect(result.current.data).toBeDefined()
        expect(result.current.data).toHaveLength(2)
        expect(result.current.data?.[0].sku).toBe('SKU001')
        expect(result.current.data?.[0].nome).toBe('Produto Teste 1')
    })

    it('deve buscar produtos com termo de busca', async () => {
        const { result } = renderHook(() => useProducts('teste'), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data).toBeDefined()
    })
})

describe('useCreateProduct Hook', () => {
    it('deve criar produto com dados corretos', async () => {
        const { result } = renderHook(() => useCreateProduct(), {
            wrapper: createWrapper(),
        })

        // Executar mutação
        result.current.mutate({
            sku: 'SKU003',
            name: 'Novo Produto',
            price: 150.00,
            stock: 25,
        })

        // Aguardar sucesso
        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        // Verificar que não houve erro
        expect(result.current.isError).toBe(false)
    })

    it('deve enviar campos no formato correto (inglês)', async () => {
        const { result } = renderHook(() => useCreateProduct(), {
            wrapper: createWrapper(),
        })

        const productData = {
            sku: 'SKU004',
            name: 'Produto Teste',  // name, não nome
            price: 100.00,          // price, não preco
            stock: 10,              // stock, não estoque_atual
        }

        result.current.mutate(productData)

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})

describe('useUpdateProduct Hook', () => {
    it('deve atualizar produto com dados corretos', async () => {
        const { result } = renderHook(() => useUpdateProduct(), {
            wrapper: createWrapper(),
        })

        result.current.mutate({
            id: 1,
            data: {
                name: 'Produto Atualizado',
                stock: 100,
            },
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.isError).toBe(false)
    })
})
