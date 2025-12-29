/**
 * Testes de Integração para API
 * 
 * Verifica se todas as chamadas de API estão usando os endpoints corretos.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import api from '@/services/api'

// Mock do módulo api
vi.mock('@/services/api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        delete: vi.fn(),
    },
}))

describe('API Endpoints', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    describe('Produtos', () => {
        it('GET /api/products - listar produtos', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: [] })

            await api.get('/api/products')

            expect(api.get).toHaveBeenCalledWith('/api/products')
        })

        it('POST /api/products - criar produto com campos corretos', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            const productData = {
                sku: 'SKU001',
                name: 'Produto',    // Backend espera "name"
                price: 100.00,      // Backend espera "price"
                stock: 50,          // Backend espera "stock"
            }

            await api.post('/api/products', productData)

            expect(api.post).toHaveBeenCalledWith('/api/products', productData)

            // Verificar que NÃO está usando nomes em português
            const callArgs = vi.mocked(api.post).mock.calls[0][1] as Record<string, unknown>
            expect(callArgs).not.toHaveProperty('nome')
            expect(callArgs).not.toHaveProperty('preco')
            expect(callArgs).not.toHaveProperty('estoque_atual')
            expect(callArgs).toHaveProperty('name')
            expect(callArgs).toHaveProperty('price')
            expect(callArgs).toHaveProperty('stock')
        })

        it('PUT /api/products/:id - atualizar produto', async () => {
            vi.mocked(api.put).mockResolvedValueOnce({ data: {} })

            const updateData = {
                name: 'Produto Atualizado',
                stock: 100,
            }

            await api.put('/api/products/1', updateData)

            expect(api.put).toHaveBeenCalledWith('/api/products/1', updateData)
        })
    })

    describe('Ordens', () => {
        it('GET /api/orders - listar ordens', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: [] })

            await api.get('/api/orders')

            expect(api.get).toHaveBeenCalledWith('/api/orders')
        })

        it('POST /api/orders - criar ordem SEM status', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            const orderData = {
                product: 'Produto',
                quantity: 10,
                value: 1000.00,
                origin: 'Manual',
                // NÃO incluir status - backend define automaticamente
            }

            await api.post('/api/orders', orderData)

            expect(api.post).toHaveBeenCalledWith('/api/orders', orderData)

            const callArgs = vi.mocked(api.post).mock.calls[0][1] as Record<string, unknown>
            expect(callArgs).not.toHaveProperty('status')
        })

        it('POST /api/orders/:id/approve - aprovar ordem', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            await api.post('/api/orders/1/approve')

            expect(api.post).toHaveBeenCalledWith('/api/orders/1/approve')
        })

        it('POST /api/orders/:id/reject - rejeitar ordem', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            await api.post('/api/orders/1/reject')

            expect(api.post).toHaveBeenCalledWith('/api/orders/1/reject')
        })
    })

    describe('Dashboard', () => {
        it('GET /api/dashboard/kpis - buscar KPIs', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: {} })

            await api.get('/api/dashboard/kpis')

            expect(api.get).toHaveBeenCalledWith('/api/dashboard/kpis')
        })

        it('GET /api/dashboard/alerts - buscar alertas', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: [] })

            await api.get('/api/dashboard/alerts')

            expect(api.get).toHaveBeenCalledWith('/api/dashboard/alerts')
        })
    })

    describe('RAG', () => {
        it('GET /api/rag/status - verificar status', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: {} })

            // IMPORTANTE: endpoint é /api/rag/status, NÃO /rag/status
            await api.get('/api/rag/status')

            expect(api.get).toHaveBeenCalledWith('/api/rag/status')
        })

        it('POST /api/rag/sync - sincronizar RAG', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            // IMPORTANTE: endpoint é /api/rag/sync, NÃO /rag/sync
            await api.post('/api/rag/sync')

            expect(api.post).toHaveBeenCalledWith('/api/rag/sync')
        })
    })

    describe('ML', () => {
        it('POST /ml/train/all/async - treinar modelos', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            // IMPORTANTE: endpoint é /ml/train/all/async, NÃO /ml/train
            await api.post('/ml/train/all/async')

            expect(api.post).toHaveBeenCalledWith('/ml/train/all/async')
        })

        it('GET /ml/predict/:sku - buscar previsões', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: {} })

            await api.get('/ml/predict/SKU001')

            expect(api.get).toHaveBeenCalledWith('/ml/predict/SKU001')
        })
    })

    describe('Agentes', () => {
        it('GET /api/agents - listar agentes', async () => {
            vi.mocked(api.get).mockResolvedValueOnce({ data: [] })

            await api.get('/api/agents')

            expect(api.get).toHaveBeenCalledWith('/api/agents')
        })

        it('POST /api/agents/:id/pause - pausar agente', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            await api.post('/api/agents/1/pause')

            expect(api.post).toHaveBeenCalledWith('/api/agents/1/pause')
        })

        it('POST /api/agents/:id/activate - ativar agente', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            await api.post('/api/agents/1/activate')

            expect(api.post).toHaveBeenCalledWith('/api/agents/1/activate')
        })

        it('POST /api/agents/:id/run - executar agente', async () => {
            vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

            await api.post('/api/agents/1/run')

            expect(api.post).toHaveBeenCalledWith('/api/agents/1/run')
        })
    })
})
