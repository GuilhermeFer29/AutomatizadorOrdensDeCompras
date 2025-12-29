import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Area,
    AreaChart
} from "recharts";
import {
    Package,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    DollarSign,
    BarChart3
} from "lucide-react";
import { Product } from "@/types/api.types";
import api from "@/services/api";

interface ProductDetailsModalProps {
    product: Product | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

interface PriceHistoryPoint {
    date: string;
    price: number;
}

interface PredictionData {
    dates: string[];
    prices: number[];
    method: string;
    metrics?: {
        rmse: number;
        mae: number;
        mape: number;
    };
}

export function ProductDetailsModal({ product, open, onOpenChange }: ProductDetailsModalProps) {
    const [priceHistory, setPriceHistory] = useState<PriceHistoryPoint[]>([]);
    const [predictions, setPredictions] = useState<PredictionData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!product || !open) return;

        const fetchData = async () => {
            setLoading(true);
            setError(null);

            try {
                // Buscar histórico de preços
                const historyResponse = await api.get(`/api/products/${product.sku}/price-history`, {
                    params: { limit: 30 }
                });

                const historyData = historyResponse.data.map((item: any) => ({
                    date: new Date(item.date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
                    price: parseFloat(item.price)
                }));
                setPriceHistory(historyData);

                // Buscar previsões
                try {
                    const predResponse = await api.get(`/ml/predict/${product.sku}`, {
                        params: { days_ahead: 14 }
                    });
                    setPredictions(predResponse.data);
                } catch (predError) {
                    console.warn('Previsões não disponíveis:', predError);
                    setPredictions(null);
                }

            } catch (err: any) {
                console.error('Erro ao buscar dados:', err);
                setError('Erro ao carregar dados do produto');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [product, open]);

    if (!product) return null;

    const stockStatus = product.estoque_atual < product.estoque_minimo
        ? 'critical'
        : product.estoque_atual < product.estoque_minimo * 1.5
            ? 'warning'
            : 'healthy';

    const stockStatusConfig = {
        critical: { label: 'Crítico', color: 'destructive', icon: AlertTriangle },
        warning: { label: 'Atenção', color: 'warning', icon: TrendingDown },
        healthy: { label: 'Saudável', color: 'success', icon: TrendingUp },
    };

    const StatusIcon = stockStatusConfig[stockStatus].icon;

    // Combinar histórico com previsões para o gráfico
    const chartData = [
        ...priceHistory.map(item => ({ ...item, type: 'history' })),
        ...(predictions?.dates?.map((date, index) => ({
            date: new Date(date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
            prediction: predictions.prices[index],
            type: 'prediction'
        })) || [])
    ];

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Package className="h-5 w-5" />
                        {product.nome}
                    </DialogTitle>
                </DialogHeader>

                {/* Info Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                    <Card>
                        <CardContent className="p-3">
                            <p className="text-xs text-muted-foreground">SKU</p>
                            <p className="font-semibold">{product.sku}</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-3">
                            <p className="text-xs text-muted-foreground">Categoria</p>
                            <p className="font-semibold">{product.categoria || '-'}</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-3">
                            <p className="text-xs text-muted-foreground">Preço Médio</p>
                            <p className="font-semibold text-green-600">
                                {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(product.preco_medio || 0)}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-3">
                            <p className="text-xs text-muted-foreground">Estoque</p>
                            <div className="flex items-center gap-2">
                                <p className="font-semibold">{product.estoque_atual}</p>
                                <Badge variant={stockStatusConfig[stockStatus].color as any} className="text-xs">
                                    <StatusIcon className="h-3 w-3 mr-1" />
                                    {stockStatusConfig[stockStatus].label}
                                </Badge>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Tabs */}
                <Tabs defaultValue="history" className="mt-4">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="history">
                            <DollarSign className="h-4 w-4 mr-2" />
                            Histórico de Preços
                        </TabsTrigger>
                        <TabsTrigger value="predictions">
                            <BarChart3 className="h-4 w-4 mr-2" />
                            Previsões ML
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="history" className="mt-4">
                        {loading ? (
                            <Skeleton className="h-[250px] w-full" />
                        ) : error ? (
                            <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                                {error}
                            </div>
                        ) : priceHistory.length === 0 ? (
                            <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                                Sem dados históricos disponíveis
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height={250}>
                                <AreaChart data={priceHistory}>
                                    <defs>
                                        <linearGradient id="colorPriceDetails" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                    <XAxis dataKey="date" style={{ fontSize: '11px' }} />
                                    <YAxis style={{ fontSize: '11px' }} />
                                    <Tooltip
                                        formatter={(value: number) => [`R$ ${value.toFixed(2)}`, 'Preço']}
                                        labelStyle={{ fontWeight: 'bold' }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="price"
                                        stroke="hsl(var(--primary))"
                                        strokeWidth={2}
                                        fill="url(#colorPriceDetails)"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        )}
                    </TabsContent>

                    <TabsContent value="predictions" className="mt-4">
                        {loading ? (
                            <Skeleton className="h-[250px] w-full" />
                        ) : !predictions ? (
                            <div className="h-[250px] flex flex-col items-center justify-center text-muted-foreground">
                                <AlertTriangle className="h-8 w-8 mb-2" />
                                <p>Previsões não disponíveis</p>
                                <p className="text-xs">O modelo pode não estar treinado ou não há dados suficientes</p>
                            </div>
                        ) : (
                            <>
                                <ResponsiveContainer width="100%" height={200}>
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                        <XAxis dataKey="date" style={{ fontSize: '11px' }} />
                                        <YAxis style={{ fontSize: '11px' }} />
                                        <Tooltip
                                            formatter={(value: number, name: string) => [
                                                `R$ ${value.toFixed(2)}`,
                                                name === 'price' ? 'Histórico' : 'Previsão'
                                            ]}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="price"
                                            stroke="hsl(var(--primary))"
                                            strokeWidth={2}
                                            dot={{ r: 3 }}
                                            name="Histórico"
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="prediction"
                                            stroke="hsl(var(--chart-2))"
                                            strokeWidth={2}
                                            strokeDasharray="5 5"
                                            dot={{ r: 3 }}
                                            name="Previsão"
                                        />
                                    </LineChart>
                                </ResponsiveContainer>

                                {/* Métricas do Modelo */}
                                {predictions.metrics && (
                                    <div className="grid grid-cols-3 gap-2 mt-4">
                                        <Card className="border-l-4 border-l-blue-500">
                                            <CardContent className="p-3">
                                                <p className="text-xs text-muted-foreground">RMSE</p>
                                                <p className="text-lg font-bold">{predictions.metrics.rmse?.toFixed(2)}</p>
                                            </CardContent>
                                        </Card>
                                        <Card className="border-l-4 border-l-green-500">
                                            <CardContent className="p-3">
                                                <p className="text-xs text-muted-foreground">MAE</p>
                                                <p className="text-lg font-bold">{predictions.metrics.mae?.toFixed(2)}</p>
                                            </CardContent>
                                        </Card>
                                        <Card className="border-l-4 border-l-purple-500">
                                            <CardContent className="p-3">
                                                <p className="text-xs text-muted-foreground">MAPE</p>
                                                <p className="text-lg font-bold">{predictions.metrics.mape?.toFixed(2)}%</p>
                                            </CardContent>
                                        </Card>
                                    </div>
                                )}

                                <p className="text-xs text-muted-foreground text-center mt-2">
                                    Método: {predictions.method}
                                </p>
                            </>
                        )}
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    );
}
