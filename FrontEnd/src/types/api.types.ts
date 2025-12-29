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
  nome: string;
  categoria?: string;
  fornecedor_padrao?: string;
  preco_medio?: number;
  estoque_atual: number;
  estoque_minimo: number;
}

export interface ProductWithHistory extends Product {
  priceHistory: PricePoint[];
}

// ============= ML Prediction Types =============
export interface MLPrediction {
  sku: string;
  product_name: string;
  dates: string[];
  prices: number[];
  method: string;
  confidence?: string;
}

export interface MLModel {
  sku: string;
  exists: boolean;
  model_type?: string;
  version?: string;
  trained_at?: string;
  metrics?: {
    rmse: number;
    mae: number;
    mape: number;
  };
  features_count?: number;
  training_samples?: number;
}

export interface PriceHistoryPoint {
  date: string;
  price: number;
  is_prediction: boolean;
}

// ============= Agent Types =============
export type AgentStatus = 'active' | 'inactive';

export interface Agent {
  id: number;
  name: string;
  description: string;
  status: AgentStatus;
  lastRun: string;
}

export interface ChatAction {
  action_type: string;
  label: string;
  action_data: Record<string, any>;
  variant?: 'default' | 'destructive' | 'outline' | 'secondary';
}

export interface ChatMessageMetadata {
  type?: string;
  confidence?: 'high' | 'medium' | 'low';
  task_id?: string;
  sku?: string;
  intent?: string;
  async?: boolean;
  stock_atual?: number;
  stock_minimo?: number;
  reason?: string;
  entities?: any;
  actions?: ChatAction[];  // Botões interativos
  decision?: string;
  supplier?: string;
  price?: number;
  quantity_recommended?: number;
}

export interface ChatMessage {
  id: number;
  session_id: number;
  sender: 'human' | 'agent' | 'system';
  content: string;
  criado_em: string;
  metadata?: ChatMessageMetadata | null;
}

// ============= Order Types =============
export type OrderStatus = 'approved' | 'pending' | 'cancelled';
export type OrderOrigin = 'Automática' | 'Manual';

export interface Order {
  id: string | number;
  product: string;
  quantity: number;
  value: number;
  status: OrderStatus;
  origin: OrderOrigin;
  date: string;
  supplier?: string;
  justification?: string;
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
