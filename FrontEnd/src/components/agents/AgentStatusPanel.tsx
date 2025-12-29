import { useAgents, useToggleAgent, useRunAgent } from "@/hooks/useAgents";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Bot,
    Play,
    Pause,
    RefreshCw,
    Clock,
    CheckCircle2,
    XCircle,
    Loader2
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";

export function AgentStatusPanel() {
    const { data: agents, isLoading, refetch } = useAgents();
    const toggleAgent = useToggleAgent();
    const runAgent = useRunAgent();

    if (isLoading) {
        return (
            <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Bot className="h-5 w-5" />
                        Status dos Agentes
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-16 w-full" />
                    </div>
                </CardContent>
            </Card>
        );
    }

    const handleToggle = (agentId: number, currentStatus: string) => {
        const action = currentStatus === 'active' ? 'pause' : 'activate';
        toggleAgent.mutate({ agentId, action });
    };

    const handleRun = (agentId: number) => {
        runAgent.mutate(agentId);
    };

    return (
        <Card className="shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle className="flex items-center gap-2">
                        <Bot className="h-5 w-5" />
                        Status dos Agentes
                    </CardTitle>
                    <CardDescription>
                        Monitore e controle os agentes do sistema
                    </CardDescription>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refetch()}
                    title="Atualizar status"
                >
                    <RefreshCw className="h-4 w-4" />
                </Button>
            </CardHeader>
            <CardContent>
                {!agents || agents.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
                        <p>Nenhum agente configurado</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {agents.map((agent) => (
                            <div
                                key={agent.id}
                                className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
                            >
                                <div className="flex items-center gap-4">
                                    {/* Status Indicator */}
                                    <div className="relative">
                                        <Bot className={`h-8 w-8 ${agent.status === 'active' ? 'text-green-500' : 'text-muted-foreground'}`} />
                                        {agent.status === 'active' && (
                                            <span className="absolute -top-1 -right-1 h-3 w-3 bg-green-500 rounded-full animate-pulse" />
                                        )}
                                    </div>

                                    {/* Agent Info */}
                                    <div>
                                        <h4 className="font-medium">{agent.name}</h4>
                                        <p className="text-sm text-muted-foreground">{agent.description}</p>
                                        {agent.lastRun && (
                                            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                                                <Clock className="h-3 w-3" />
                                                <span>
                                                    Última execução:{" "}
                                                    {formatDistanceToNow(new Date(agent.lastRun), {
                                                        addSuffix: true,
                                                        locale: ptBR,
                                                    })}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex items-center gap-2">
                                    <Badge
                                        variant={agent.status === 'active' ? 'default' : 'secondary'}
                                        className="min-w-[80px] justify-center"
                                    >
                                        {agent.status === 'active' ? (
                                            <>
                                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                                Ativo
                                            </>
                                        ) : (
                                            <>
                                                <XCircle className="h-3 w-3 mr-1" />
                                                Inativo
                                            </>
                                        )}
                                    </Badge>

                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleToggle(agent.id, agent.status)}
                                        disabled={toggleAgent.isPending}
                                        title={agent.status === 'active' ? 'Pausar agente' : 'Ativar agente'}
                                    >
                                        {toggleAgent.isPending ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : agent.status === 'active' ? (
                                            <Pause className="h-4 w-4" />
                                        ) : (
                                            <Play className="h-4 w-4" />
                                        )}
                                    </Button>

                                    <Button
                                        variant="default"
                                        size="sm"
                                        onClick={() => handleRun(agent.id)}
                                        disabled={runAgent.isPending || agent.status !== 'active'}
                                        title="Executar agora"
                                    >
                                        {runAgent.isPending ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <>
                                                <RefreshCw className="h-4 w-4 mr-1" />
                                                Executar
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
