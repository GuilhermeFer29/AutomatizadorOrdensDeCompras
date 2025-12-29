/**
 * Setup de testes - Configuração global para Vitest
 * 
 * Este arquivo é executado antes de cada arquivo de teste.
 * Usa padrões de URL flexíveis que funcionam tanto local como em Docker.
 */

import '@testing-library/jest-dom'
import { afterEach, beforeAll, afterAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

// =====================================================
// MOCK SERVER - Simula as APIs do Backend
// =====================================================

// Handlers padrão para mock das APIs - usando padrões flexíveis
export const handlers = [
    // Auth
    http.post('*/auth/login', () => {
        return HttpResponse.json({
            access_token: 'mock-jwt-token',
            token_type: 'bearer'
        })
    }),

    http.post('*/auth/register', () => {
        return HttpResponse.json({
            id: 1,
            email: 'test@test.com',
            full_name: 'Test User'
        })
    }),

    // Products
    http.get('*/api/products', () => {
        return HttpResponse.json([
            {
                id: 1,
                sku: 'SKU001',
                nome: 'Produto Teste 1',
                categoria: 'Categoria A',
                preco_medio: 100.50,
                estoque_atual: 50,
                estoque_minimo: 10,
                fornecedor_padrao: 'Fornecedor A'
            },
            {
                id: 2,
                sku: 'SKU002',
                nome: 'Produto Teste 2',
                categoria: 'Categoria B',
                preco_medio: 200.00,
                estoque_atual: 5,
                estoque_minimo: 10,
                fornecedor_padrao: 'Fornecedor B'
            }
        ])
    }),

    http.post('*/api/products', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({
            id: 3,
            ...body,
            estoque_atual: body.stock,
            estoque_minimo: 10,
        }, { status: 201 })
    }),

    http.put('*/api/products/:id', async ({ params, request }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({
            id: params.id,
            sku: 'SKU001',
            ...body,
        })
    }),

    // Orders
    http.get('*/api/orders', () => {
        return HttpResponse.json([
            {
                id: '1',
                product: 'Produto Teste 1',
                quantity: 10,
                value: 1005.00,
                status: 'pending',
                origin: 'Manual',
                date: new Date().toISOString()
            },
            {
                id: '2',
                product: 'Produto Teste 2',
                quantity: 5,
                value: 1000.00,
                status: 'approved',
                origin: 'Automática',
                date: new Date().toISOString()
            }
        ])
    }),

    http.post('*/api/orders', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({
            id: '3',
            ...body,
            status: 'pending',
            date: new Date().toISOString()
        }, { status: 201 })
    }),

    http.post('*/api/orders/:id/approve', ({ params }) => {
        return HttpResponse.json({
            id: params.id,
            status: 'approved'
        })
    }),

    http.post('*/api/orders/:id/reject', ({ params }) => {
        return HttpResponse.json({
            id: params.id,
            status: 'cancelled'
        })
    }),

    // Dashboard
    http.get('*/api/dashboard/kpis', () => {
        return HttpResponse.json({
            economy: 5000.00,
            automatedOrders: 15,
            stockLevel: 'Saudável',
            modelAccuracy: 0.85
        })
    }),

    http.get('*/api/dashboard/alerts', () => {
        return HttpResponse.json([
            {
                id: 2,
                product: 'Produto Teste 2',
                sku: 'SKU002',
                alert: 'Estoque crítico! Faltam 5 unidades',
                stock: 5,
                minStock: 10,
                severity: 'error'
            }
        ])
    }),

    // Agents
    http.get('*/api/agents', () => {
        return HttpResponse.json([
            {
                id: 1,
                name: 'Agente de Análise',
                description: 'Analisa demanda e preços',
                status: 'active',
                lastRun: new Date().toISOString()
            }
        ])
    }),

    http.post('*/api/agents/:id/pause', ({ params }) => {
        return HttpResponse.json({ id: params.id, status: 'paused' })
    }),

    http.post('*/api/agents/:id/activate', ({ params }) => {
        return HttpResponse.json({ id: params.id, status: 'active' })
    }),

    http.post('*/api/agents/:id/run', ({ params }) => {
        return HttpResponse.json({ id: params.id, status: 'running' })
    }),

    // RAG
    http.get('*/api/rag/status', () => {
        return HttpResponse.json({
            success: true,
            data: {
                products_indexed: 10,
                last_sync: new Date().toISOString()
            }
        })
    }),

    http.post('*/api/rag/sync', () => {
        return HttpResponse.json({
            success: true,
            message: 'RAG sincronizado com sucesso',
            data: { products_indexed: 10 }
        })
    }),

    // ML
    http.post('*/ml/train/all/async', () => {
        return HttpResponse.json({
            task_id: 'mock-task-123',
            status: 'PENDING',
            message: 'Task de treinamento em lote iniciada'
        }, { status: 202 })
    }),

    http.get('*/ml/predict/:sku', () => {
        return HttpResponse.json({
            sku: 'SKU001',
            dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
            prices: [100.5, 101.2, 102.0],
            model_used: 'LightGBM',
            method: 'autoregressive',
            metrics: { rmse: 2.5, mae: 2.0, mape: 5.0 }
        })
    }),

    // Price History
    http.get('*/api/products/:sku/price-history', () => {
        return HttpResponse.json([
            { date: '2024-01-01T00:00:00Z', price: 100.00 },
            { date: '2024-01-02T00:00:00Z', price: 101.50 },
            { date: '2024-01-03T00:00:00Z', price: 99.00 },
        ])
    }),
]

// Criar servidor MSW
export const server = setupServer(...handlers)

// =====================================================
// CONFIGURAÇÃO GLOBAL DOS TESTES
// =====================================================

// Mock do localStorage
const localStorageMock = {
    getItem: vi.fn((key: string) => {
        if (key === 'token') return 'mock-jwt-token'
        return null
    }),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock do matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
})

// Mock do ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

// =====================================================
// LIFECYCLE HOOKS
// =====================================================

// Iniciar servidor antes de todos os testes
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))

// Limpar mocks após cada teste
afterEach(() => {
    cleanup()
    server.resetHandlers()
    vi.clearAllMocks()
})

// Fechar servidor após todos os testes
afterAll(() => server.close())
