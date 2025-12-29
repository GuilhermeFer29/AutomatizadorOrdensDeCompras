import { useState } from "react";
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
import { Plus, Loader2 } from "lucide-react";
import { useCreateProduct } from "@/hooks/useProducts";

interface CreateProductModalProps {
    trigger?: React.ReactNode;
}

export function CreateProductModal({ trigger }: CreateProductModalProps) {
    const [open, setOpen] = useState(false);
    const [formData, setFormData] = useState({
        sku: "",
        name: "",
        price: "",
        stock: "",
        categoria: "",
        estoque_minimo: "",
    });

    const createProduct = useCreateProduct();

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData((prev) => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        await createProduct.mutateAsync({
            sku: formData.sku,
            name: formData.name,
            price: parseFloat(formData.price) || 0,
            stock: parseInt(formData.stock) || 0,
        });

        // Reset form and close modal
        setFormData({
            sku: "",
            name: "",
            price: "",
            stock: "",
            categoria: "",
            estoque_minimo: "",
        });
        setOpen(false);
    };

    const isFormValid =
        formData.sku.trim() !== "" &&
        formData.name.trim() !== "" &&
        parseFloat(formData.price) > 0;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {trigger || (
                    <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Adicionar Novo Produto
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Adicionar Novo Produto</DialogTitle>
                    <DialogDescription>
                        Preencha as informações do produto. O SKU deve ser único.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        {/* SKU */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="sku" className="text-right">
                                SKU *
                            </Label>
                            <Input
                                id="sku"
                                name="sku"
                                placeholder="Ex: SKU_001"
                                value={formData.sku}
                                onChange={handleInputChange}
                                className="col-span-3"
                                required
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

                        {/* Preço */}
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="price" className="text-right">
                                Preço (R$) *
                            </Label>
                            <Input
                                id="price"
                                name="price"
                                type="number"
                                step="0.01"
                                min="0"
                                placeholder="0.00"
                                value={formData.price}
                                onChange={handleInputChange}
                                className="col-span-3"
                                required
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
                            onClick={() => setOpen(false)}
                        >
                            Cancelar
                        </Button>
                        <Button
                            type="submit"
                            disabled={!isFormValid || createProduct.isPending}
                        >
                            {createProduct.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Criando...
                                </>
                            ) : (
                                "Criar Produto"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
