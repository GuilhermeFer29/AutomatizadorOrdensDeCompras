import { useState, useMemo, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  LineChart, 
  Line, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer
} from "recharts";
import { TrendingUp, AlertTriangle, Search, Activity, Target, TrendingDown } from "lucide-react";
import { useProducts, useProductPredictions } from "@/hooks/useDashboard";
import { Product } from "@/types/api.types";
import api from "@/services/api";

interface ChartDataPoint {
  date: string;
  price?: number;
  prediction?: number;
}

interface PriceChartProps {
  onModelMetricsChange?: (metrics: { mape: number; sku: string; productName: string } | null) => void;
}

export function PriceChart({ onModelMetricsChange }: PriceChartProps = {}) {
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [historicalData, setHistoricalData] = useState<ChartDataPoint[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const { data: products, isLoading: productsLoading } = useProducts();
  const { data: predictions, isLoading: predictionsLoading, error: predictionsError } = useProductPredictions(selectedSku, 14);

  // Buscar histórico de preços quando produto for selecionado
  useEffect(() => {
    if (!selectedSku) return;

    const fetchHistory = async () => {
      setLoadingHistory(true);
      try {
        const response = await api.get(`/api/products/${selectedSku}/price-history`, {
          params: { limit: 30 } // Últimos 30 dias
        });
        
        if (!response.data || response.data.length === 0) {
          console.warn('Nenhum dado histórico encontrado para', selectedSku);
          setHistoricalData([]);
          return;
        }
        
        const historyData = response.data.map((item: any) => {
          const dateObj = new Date(item.date);
          return {
            date: dateObj.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
            price: parseFloat(item.price)
          };
        });
        
        console.log('Histórico carregado:', historyData.length, 'registros');
        setHistoricalData(historyData);
      } catch (error) {
        console.error('Erro ao buscar histórico:', error);
        setHistoricalData([]);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [selectedSku]);

  // Selecionar primeiro produto automaticamente
  useEffect(() => {
    if (products && products.length > 0 && !selectedSku) {
      setSelectedSku(products[0].sku);
    }
  }, [products, selectedSku]);

  // Combinar histórico com previsões
  const chartData = useMemo(() => {
    const combined: ChartDataPoint[] = [];
    
    // Adicionar histórico
    historicalData.forEach(item => {
      combined.push({
        date: item.date,
        price: item.price,
        prediction: undefined
      });
    });

    // Adicionar previsões
    if (predictions && predictions.dates && predictions.prices) {
      predictions.dates.forEach((date: string, index: number) => {
        const dateFormatted = new Date(date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        combined.push({
          date: dateFormatted,
          price: undefined,
          prediction: predictions.prices[index]
        });
      });
    }

    console.log('Dados do gráfico:', {
      historico: historicalData.length,
      previsoes: predictions?.prices?.length || 0,
      total: combined.length
    });

    return combined;
  }, [historicalData, predictions]);

  const selectedProduct = useMemo(() => {
    return products?.find((p: Product) => p.sku === selectedSku);
  }, [products, selectedSku]);

  // Filtrar produtos pela busca
  const filteredProducts = useMemo(() => {
    if (!products) return [];
    if (!searchQuery.trim()) return products;
    
    const query = searchQuery.toLowerCase();
    return products.filter((p: Product) => 
      p.sku.toLowerCase().includes(query) || 
      p.nome.toLowerCase().includes(query)
    );
  }, [products, searchQuery]);

  // Custom Tooltip melhorado
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    
    const data = payload[0].payload;
    const hasPrice = data.price !== undefined;
    const hasPrediction = data.prediction !== undefined;
    
    return (
      <div className="bg-card border border-border rounded-lg shadow-lg p-3">
        <p className="text-sm font-semibold mb-2">{data.date}</p>
        {hasPrice && (
          <div className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">Histórico:</span>
            <span className="font-semibold">R$ {data.price.toFixed(2)}</span>
          </div>
        )}
        {hasPrediction && (
          <div className="flex items-center gap-2 text-sm mt-1">
            <div className="w-3 h-3 rounded-full bg-chart-2" />
            <span className="text-muted-foreground">Previsão ML:</span>
            <span className="font-semibold">R$ {data.prediction.toFixed(2)}</span>
          </div>
        )}
      </div>
    );
  };

  // Notificar Dashboard sobre mudanças nas métricas
  useEffect(() => {
    if (onModelMetricsChange) {
      if (predictions && predictions.metrics && selectedProduct) {
        onModelMetricsChange({
          mape: predictions.metrics.mape || 0,
          sku: selectedSku || '',
          productName: selectedProduct.nome
        });
      } else {
        onModelMetricsChange(null);
      }
    }
  }, [predictions, selectedProduct, selectedSku, onModelMetricsChange]);

  if (productsLoading) {
    return <Skeleton className="h-[450px] w-full" />;
  }

  if (!products || products.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Nenhum produto encontrado no catálogo.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex-1">
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Previsão de Preços
            </CardTitle>
            {selectedProduct && (
              <CardDescription className="mt-2">
                {selectedProduct.nome}
                {predictions && predictions.method && (
                  <Badge variant="outline" className="ml-2">
                    {predictions.method}
                  </Badge>
                )}
              </CardDescription>
            )}
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar produto..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-full sm:w-48"
              />
            </div>
            <Select value={selectedSku || undefined} onValueChange={setSelectedSku}>
              <SelectTrigger className="w-full sm:w-64">
                <SelectValue placeholder="Selecione um produto" />
              </SelectTrigger>
              <SelectContent className="max-h-80">
                {filteredProducts.length === 0 ? (
                  <div className="p-4 text-sm text-muted-foreground text-center">
                    Nenhum produto encontrado
                  </div>
                ) : (
                  filteredProducts.map((product: Product) => (
                    <SelectItem key={product.sku} value={product.sku}>
                      {product.sku} - {product.nome}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {(loadingHistory || predictionsLoading) ? (
          <div className="h-[350px] flex items-center justify-center">
            <Skeleton className="h-full w-full" />
          </div>
        ) : predictionsError ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Modelo de ML não treinado para este produto. Use o endpoint POST /ml/train/{selectedSku} para treinar.
            </AlertDescription>
          </Alert>
        ) : chartData.length === 0 ? (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Sem dados de histórico ou previsões disponíveis.
            </AlertDescription>
          </Alert>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorPrediction" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="date" 
                stroke="hsl(var(--muted-foreground))"
                style={{ fontSize: '11px' }}
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
              />
              <YAxis 
                stroke="hsl(var(--muted-foreground))"
                style={{ fontSize: '11px' }}
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
                label={{ 
                  value: 'Preço (R$)', 
                  angle: -90, 
                  position: 'insideLeft', 
                  style: { fontSize: '12px', fill: 'hsl(var(--muted-foreground))' } 
                }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ paddingTop: '20px' }}
                iconType="line"
              />
              <Area 
                type="monotone" 
                dataKey="price" 
                stroke="hsl(var(--primary))" 
                strokeWidth={3}
                fill="url(#colorPrice)"
                name="Histórico"
                dot={{ fill: 'hsl(var(--primary))', r: 4, strokeWidth: 2, stroke: '#fff' }}
                activeDot={{ r: 6 }}
                connectNulls
                animationDuration={800}
              />
              <Area 
                type="monotone" 
                dataKey="prediction" 
                stroke="hsl(var(--chart-2))" 
                strokeWidth={3}
                strokeDasharray="8 4"
                fill="url(#colorPrediction)"
                name="Previsão ML"
                dot={{ fill: 'hsl(var(--chart-2))', r: 4, strokeWidth: 2, stroke: '#fff' }}
                activeDot={{ r: 6 }}
                connectNulls
                animationDuration={800}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
        
        {predictions && predictions.metrics && (
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Card className="border-l-4 border-l-blue-500 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                    <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">RMSE</p>
                    <p className="text-2xl font-bold">{predictions.metrics.rmse?.toFixed(2) || 'N/A'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-l-4 border-l-green-500 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                    <Target className="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">MAE</p>
                    <p className="text-2xl font-bold">{predictions.metrics.mae?.toFixed(2) || 'N/A'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-l-4 border-l-purple-500 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
                    <TrendingDown className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">MAPE (Precisão)</p>
                    <p className="text-2xl font-bold">{predictions.metrics.mape?.toFixed(2)}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
