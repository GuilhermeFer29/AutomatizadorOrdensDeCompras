import { useState, useEffect } from 'react';
import api from '@/services/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { Slider } from '@/components/ui/slider';
import { useToast } from '@/hooks/use-toast';
import { Search, Truck, Star, Clock, Package, MapPin, ChevronRight, Plus, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface Supplier {
    id: number;
    nome: string;
    cep: string | null;
    confiabilidade: number;
    prazo_entrega_dias: number;
    latitude: number | null;
    longitude: number | null;
    ofertas_count: number;
    criado_em: string;
    atualizado_em: string;
}

interface Offer {
    id: number;
    produto_id: number;
    produto_sku: string;
    produto_nome: string;
    preco: number;
    estoque_disponivel: number;
    atualizado_em: string;
}

interface NewSupplier {
    nome: string;
    cep: string;
    confiabilidade: number;
    prazo_entrega_dias: number;
}

export default function Suppliers() {
    const [suppliers, setSuppliers] = useState<Supplier[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
    const [offers, setOffers] = useState<Offer[]>([]);
    const [loadingOffers, setLoadingOffers] = useState(false);

    // Estado para modal de novo fornecedor
    const [showNewModal, setShowNewModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [newSupplier, setNewSupplier] = useState<NewSupplier>({
        nome: '',
        cep: '',
        confiabilidade: 0.9,
        prazo_entrega_dias: 7
    });

    const { toast } = useToast();

    useEffect(() => {
        loadSuppliers();
    }, []);

    const loadSuppliers = async (search?: string) => {
        setLoading(true);
        try {
            const params = search ? { search } : {};
            const response = await api.get('/api/suppliers/', { params });
            setSuppliers(response.data);
        } catch (error) {
            console.error('Erro ao carregar fornecedores:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadOffers = async (supplierId: number) => {
        setLoadingOffers(true);
        try {
            const response = await api.get(`/api/suppliers/${supplierId}/offers`);
            setOffers(response.data.ofertas);
        } catch (error) {
            console.error('Erro ao carregar ofertas:', error);
            setOffers([]);
        } finally {
            setLoadingOffers(false);
        }
    };

    const handleSearch = () => {
        loadSuppliers(searchQuery);
    };

    const handleSelectSupplier = (supplier: Supplier) => {
        setSelectedSupplier(supplier);
        loadOffers(supplier.id);
    };

    const handleCreateSupplier = async () => {
        if (!newSupplier.nome.trim()) {
            toast({
                title: "Erro",
                description: "O nome do fornecedor é obrigatório",
                variant: "destructive"
            });
            return;
        }

        setSaving(true);
        try {
            await api.post('/api/suppliers/', {
                nome: newSupplier.nome,
                cep: newSupplier.cep || null,
                confiabilidade: newSupplier.confiabilidade,
                prazo_entrega_dias: newSupplier.prazo_entrega_dias
            });

            toast({
                title: "Sucesso!",
                description: "Fornecedor cadastrado com sucesso",
            });

            setShowNewModal(false);
            setNewSupplier({ nome: '', cep: '', confiabilidade: 0.9, prazo_entrega_dias: 7 });
            loadSuppliers();
        } catch (error: any) {
            toast({
                title: "Erro ao cadastrar",
                description: error.response?.data?.detail || "Erro desconhecido",
                variant: "destructive"
            });
        } finally {
            setSaving(false);
        }
    };

    const getConfiabilidadeColor = (conf: number) => {
        if (conf >= 0.9) return 'text-green-600 bg-green-100';
        if (conf >= 0.7) return 'text-yellow-600 bg-yellow-100';
        return 'text-red-600 bg-red-100';
    };

    const getConfiabilidadeLabel = (conf: number) => {
        if (conf >= 0.9) return 'Excelente';
        if (conf >= 0.8) return 'Muito Boa';
        if (conf >= 0.7) return 'Boa';
        if (conf >= 0.5) return 'Regular';
        return 'Baixa';
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Truck className="h-6 w-6" />
                        Fornecedores
                    </h1>
                    <p className="text-muted-foreground">
                        Gerencie e visualize informações dos fornecedores cadastrados
                    </p>
                </div>
                <div className="flex gap-2">
                    <Input
                        placeholder="Buscar fornecedor..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                        className="w-64"
                    />
                    <Button variant="outline" onClick={handleSearch}>
                        <Search className="h-4 w-4" />
                    </Button>
                    <Button onClick={() => setShowNewModal(true)}>
                        <Plus className="h-4 w-4 mr-2" />
                        Novo Fornecedor
                    </Button>
                </div>
            </div>

            {/* Estatísticas */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                                <Truck className="h-5 w-5 text-blue-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">{suppliers.length}</p>
                                <p className="text-sm text-muted-foreground">Fornecedores</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-100 rounded-lg">
                                <Star className="h-5 w-5 text-green-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {suppliers.filter(s => s.confiabilidade >= 0.9).length}
                                </p>
                                <p className="text-sm text-muted-foreground">Alta Confiabilidade</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-100 rounded-lg">
                                <Package className="h-5 w-5 text-purple-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {suppliers.reduce((acc, s) => acc + s.ofertas_count, 0)}
                                </p>
                                <p className="text-sm text-muted-foreground">Ofertas Totais</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-orange-100 rounded-lg">
                                <Clock className="h-5 w-5 text-orange-600" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {suppliers.length > 0
                                        ? Math.round(suppliers.reduce((acc, s) => acc + s.prazo_entrega_dias, 0) / suppliers.length)
                                        : 0} dias
                                </p>
                                <p className="text-sm text-muted-foreground">Prazo Médio</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Tabela de Fornecedores */}
            <Card>
                <CardHeader>
                    <CardTitle>Lista de Fornecedores</CardTitle>
                    <CardDescription>
                        Clique em um fornecedor para ver suas ofertas
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="space-y-2">
                            {[...Array(5)].map((_, i) => (
                                <Skeleton key={i} className="h-12 w-full" />
                            ))}
                        </div>
                    ) : suppliers.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            <Truck className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>Nenhum fornecedor encontrado</p>
                            <Button
                                variant="outline"
                                className="mt-4"
                                onClick={() => setShowNewModal(true)}
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Cadastrar primeiro fornecedor
                            </Button>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Fornecedor</TableHead>
                                    <TableHead>Confiabilidade</TableHead>
                                    <TableHead>Prazo</TableHead>
                                    <TableHead>Localização</TableHead>
                                    <TableHead>Ofertas</TableHead>
                                    <TableHead></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {suppliers.map((supplier) => (
                                    <TableRow
                                        key={supplier.id}
                                        className={cn(
                                            "cursor-pointer transition-colors",
                                            selectedSupplier?.id === supplier.id ? "bg-muted" : "hover:bg-muted/50"
                                        )}
                                        onClick={() => handleSelectSupplier(supplier)}
                                    >
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 bg-primary/10 rounded-full">
                                                    <Truck className="h-4 w-4 text-primary" />
                                                </div>
                                                <div>
                                                    <p className="font-medium">{supplier.nome}</p>
                                                    <p className="text-xs text-muted-foreground">
                                                        ID: {supplier.id}
                                                    </p>
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge className={getConfiabilidadeColor(supplier.confiabilidade)}>
                                                <Star className="h-3 w-3 mr-1" />
                                                {(supplier.confiabilidade * 100).toFixed(0)}% - {getConfiabilidadeLabel(supplier.confiabilidade)}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-1 text-sm">
                                                <Clock className="h-4 w-4 text-muted-foreground" />
                                                {supplier.prazo_entrega_dias} dias
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {supplier.cep ? (
                                                <div className="flex items-center gap-1 text-sm">
                                                    <MapPin className="h-4 w-4 text-muted-foreground" />
                                                    {supplier.cep}
                                                </div>
                                            ) : (
                                                <span className="text-muted-foreground">-</span>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline">
                                                {supplier.ofertas_count} produtos
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>

            {/* Dialog de Ofertas */}
            <Dialog open={!!selectedSupplier} onOpenChange={() => setSelectedSupplier(null)}>
                <DialogContent className="max-w-3xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Truck className="h-5 w-5" />
                            {selectedSupplier?.nome}
                        </DialogTitle>
                        <DialogDescription>
                            Ofertas de produtos deste fornecedor
                        </DialogDescription>
                    </DialogHeader>

                    {loadingOffers ? (
                        <div className="space-y-2">
                            {[...Array(3)].map((_, i) => (
                                <Skeleton key={i} className="h-10 w-full" />
                            ))}
                        </div>
                    ) : offers.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            Este fornecedor não possui ofertas cadastradas
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>SKU</TableHead>
                                    <TableHead>Produto</TableHead>
                                    <TableHead>Preço</TableHead>
                                    <TableHead>Estoque</TableHead>
                                    <TableHead>Atualizado</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {offers.map((offer) => (
                                    <TableRow key={offer.id}>
                                        <TableCell className="font-mono">{offer.produto_sku}</TableCell>
                                        <TableCell>{offer.produto_nome}</TableCell>
                                        <TableCell className="font-semibold">
                                            R$ {offer.preco.toFixed(2)}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={offer.estoque_disponivel > 0 ? 'default' : 'destructive'}>
                                                {offer.estoque_disponivel} un
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {formatDistanceToNow(new Date(offer.atualizado_em), {
                                                addSuffix: true,
                                                locale: ptBR
                                            })}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </DialogContent>
            </Dialog>

            {/* Dialog de Novo Fornecedor */}
            <Dialog open={showNewModal} onOpenChange={setShowNewModal}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Plus className="h-5 w-5" />
                            Novo Fornecedor
                        </DialogTitle>
                        <DialogDescription>
                            Preencha os dados para cadastrar um novo fornecedor
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="nome">Nome do Fornecedor *</Label>
                            <Input
                                id="nome"
                                placeholder="Ex: Distribuidora ABC"
                                value={newSupplier.nome}
                                onChange={(e) => setNewSupplier({ ...newSupplier, nome: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="cep">CEP (opcional)</Label>
                            <Input
                                id="cep"
                                placeholder="Ex: 01310-100"
                                value={newSupplier.cep}
                                onChange={(e) => setNewSupplier({ ...newSupplier, cep: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Confiabilidade: {(newSupplier.confiabilidade * 100).toFixed(0)}%</Label>
                            <Slider
                                value={[newSupplier.confiabilidade * 100]}
                                onValueChange={(value) => setNewSupplier({ ...newSupplier, confiabilidade: value[0] / 100 })}
                                max={100}
                                min={0}
                                step={5}
                            />
                            <p className="text-xs text-muted-foreground">
                                {getConfiabilidadeLabel(newSupplier.confiabilidade)}
                            </p>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="prazo">Prazo de Entrega (dias)</Label>
                            <Input
                                id="prazo"
                                type="number"
                                min={1}
                                max={60}
                                value={newSupplier.prazo_entrega_dias}
                                onChange={(e) => setNewSupplier({ ...newSupplier, prazo_entrega_dias: parseInt(e.target.value) || 7 })}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowNewModal(false)}>
                            Cancelar
                        </Button>
                        <Button onClick={handleCreateSupplier} disabled={saving}>
                            {saving ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Salvando...
                                </>
                            ) : (
                                <>
                                    <Plus className="h-4 w-4 mr-2" />
                                    Cadastrar
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
