-- Migration: Adicionar features de mercado para fornecedores e ofertas
-- Data: 2025-10-16
-- Descrição: Suporte a simulação de mercado competitivo para agentes

-- 1. Adicionar colunas de confiabilidade e prazo aos fornecedores
ALTER TABLE fornecedores 
ADD COLUMN IF NOT EXISTS confiabilidade FLOAT DEFAULT 0.9 CHECK (confiabilidade >= 0.0 AND confiabilidade <= 1.0);

ALTER TABLE fornecedores 
ADD COLUMN IF NOT EXISTS prazo_entrega_dias INT DEFAULT 7 CHECK (prazo_entrega_dias >= 1 AND prazo_entrega_dias <= 60);

-- 2. Criar tabela de ofertas de produtos (simula mercado)
CREATE TABLE IF NOT EXISTS ofertas_produtos (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    fornecedor_id INTEGER NOT NULL REFERENCES fornecedores(id) ON DELETE CASCADE,
    preco_ofertado DECIMAL(10, 2) NOT NULL CHECK (preco_ofertado >= 0.01),
    estoque_disponivel INTEGER DEFAULT 100 CHECK (estoque_disponivel >= 0),
    validade_oferta TIMESTAMP WITH TIME ZONE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Índices para performance
    INDEX idx_ofertas_produto (produto_id),
    INDEX idx_ofertas_fornecedor (fornecedor_id),
    INDEX idx_ofertas_preco (preco_ofertado),
    INDEX idx_ofertas_validade (validade_oferta)
);

-- 3. Criar índices compostos para queries comuns
CREATE INDEX IF NOT EXISTS idx_ofertas_produto_preco 
ON ofertas_produtos(produto_id, preco_ofertado);

CREATE INDEX IF NOT EXISTS idx_ofertas_produto_fornecedor 
ON ofertas_produtos(produto_id, fornecedor_id);

-- 4. Comentários de documentação
COMMENT ON TABLE ofertas_produtos IS 'Ofertas de produtos por fornecedores para simulação de mercado competitivo';
COMMENT ON COLUMN ofertas_produtos.preco_ofertado IS 'Preço ofertado pelo fornecedor (pode variar do preço histórico)';
COMMENT ON COLUMN ofertas_produtos.estoque_disponivel IS 'Quantidade disponível no estoque do fornecedor';
COMMENT ON COLUMN ofertas_produtos.validade_oferta IS 'Data de expiração da oferta (NULL = sem expiração)';

COMMENT ON COLUMN fornecedores.confiabilidade IS 'Score de confiabilidade do fornecedor (0.0 a 1.0)';
COMMENT ON COLUMN fornecedores.prazo_entrega_dias IS 'Prazo médio de entrega em dias úteis';
