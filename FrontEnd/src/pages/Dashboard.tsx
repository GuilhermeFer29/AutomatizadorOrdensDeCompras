import { useState } from "react";
import { TrendingUp, ShoppingBag, Package, Target } from "lucide-react";
import { KPICard } from "@/components/dashboard/KPICard";
import { PriceChart } from "@/components/dashboard/PriceChart";
import { AlertsTable } from "@/components/dashboard/AlertsTable";
import { AgentStatusPanel } from "@/components/agents/AgentStatusPanel";
import { useDashboardKPIs, useDashboardAlerts } from "@/hooks/useDashboard";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function Dashboard() {
  const { data: kpiData, isLoading: kpiLoading, error: kpiError } = useDashboardKPIs();
  const { data: alerts, isLoading: alertsLoading } = useDashboardAlerts();
  const [selectedProductMetrics, setSelectedProductMetrics] = useState<{
    mape: number;
    sku: string;
    productName: string;
  } | null>(null);

  if (kpiLoading || alertsLoading) {
    return <div className="space-y-6">
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-96 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>;
  }

  if (kpiError) {
    return <Alert variant="destructive">
      <AlertDescription>
        Erro ao carregar dados do dashboard. Verifique a conexão com a API.
      </AlertDescription>
    </Alert>;
  }

  // Determinar cor do ícone de estoque baseado no nível
  const stockIconColor = kpiData?.stockLevel === 'Crítico'
    ? 'text-destructive'
    : kpiData?.stockLevel === 'Atenção'
      ? 'text-warning'
      : 'text-success';

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-foreground">Visão Geral</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Painel de controle do sistema de automação inteligente
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Economia Estimada"
          value={`R$ ${(kpiData?.economy || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`}
          icon={TrendingUp}
          iconColor="text-success"
        />
        <KPICard
          title="Ordens Automatizadas"
          value={kpiData?.automatedOrders || 0}
          icon={ShoppingBag}
          iconColor="text-primary"
        />
        <KPICard
          title="Nível de Estoque"
          value={kpiData?.stockLevel || 'N/A'}
          icon={Package}
          iconColor={stockIconColor}
        />
        <KPICard
          title="Acurácia do Modelo"
          value={
            selectedProductMetrics
              ? `${(100 - selectedProductMetrics.mape).toFixed(1)}%`
              : kpiData?.modelAccuracy
                ? `${(kpiData.modelAccuracy * 100).toFixed(0)}%`
                : 'N/A'
          }
          subtitle={
            selectedProductMetrics
              ? `${selectedProductMetrics.productName.substring(0, 30)}...`
              : kpiData?.modelAccuracy ? "Média Global" : "Modelo não treinado"
          }
          icon={Target}
          iconColor="text-primary"
        />
      </div>

      {/* Price Prediction Chart */}
      <PriceChart onModelMetricsChange={setSelectedProductMetrics} />

      {/* Two Column Layout for Alerts and Agent Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Alerts Table */}
        <AlertsTable alerts={alerts || []} />

        {/* Agent Status Panel */}
        <AgentStatusPanel />
      </div>
    </div>
  );
}
