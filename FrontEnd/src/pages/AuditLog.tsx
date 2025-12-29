import { useState, useEffect } from 'react';
import api from '@/services/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, FileText, Bot, Package, Calendar, Eye, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDistanceToNow, format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface Decision {
    id: number;
    agente_nome: string;
    sku: string;
    acao: string;
    decisao_preview: string;
    data_decisao: string;
    usuario_id: string | null;
}

interface DecisionDetail {
    id: number;
    agente_nome: string;
    sku: string;
    acao: string;
    decisao: string;
    raciocinio: string;
    contexto: string;
    usuario_id: string | null;
    data_decisao: string;
    ip_origem: string | null;
}

interface AuditStats {
    total_decisions: number;
    period_days: number;
    by_agent: Record<string, number>;
    by_action: Record<string, number>;
    top_skus: Record<string, number>;
}

export default function AuditLog() {
    const [decisions, setDecisions] = useState<Decision[]>([]);
    const [stats, setStats] = useState<AuditStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchSku, setSearchSku] = useState('');
    const [selectedDecision, setSelectedDecision] = useState<DecisionDetail | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);

    useEffect(() => {
        loadDecisions();
        loadStats();
    }, []);

    const loadDecisions = async (sku?: string) => {
        setLoading(true);
        try {
            const params: Record<string, any> = { limit: 100 };
            if (sku) params.sku = sku;

            const response = await api.get('/api/audit/decisions/', { params });
            setDecisions(response.data);
        } catch (error) {
            console.error('Erro ao carregar decisões:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadStats = async () => {
        try {
            const response = await api.get('/api/audit/stats/');
            setStats(response.data);
        } catch (error) {
            console.error('Erro ao carregar estatísticas:', error);
        }
    };

    const loadDecisionDetail = async (id: number) => {
        setLoadingDetail(true);
        try {
            const response = await api.get(`/api/audit/decisions/${id}`);
            setSelectedDecision(response.data);
        } catch (error) {
            console.error('Erro ao carregar detalhes:', error);
        } finally {
            setLoadingDetail(false);
        }
    };

    const handleSearch = () => {
        loadDecisions(searchSku);
    };

    const getActionColor = (action: string) => {
        const colors: Record<string, string> = {
            'approve': 'bg-green-100 text-green-700',
            'reject': 'bg-red-100 text-red-700',
            'manual_review': 'bg-yellow-100 text-yellow-700',
            'recommend_supplier': 'bg-blue-100 text-blue-700',
        };
        return colors[action] || 'bg-gray-100 text-gray-700';
    };

    const getActionLabel = (action: string) => {
        const labels: Record<string, string> = {
            'approve': 'Aprovado',
            'reject': 'Rejeitado',
            'manual_review': 'Revisão Manual',
            'recommend_supplier': 'Recomendação',
        };
        return labels[action] || action;
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <FileText className="h-6 w-6" />
                        Log de Auditoria
                    </h1>
                    <p className="text-muted-foreground">
                        Histórico de decisões tomadas pelos agentes
                    </p>
                </div>
                <div className="flex gap-2">
                    <Input
                        placeholder="Filtrar por SKU..."
                        value={searchSku}
                        onChange={(e) => setSearchSku(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                        className="w-48"
                    />
                    <Button variant="outline" onClick={handleSearch}>
                        <Search className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" onClick={() => { loadDecisions(); loadStats(); }}>
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Estatísticas */}
            {stats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card>
                        <CardContent className="p-4">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-blue-100 rounded-lg">
                                    <FileText className="h-5 w-5 text-blue-600" />
                                </div>
                                <div>
                                    <p className="text-2xl font-bold">{stats.total_decisions}</p>
                                    <p className="text-sm text-muted-foreground">Decisões (30 dias)</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-green-100 rounded-lg">
                                    <Bot className="h-5 w-5 text-green-600" />
                                </div>
                                <div>
                                    <p className="text-2xl font-bold">{Object.keys(stats.by_agent).length}</p>
                                    <p className="text-sm text-muted-foreground">Agentes Ativos</p>
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
                                    <p className="text-2xl font-bold">{Object.keys(stats.top_skus).length}</p>
                                    <p className="text-sm text-muted-foreground">SKUs Analisados</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-orange-100 rounded-lg">
                                    <Calendar className="h-5 w-5 text-orange-600" />
                                </div>
                                <div>
                                    <p className="text-2xl font-bold">{stats.period_days}</p>
                                    <p className="text-sm text-muted-foreground">Dias de Histórico</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Tabela de Decisões */}
            <Card>
                <CardHeader>
                    <CardTitle>Histórico de Decisões</CardTitle>
                    <CardDescription>
                        Clique em uma decisão para ver os detalhes completos
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="space-y-2">
                            {[...Array(5)].map((_, i) => (
                                <Skeleton key={i} className="h-12 w-full" />
                            ))}
                        </div>
                    ) : decisions.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>Nenhuma decisão registrada</p>
                            <p className="text-sm">As decisões dos agentes aparecerão aqui</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Data</TableHead>
                                    <TableHead>Agente</TableHead>
                                    <TableHead>SKU</TableHead>
                                    <TableHead>Ação</TableHead>
                                    <TableHead>Preview</TableHead>
                                    <TableHead></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {decisions.map((decision) => (
                                    <TableRow
                                        key={decision.id}
                                        className="cursor-pointer hover:bg-muted/50"
                                        onClick={() => loadDecisionDetail(decision.id)}
                                    >
                                        <TableCell className="text-sm">
                                            <div className="flex flex-col">
                                                <span>{format(new Date(decision.data_decisao), 'dd/MM/yyyy', { locale: ptBR })}</span>
                                                <span className="text-xs text-muted-foreground">
                                                    {format(new Date(decision.data_decisao), 'HH:mm', { locale: ptBR })}
                                                </span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <Bot className="h-4 w-4 text-muted-foreground" />
                                                <span className="font-medium">{decision.agente_nome}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="font-mono">
                                                {decision.sku}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge className={getActionColor(decision.acao)}>
                                                {getActionLabel(decision.acao)}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                                            {decision.decisao_preview}
                                        </TableCell>
                                        <TableCell>
                                            <Eye className="h-4 w-4 text-muted-foreground" />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>

            {/* Dialog de Detalhes */}
            <Dialog open={!!selectedDecision} onOpenChange={() => setSelectedDecision(null)}>
                <DialogContent className="max-w-4xl max-h-[80vh]">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5" />
                            Detalhes da Decisão #{selectedDecision?.id}
                        </DialogTitle>
                        <DialogDescription>
                            {selectedDecision && format(new Date(selectedDecision.data_decisao), "dd 'de' MMMM 'de' yyyy 'às' HH:mm", { locale: ptBR })}
                        </DialogDescription>
                    </DialogHeader>

                    {loadingDetail ? (
                        <div className="space-y-4">
                            <Skeleton className="h-20 w-full" />
                            <Skeleton className="h-40 w-full" />
                        </div>
                    ) : selectedDecision && (
                        <ScrollArea className="max-h-[60vh]">
                            <div className="space-y-4 pr-4">
                                {/* Info básica */}
                                <div className="grid grid-cols-3 gap-4">
                                    <div>
                                        <p className="text-sm text-muted-foreground">Agente</p>
                                        <p className="font-medium">{selectedDecision.agente_nome}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">SKU</p>
                                        <Badge variant="outline" className="font-mono">{selectedDecision.sku}</Badge>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Ação</p>
                                        <Badge className={getActionColor(selectedDecision.acao)}>
                                            {getActionLabel(selectedDecision.acao)}
                                        </Badge>
                                    </div>
                                </div>

                                {/* Decisão */}
                                <div className="space-y-2">
                                    <p className="text-sm font-medium">Decisão</p>
                                    <div className="p-4 bg-muted rounded-lg">
                                        <pre className="whitespace-pre-wrap text-sm">{selectedDecision.decisao}</pre>
                                    </div>
                                </div>

                                {/* Raciocínio */}
                                <div className="space-y-2">
                                    <p className="text-sm font-medium">Raciocínio do Agente</p>
                                    <div className="p-4 bg-muted rounded-lg">
                                        <pre className="whitespace-pre-wrap text-sm">{selectedDecision.raciocinio}</pre>
                                    </div>
                                </div>

                                {/* Contexto */}
                                <div className="space-y-2">
                                    <p className="text-sm font-medium">Contexto da Solicitação</p>
                                    <div className="p-4 bg-muted rounded-lg">
                                        <pre className="whitespace-pre-wrap text-sm">{selectedDecision.contexto}</pre>
                                    </div>
                                </div>

                                {/* Metadata */}
                                {(selectedDecision.usuario_id || selectedDecision.ip_origem) && (
                                    <div className="flex gap-4 text-sm text-muted-foreground border-t pt-4">
                                        {selectedDecision.usuario_id && (
                                            <span>Usuário: {selectedDecision.usuario_id}</span>
                                        )}
                                        {selectedDecision.ip_origem && (
                                            <span>IP: {selectedDecision.ip_origem}</span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </ScrollArea>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
