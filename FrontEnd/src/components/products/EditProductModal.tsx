import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { useUpdateProduct } from "@/hooks/useProducts";
import { Product } from "@/types/api.types";

interface EditProductModalProps {
    product: Product | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function EditProductModal({ product, open, onOpenChange }: EditProductModalProps) {
    const [formData, setFormData] = useState({
        name: "",
        price: "",
        stock: "",
        categoria: "",
        estoque_minimo: "",
    });

    const updateProduct = useUpdateProduct();

    // Preencher formulário quando o produto mudar
    useEffect(() => {
        if (product) {
            setFormData({
                name: product.nome || "",
                price: product.preco_medio?.toString() || "0",
                stock: product.estoque_atual?.toString() || "0",
                categoria: product.categoria || "",
                estoque_minimo: product.estoque_minimo?.toString() || "0",
            });
        }
    }, [product]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData((prev) => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!product) return;

        await updateProduct.mutateAsync({
            id: product.id,
            data: {
                name: formData.name,
                price: parseFloat(formData.price) || undefined,
                stock: parseInt(formData.stock) || 0,
                ...(formData.categoria !== undefined && { categoria: formData.categoria }),
                ...(formData.estoque_minimo && { estoque_minimo: parseInt(formData.estoque_minimo) || 0 }),
            },
        });

        onOpenChange(false);
    };

    const isFormValid = formData.name.trim() !== "";

    if (!product) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Editar Produto</DialogTitle>
                    <DialogDescription>
                        Atualize as informações do produto <strong>{product.sku}</strong>
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        {/* SKU (readonly) */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="sku" className="text-right">
                                SKU
                            </Label>
                            <Input
                                id="sku"
                                value={product.sku}
                                disabled
                                className="col-span-3 bg-muted"
                            />
                        </div>

                        {/* Nome */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="name" className="text-right">
                                Nome *
                            </Label>
                            <Input
                                id="name"
                                name="name"
                                placeholder="Nome do produto"
                                value={formData.name}
                                onChange={handleInputChange}
                                className="col-span-3"
                                required
                            />
                        </div>

                        {/* Categoria */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="categoria" className="text-right">
                                Categoria
                            </Label>
                            <Input
                                id="categoria"
                                name="categoria"
                                placeholder="Ex: Ferramentas"
                                value={formData.categoria}
                                onChange={handleInputChange}
                                className="col-span-3"
                            />
                        </div>

                        {/* Estoque Atual */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="stock" className="text-right">
                                Estoque Atual
                            </Label>
                            <Input
                                id="stock"
                                name="stock"
                                type="number"
                                min="0"
                                placeholder="0"
                                value={formData.stock}
                                onChange={handleInputChange}
                                className="col-span-3"
                            />
                        </div>

                        {/* Estoque Mínimo */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="estoque_minimo" className="text-right">
                                Estoque Mínimo
                            </Label>
                            <Input
                                id="estoque_minimo"
                                name="estoque_minimo"
                                type="number"
                                min="0"
                                placeholder="0"
                                value={formData.estoque_minimo}
                                onChange={handleInputChange}
                                className="col-span-3"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Cancelar
                        </Button>
                        <Button
                            type="submit"
                            disabled={!isFormValid || updateProduct.isPending}
                        >
                            {updateProduct.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Salvando...
                                </>
                            ) : (
                                "Salvar Alterações"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
