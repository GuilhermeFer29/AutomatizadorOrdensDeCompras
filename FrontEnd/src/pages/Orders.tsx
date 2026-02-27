import { useState } from "react";
import { useOrders } from "@/hooks/useOrders";
import { OrderStatus } from "@/types/api.types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Check, X } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { ErrorMessage } from "@/components/ui/error-message";
import api from "@/services/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CreateOrderModal } from "@/components/orders/CreateOrderModal";
import { OrderDetailsModal } from "@/components/orders/OrderDetailsModal";
import { Order } from "@/types/api.types";

const statusConfig = {
  approved: {
    label: "Aprovada",
    className: "bg-success/10 text-success hover:bg-success/20"
  },
  pending: {
    label: "Pendente",
    className: "bg-warning/10 text-warning hover:bg-warning/20"
  },
  cancelled: {
    label: "Cancelada",
    className: "bg-destructive/10 text-destructive hover:bg-destructive/20"
  },
  rejected: {
    label: "Rejeitada",
    className: "bg-destructive/10 text-destructive hover:bg-destructive/20"
  }
};

export default function Orders() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | undefined>();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: orders, isLoading, error, refetch } = useOrders({
    status: statusFilter,
    search: searchTerm,
  });

  // Mutation para aprovar ordem
  const approveMutation = useMutation({
    mutationFn: (orderId: number) => api.post(`/api/orders/${orderId}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (error: any) => {
      console.error('Erro ao aprovar ordem:', error);
    }
  });

  // Mutation para rejeitar ordem
  const rejectMutation = useMutation({
    mutationFn: (orderId: number) => api.post(`/api/orders/${orderId}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (error: any) => {
      console.error('Erro ao rejeitar ordem:', error);
    }
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message="Falha ao carregar ordens." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-foreground">Gestão de Ordens de Compra</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Visualize e gerencie todas as ordens de compra do sistema
          </p>
        </div>
        <CreateOrderModal />
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por ID ou produto..."
                className="pl-9"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <Select onValueChange={(value) => setStatusFilter(value === "all" ? undefined : value as OrderStatus)}>
              <SelectTrigger>
                <SelectValue placeholder="Filtrar por status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os status</SelectItem>
                <SelectItem value="approved">Aprovadas</SelectItem>
                <SelectItem value="pending">Pendentes</SelectItem>
                <SelectItem value="cancelled">Canceladas</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Produto(s)</TableHead>
                <TableHead className="text-right">Quantidade</TableHead>
                <TableHead className="text-right">Valor</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Origem</TableHead>
                <TableHead>Data</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders?.map((order) => (
                <TableRow
                  key={order.id}
                  className="cursor-pointer hover:bg-secondary/50"
                  onClick={() => {
                    setSelectedOrder(order);
                    setIsDetailsOpen(true);
                  }}
                >
                  <TableCell className="font-medium">{order.id}</TableCell>
                  <TableCell>{order.product}</TableCell>
                  <TableCell className="text-right">{order.quantity}</TableCell>
                  <TableCell className="text-right">
                    {new Intl.NumberFormat('pt-BR', {
                      style: 'currency',
                      currency: 'BRL'
                    }).format(order.value)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={statusConfig[order.status as keyof typeof statusConfig]?.className || ""}
                      variant="secondary"
                    >
                      {statusConfig[order.status as keyof typeof statusConfig]?.label || order.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{order.origin}</TableCell>
                  <TableCell>
                    {new Date(order.date).toLocaleDateString('pt-BR')}
                  </TableCell>
                  <TableCell className="text-right">
                    {order.status === 'pending' && (
                      <div className="flex gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="default"
                          onClick={(e) => { e.stopPropagation(); approveMutation.mutate(Number(order.id)); }}
                          disabled={approveMutation.isPending}
                          className="gap-1"
                        >
                          <Check className="h-4 w-4" />
                          Aprovar
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={(e) => { e.stopPropagation(); rejectMutation.mutate(Number(order.id)); }}
                          disabled={rejectMutation.isPending}
                          className="gap-1"
                        >
                          <X className="h-4 w-4" />
                          Rejeitar
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <OrderDetailsModal
        order={selectedOrder}
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        statusConfig={statusConfig}
      />
    </div>
  );
}
