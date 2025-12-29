import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2 } from "lucide-react";
import { useCreateOrder } from "@/hooks/useOrders";
import { useProducts } from "@/hooks/useProducts";

interface CreateOrderModalProps {
    trigger?: React.ReactNode;
}

export function CreateOrderModal({ trigger }: CreateOrderModalProps) {
    const [open, setOpen] = useState(false);
    const [formData, setFormData] = useState({
        product: "",
        quantity: "1",
        value: "",
        origin: "Manual",
    });

    const { data: products } = useProducts();
    const createOrder = useCreateOrder();

    // Atualizar valor quando produto for selecionado
    useEffect(() => {
        if (formData.product && products) {
            const selectedProduct = products.find(p => p.sku === formData.product || p.nome === formData.product);
            if (selectedProduct && selectedProduct.preco_medio) {
                const quantity = parseInt(formData.quantity) || 1;
                const totalValue = selectedProduct.preco_medio * quantity;
                setFormData(prev => ({ ...prev, value: totalValue.toFixed(2) }));
            }
        }
    }, [formData.product, formData.quantity, products]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData((prev) => ({ ...prev, [name]: value }));
    };

    const handleProductChange = (value: string) => {
        setFormData((prev) => ({ ...prev, product: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        await createOrder.mutateAsync({
            product: formData.product,
            quantity: parseInt(formData.quantity) || 1,
            value: parseFloat(formData.value) || 0,
            origin: formData.origin as "Manual" | "Automática",
        });

        // Reset form and close modal
        setFormData({
            product: "",
            quantity: "1",
            value: "",
            origin: "Manual",
        });
        setOpen(false);
    };

    const isFormValid =
        formData.product.trim() !== "" &&
        parseInt(formData.quantity) > 0 &&
        parseFloat(formData.value) > 0;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {trigger || (
                    <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Criar Nova Ordem
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Criar Nova Ordem de Compra</DialogTitle>
                    <DialogDescription>
                        Preencha as informações para criar uma ordem de compra manual.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        {/* Produto */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="product" className="text-right">
                                Produto *
                            </Label>
                            <div className="col-span-3">
                                <Select value={formData.product} onValueChange={handleProductChange}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Selecione um produto" />
                                    </SelectTrigger>
                                    <SelectContent className="max-h-60">
                                        {products?.map((product) => (
                                            <SelectItem key={product.id} value={product.nome}>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{product.sku}</span>
                                                    <span className="text-muted-foreground">-</span>
                                                    <span>{product.nome}</span>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Quantidade */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="quantity" className="text-right">
                                Quantidade *
                            </Label>
                            <Input
                                id="quantity"
                                name="quantity"
                                type="number"
                                min="1"
                                placeholder="1"
                                value={formData.quantity}
                                onChange={handleInputChange}
                                className="col-span-3"
                                required
                            />
                        </div>

                        {/* Valor Total */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="value" className="text-right">
                                Valor Total (R$) *
                            </Label>
                            <Input
                                id="value"
                                name="value"
                                type="number"
                                step="0.01"
                                min="0.01"
                                placeholder="0.00"
                                value={formData.value}
                                onChange={handleInputChange}
                                className="col-span-3"
                                required
                            />
                        </div>

                        {/* Origem */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="origin" className="text-right">
                                Origem
                            </Label>
                            <div className="col-span-3">
                                <Select
                                    value={formData.origin}
                                    onValueChange={(value) =>
                                        setFormData((prev) => ({ ...prev, origin: value }))
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="Manual">Manual</SelectItem>
                                        <SelectItem value="Automática">Automática</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setOpen(false)}
                        >
                            Cancelar
                        </Button>
                        <Button
                            type="submit"
                            disabled={!isFormValid || createOrder.isPending}
                        >
                            {createOrder.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Criando...
                                </>
                            ) : (
                                "Criar Ordem"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
