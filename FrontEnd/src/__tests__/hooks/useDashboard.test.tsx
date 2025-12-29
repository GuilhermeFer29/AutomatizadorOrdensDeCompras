/**
 * Testes para hooks de Dashboard
 * 
 * Verifica se os KPIs e Alertas estão sendo buscados corretamente.
 */

import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useDashboardKPIs, useDashboardAlerts } from '@/hooks/useDashboard'
import { ReactNode } from 'react'

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

describe('useDashboardKPIs Hook', () => {
    it('deve buscar KPIs corretamente', async () => {
        const { result } = renderHook(() => useDashboardKPIs(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data).toBeDefined()
        expect(result.current.data?.economy).toBe(5000.00)
        expect(result.current.data?.automatedOrders).toBe(15)
        expect(result.current.data?.stockLevel).toBe('Saudável')
        expect(result.current.data?.modelAccuracy).toBe(0.85)
    })
})

describe('useDashboardAlerts Hook', () => {
    it('deve buscar alertas corretamente', async () => {
        const { result } = renderHook(() => useDashboardAlerts(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data).toBeDefined()
        expect(result.current.data).toHaveLength(1)
        expect(result.current.data?.[0].severity).toBe('error')
        expect(result.current.data?.[0].sku).toBe('SKU002')
    })
})
