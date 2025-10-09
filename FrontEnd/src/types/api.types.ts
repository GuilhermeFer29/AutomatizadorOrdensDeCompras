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
