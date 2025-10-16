import { useState, useMemo, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { TrendingUp, AlertTriangle } from "lucide-react";
import { useProducts, useProductPredictions } from "@/hooks/useDashboard";
import { Product } from "@/types/api.types";
import api from "@/services/api";

interface ChartDataPoint {
  date: string;
  price?: number;
  prediction?: number;
}

export function PriceChart() {
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [historicalData, setHistoricalData] = useState<ChartDataPoint[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const { data: products, isLoading: productsLoading } = useProducts();
  const { data: predictions, isLoading: predictionsLoading, error: predictionsError } = useProductPredictions(selectedSku, 14);

  // Buscar histórico de preços quando produto for selecionado
  useEffect(() => {
    if (!selectedSku) return;

    const fetchHistory = async () => {
      setLoadingHistory(true);
      try {
        const response = await api.get(`/precos/historico/${selectedSku}`, {
          params: { limit: 30 } // Últimos 30 dias
        });
        
        const historyData = response.data.map((item: any) => ({
          date: new Date(item.coletado_em).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
          price: parseFloat(item.preco)
        }));
        
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
    const combined: ChartDataPoint[] = [...historicalData];

    if (predictions && predictions.dates && predictions.prices) {
      // Adicionar previsões
      predictions.dates.forEach((date: string, index: number) => {
        combined.push({
          date: new Date(date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
          prediction: predictions.prices[index]
        });
      });
    }

    return combined;
  }, [historicalData, predictions]);

  const selectedProduct = useMemo(() => {
    return products?.find((p: Product) => p.sku === selectedSku);
  }, [products, selectedSku]);

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
          <Select value={selectedSku || undefined} onValueChange={setSelectedSku}>
            <SelectTrigger className="w-full sm:w-64">
              <SelectValue placeholder="Selecione um produto" />
            </SelectTrigger>
            <SelectContent>
              {products.map((product: Product) => (
                <SelectItem key={product.sku} value={product.sku}>
                  {product.sku} - {product.nome}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis 
                dataKey="date" 
                stroke="hsl(var(--muted-foreground))"
                style={{ fontSize: '12px' }}
              />
              <YAxis 
                stroke="hsl(var(--muted-foreground))"
                style={{ fontSize: '12px' }}
                label={{ value: 'Preço (R$)', angle: -90, position: 'insideLeft', style: { fontSize: '12px' } }}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px'
                }}
                formatter={(value: any) => [`R$ ${value.toFixed(2)}`, '']}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="price" 
                stroke="hsl(var(--primary))" 
                strokeWidth={2}
                name="Histórico"
                dot={{ fill: 'hsl(var(--primary))', r: 3 }}
                connectNulls
              />
              <Line 
                type="monotone" 
                dataKey="prediction" 
                stroke="hsl(var(--chart-2))" 
                strokeWidth={2}
                strokeDasharray="5 5"
                name="Previsão ML"
                dot={{ fill: 'hsl(var(--chart-2))', r: 3 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
        
        {predictions && predictions.metrics && (
          <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
            <div className="text-center">
              <div className="font-semibold text-muted-foreground">RMSE</div>
              <div className="text-lg">{predictions.metrics.rmse?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="text-center">
              <div className="font-semibold text-muted-foreground">MAE</div>
              <div className="text-lg">{predictions.metrics.mae?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="text-center">
              <div className="font-semibold text-muted-foreground">MAPE</div>
              <div className="text-lg">{predictions.metrics.mape?.toFixed(2)}%</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
