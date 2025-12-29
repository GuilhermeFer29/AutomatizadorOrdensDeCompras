import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import {
    Settings2,
    Database,
    Brain,
    RefreshCw,
    CheckCircle2,
    XCircle,
    Loader2,
    Server,
    Cpu,
    HardDrive
} from "lucide-react";
import api from "@/services/api";
import { useMutation } from "@tanstack/react-query";
import { toast } from "@/components/ui/use-toast";

export default function Settings() {
    const [ragStatus, setRagStatus] = useState<{
        indexed: number;
        lastSync: string | null;
    } | null>(null);
    const [checkingRag, setCheckingRag] = useState(false);

    // Mutation para sincronizar RAG
    const syncRAGMutation = useMutation({
        mutationFn: async () => {
            const response = await api.post('/api/rag/sync');
            return response.data;
        },
        onSuccess: (data) => {
            toast({
                title: "RAG Sincronizado",
                description: `${data.products_indexed || 0} produtos indexados com sucesso!`,
            });
            checkRagStatus();
        },
        onError: (error: any) => {
            toast({
                title: "Erro",
                description: error.response?.data?.detail || "Falha ao sincronizar RAG",
                variant: "destructive",
            });
        },
    });

    // Mutation para treinar modelos ML
    const trainModelsMutation = useMutation({
        mutationFn: async () => {
            const response = await api.post('/ml/train/all/async');
            return response.data;
        },
        onSuccess: (data) => {
            toast({
                title: "Treinamento Iniciado",
                description: data.message || "Os modelos estão sendo treinados em background.",
            });
        },
        onError: (error: any) => {
            toast({
                title: "Erro",
                description: error.response?.data?.detail || "Falha ao iniciar treinamento",
                variant: "destructive",
            });
        },
    });

    const checkRagStatus = async () => {
        setCheckingRag(true);
        try {
            const response = await api.get('/api/rag/status');
            setRagStatus({
                indexed: response.data.products_indexed || 0,
                lastSync: response.data.last_sync || null,
            });
        } catch (error) {
            console.error('Erro ao verificar status RAG:', error);
        } finally {
            setCheckingRag(false);
        }
    };

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-semibold text-foreground flex items-center gap-2">
                    <Settings2 className="h-8 w-8" />
                    Configurações
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Gerencie o sistema, modelos de ML e base de conhecimento
                </p>
            </div>

            {/* RAG Section */}
            <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        Base de Conhecimento (RAG)
                    </CardTitle>
                    <CardDescription>
                        Sistema de busca semântica para consultas sobre produtos
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <p className="text-sm font-medium">Status do ChromaDB</p>
                            <p className="text-sm text-muted-foreground">
                                Indexação de produtos no vector store
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            {ragStatus ? (
                                <Badge variant="default">
                                    <CheckCircle2 className="h-3 w-3 mr-1" />
                                    {ragStatus.indexed} produtos
                                </Badge>
                            ) : (
                                <Badge variant="secondary">
                                    <XCircle className="h-3 w-3 mr-1" />
                                    Não verificado
                                </Badge>
                            )}
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={checkRagStatus}
                                disabled={checkingRag}
                            >
                                {checkingRag ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <RefreshCw className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                    </div>

                    <Separator />

                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <p className="text-sm font-medium">Sincronizar RAG</p>
                            <p className="text-sm text-muted-foreground">
                                Atualiza a base de conhecimento com produtos do banco de dados
                            </p>
                        </div>
                        <Button
                            onClick={() => syncRAGMutation.mutate()}
                            disabled={syncRAGMutation.isPending}
                        >
                            {syncRAGMutation.isPending ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Sincronizando...
                                </>
                            ) : (
                                <>
                                    <Database className="h-4 w-4 mr-2" />
                                    Sincronizar
                                </>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* ML Section */}
            <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Brain className="h-5 w-5" />
                        Machine Learning
                    </CardTitle>
                    <CardDescription>
                        Modelos de previsão de preços e demanda
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <p className="text-sm font-medium">Treinar Modelos</p>
                            <p className="text-sm text-muted-foreground">
                                Inicia o treinamento dos modelos de previsão (StatsForecast/AutoARIMA)
                            </p>
                        </div>
                        <Button
                            onClick={() => trainModelsMutation.mutate()}
                            disabled={trainModelsMutation.isPending}
                        >
                            {trainModelsMutation.isPending ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Treinando...
                                </>
                            ) : (
                                <>
                                    <Cpu className="h-4 w-4 mr-2" />
                                    Treinar Modelos
                                </>
                            )}
                        </Button>
                    </div>

                    <Alert>
                        <AlertDescription className="text-sm">
                            O treinamento pode demorar alguns minutos dependendo da quantidade de dados.
                            Os modelos são treinados em background usando Celery.
                        </AlertDescription>
                    </Alert>
                </CardContent>
            </Card>

            {/* System Info Section */}
            <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Server className="h-5 w-5" />
                        Informações do Sistema
                    </CardTitle>
                    <CardDescription>
                        Status e informações técnicas
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="p-4 rounded-lg border">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                                <Server className="h-4 w-4" />
                                Backend
                            </div>
                            <p className="font-medium">FastAPI + Agno</p>
                            <p className="text-xs text-muted-foreground">Python 3.11+</p>
                        </div>
                        <div className="p-4 rounded-lg border">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                                <Brain className="h-4 w-4" />
                                LLM
                            </div>
                            <p className="font-medium">Gemini 2.5 Flash</p>
                            <p className="text-xs text-muted-foreground">Google AI</p>
                        </div>
                        <div className="p-4 rounded-lg border">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                                <HardDrive className="h-4 w-4" />
                                Vector Store
                            </div>
                            <p className="font-medium">ChromaDB</p>
                            <p className="text-xs text-muted-foreground">text-embedding-004</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
