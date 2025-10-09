import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

// TODO: Conectar ao endpoint /api/products para buscar lista de produtos
const mockProducts = [
  { id: "1", name: "Produto A" },
  { id: "2", name: "Produto B" },
  { id: "3", name: "Produto C" },
];

// TODO: Conectar ao endpoint /api/products/{productId}/price-history
// Este array deve conter o histórico de preços e as previsões
const mockChartData = [
  { date: "01/10", price: 95 },
  { date: "03/10", price: 100 },
  { date: "05/10", price: 98 },
  { date: "07/10", price: 105 },
  { date: "09/10", price: 102 },
  { date: "11/10", price: 108 },
  { date: "13/10", price: 110 },
  { date: "15/10", price: 112, prediction: 112 },
  { date: "17/10", prediction: 115 },
  { date: "19/10", prediction: 118 },
  { date: "21/10", prediction: 116 },
  { date: "23/10", prediction: 120 },
  { date: "25/10", prediction: 122 },
  { date: "27/10", prediction: 125 },
];

export function PriceChart() {
  return (
    <Card className="shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Previsão de Preços</CardTitle>
        <Select defaultValue="1">
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Selecione um produto" />
          </SelectTrigger>
          <SelectContent>
            {mockProducts.map((product) => (
              <SelectItem key={product.id} value={product.id}>
                {product.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={mockChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis 
              dataKey="date" 
              stroke="hsl(var(--muted-foreground))"
              style={{ fontSize: '12px' }}
            />
            <YAxis 
              stroke="hsl(var(--muted-foreground))"
              style={{ fontSize: '12px' }}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px'
              }}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="price" 
              stroke="hsl(var(--primary))" 
              strokeWidth={2}
              name="Histórico de Preços"
              dot={{ fill: 'hsl(var(--primary))' }}
            />
            <Line 
              type="monotone" 
              dataKey="prediction" 
              stroke="hsl(var(--primary))" 
              strokeWidth={2}
              strokeDasharray="5 5"
              name="Previsão"
              dot={{ fill: 'hsl(var(--primary))' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
