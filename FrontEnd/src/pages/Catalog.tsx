import { useState } from "react";
import { useProducts } from "@/hooks/useProducts";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Edit, TrendingUp, AlertTriangle } from "lucide-react";
import { CreateProductModal } from "@/components/products/CreateProductModal";
import { EditProductModal } from "@/components/products/EditProductModal";
import { ProductDetailsModal } from "@/components/products/ProductDetailsModal";
import { Product } from "@/types/api.types";

export default function Catalog() {
  const [searchTerm, setSearchTerm] = useState("");
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [detailsProduct, setDetailsProduct] = useState<Product | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  const { data: products, isLoading } = useProducts(searchTerm);

  const handleEditClick = (product: Product) => {
    setEditingProduct(product);
    setIsEditModalOpen(true);
  };

  const handleDetailsClick = (product: Product) => {
    setDetailsProduct(product);
    setIsDetailsModalOpen(true);
  };

  const getStockStatus = (product: Product) => {
    if (product.estoque_atual < product.estoque_minimo) {
      return { label: "Baixo", variant: "destructive" as const };
    }
    if (product.estoque_atual < product.estoque_minimo * 1.5) {
      return { label: "Atenção", variant: "warning" as const };
    }
    return { label: "OK", variant: "success" as const };
  };

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-foreground">Catálogo de Produtos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Gerencie produtos, fornecedores e histórico de preços
          </p>
        </div>
        <CreateProductModal />
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Buscar Produtos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por nome ou SKU..."
              className="pl-9"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Nome do Produto</TableHead>
                <TableHead>Fornecedor</TableHead>
                <TableHead className="text-right">Preço Médio</TableHead>
                <TableHead className="text-right">Estoque</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products?.map((product) => {
                const stockStatus = getStockStatus(product);
                return (
                  <TableRow key={product.id} className="hover:bg-muted/50">
                    <TableCell className="font-medium font-mono">{product.sku}</TableCell>
                    <TableCell>{product.nome}</TableCell>
                    <TableCell className="text-muted-foreground">{product.fornecedor_padrao || '-'}</TableCell>
                    <TableCell className="text-right">
                      {new Intl.NumberFormat('pt-BR', {
                        style: 'currency',
                        currency: 'BRL'
                      }).format(product.preco_medio || 0)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span>{product.estoque_atual}</span>
                        {product.estoque_atual < product.estoque_minimo && (
                          <Badge variant="destructive" className="text-xs">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            {stockStatus.label}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditClick(product)}
                          title="Editar produto"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDetailsClick(product)}
                          title="Ver histórico e previsões"
                        >
                          <TrendingUp className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Modal de Edição */}
      <EditProductModal
        product={editingProduct}
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
      />

      {/* Modal de Detalhes */}
      <ProductDetailsModal
        product={detailsProduct}
        open={isDetailsModalOpen}
        onOpenChange={setIsDetailsModalOpen}
      />
    </div>
  );
}
