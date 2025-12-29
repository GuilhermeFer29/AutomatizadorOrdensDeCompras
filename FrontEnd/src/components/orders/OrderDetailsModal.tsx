import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Order } from "@/types/api.types";
import {
    Calendar,
    Package,
    ShoppingBag,
    Truck,
    FileText,
    CreditCard,
    User
} from "lucide-react";

interface OrderDetailsModalProps {
    order: Order | null;
    isOpen: boolean;
    onClose: () => void;
    statusConfig: Record<string, { label: string; className: string }>;
}

export function OrderDetailsModal({ order, isOpen, onClose, statusConfig }: OrderDetailsModalProps) {
    if (!order) return null;

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleString('pt-BR');
        } catch (e) {
            return dateStr;
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <DialogTitle className="text-xl">Detalhes da Ordem #{order.id}</DialogTitle>
                        <Badge
                            className={statusConfig[order.status]?.className}
                            variant="secondary"
                        >
                            {statusConfig[order.status]?.label || order.status}
                        </Badge>
                    </div>
                    <DialogDescription>
                        Informações detalhadas sobre a solicitação de compra.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    {/* Produto e Quantidade */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <Package className="h-3 w-3" /> Produto
                            </p>
                            <p className="font-semibold">{order.product}</p>
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <ShoppingBag className="h-3 w-3" /> Quantidade
                            </p>
                            <p className="font-semibold">{order.quantity} unidades</p>
                        </div>
                    </div>

                    {/* Valor e Fornecedor */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <CreditCard className="h-3 w-3" /> Valor Total
                            </p>
                            <p className="font-semibold text-primary">
                                {new Intl.NumberFormat('pt-BR', {
                                    style: 'currency',
                                    currency: 'BRL'
                                }).format(order.value)}
                            </p>
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <Truck className="h-3 w-3" /> Fornecedor
                            </p>
                            <p className="font-semibold">{(order as any).supplier || 'Padrão'}</p>
                        </div>
                    </div>

                    {/* Origem e Data */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <User className="h-3 w-3" /> Origem
                            </p>
                            <p className="font-semibold">{order.origin}</p>
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <Calendar className="h-3 w-3" /> Data de Criação
                            </p>
                            <p className="font-semibold">{formatDate(order.date)}</p>
                        </div>
                    </div>

                    {/* Justificativa */}
                    {(order as any).justification && (
                        <div className="space-y-1 pt-2 border-t">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <FileText className="h-3 w-3" /> Justificativa / Raciocínio
                            </p>
                            <p className="text-sm italic text-muted-foreground">
                                {(order as any).justification}
                            </p>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button onClick={onClose}>Fechar</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
