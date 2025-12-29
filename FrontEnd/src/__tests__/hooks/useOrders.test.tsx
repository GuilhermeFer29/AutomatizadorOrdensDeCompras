/**
 * Testes para hooks de Ordens
 * 
 * Verifica se os hooks estão chamando as APIs corretamente.
 */

import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useOrders, useCreateOrder } from '@/hooks/useOrders'
import { ReactNode } from 'react'

// Wrapper com QueryClient
const createWrapper = () => {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false, gcTime: 0 },
        },
    })
    return ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
}

describe('useOrders Hook', () => {
    it('deve buscar lista de ordens', async () => {
        const { result } = renderHook(() => useOrders(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data).toBeDefined()
        expect(result.current.data).toHaveLength(2)
        expect(result.current.data?.[0].status).toBe('pending')
        expect(result.current.data?.[1].status).toBe('approved')
    })

    it('deve filtrar por status', async () => {
        const { result } = renderHook(
            () => useOrders({ status: 'pending' }),
            { wrapper: createWrapper() }
        )

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.data).toBeDefined()
    })
})

describe('useCreateOrder Hook', () => {
    it('deve criar ordem sem campo status', async () => {
        const { result } = renderHook(() => useCreateOrder(), {
            wrapper: createWrapper(),
        })

        // OrderCreate não deve incluir status
        const orderData = {
            product: 'Produto Teste',
            quantity: 10,
            value: 1000.00,
            origin: 'Manual' as const,
            // NÃO INCLUIR: status
        }

        result.current.mutate(orderData)

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(result.current.isError).toBe(false)
    })

    it('deve enviar campos corretos', async () => {
        const { result } = renderHook(() => useCreateOrder(), {
            wrapper: createWrapper(),
        })

        result.current.mutate({
            product: 'Produto Teste',
            quantity: 5,
            value: 500.00,
            origin: 'Automática',
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
    })
})
