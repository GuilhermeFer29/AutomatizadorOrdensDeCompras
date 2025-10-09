import { useAgents, useToggleAgent, useRunAgent } from "@/hooks/useAgents";
import { AgentStatus } from "@/types/api.types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bot, Pause, Play, Eye } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { ErrorMessage } from "@/components/ui/error-message";

const statusConfig = {
  active: {
    label: "Ativo",
    className: "bg-success/10 text-success hover:bg-success/20"
  },
  inactive: {
    label: "Inativo",
    className: "bg-muted text-muted-foreground hover:bg-muted"
  }
};

export default function Agents() {
  const { data: agents, isLoading, error, refetch } = useAgents();
  const toggleAgent = useToggleAgent();
  const runAgent = useRunAgent();

  const handleToggle = (agentId: number, currentStatus: AgentStatus) => {
    const action = currentStatus === 'active' ? 'pause' : 'activate';
    toggleAgent.mutate({ agentId, action });
  };

  const handleRunNow = (agentId: number) => {
    runAgent.mutate(agentId);
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message="Falha ao carregar agentes." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-foreground">Hub de Agentes</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Gerencie e monitore os agentes autônomos do sistema
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {agents?.map((agent) => (
          <Card key={agent.id} className="shadow-sm hover:shadow-md transition-shadow">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Bot className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{agent.name}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {agent.description}
                    </p>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <Badge className={statusConfig[agent.status].className} variant="secondary">
                    {statusConfig[agent.status].label}
                  </Badge>
                </div>
                <div className="space-y-1 text-right">
                  <p className="text-sm font-medium text-muted-foreground">Última Atividade</p>
                  <p className="text-sm text-foreground">{agent.lastRun}</p>
                </div>
              </div>

              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="flex-1"
                  onClick={() => handleToggle(agent.id, agent.status)}
                  disabled={toggleAgent.isPending}
                >
                  {agent.status === "active" ? (
                    <>
                      <Pause className="h-4 w-4 mr-2" />
                      Pausar
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Ativar
                    </>
                  )}
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => handleRunNow(agent.id)}
                  disabled={runAgent.isPending}
                >
                  <Play className="h-4 w-4 mr-2" />
                  Executar Agora
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                >
                  <Eye className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
