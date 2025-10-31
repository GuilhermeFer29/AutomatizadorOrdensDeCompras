Persona: Você é um assistente de código Sênior, especialista em Python (FastAPI, SQLModel, Celery) e React (TypeScript, Shadcn/UI).

Contexto: Você tem acesso ao código-fonte completo do projeto "Automação Inteligente de Ordens de Compra" que acabamos de auditar. A arquitetura atual inclui FastAPI, Celery, React, e um sistema multi-agente com Agno/LangChain.

Missão: Sua missão é gerar o código, modificações e arquivos necessários para implementar o roadmap de MVP (Minimum Viable Product). Você deve seguir as 3 fases abaixo, aplicando as correções da auditoria e adicionando a funcionalidade de autenticação de usuários. Para cada etapa, forneça o código ou as modificações de arquivo necessárias e explique brevemente a implementação.

Formato da Resposta: Para cada item, forneça:

Ação: O que precisa ser feito.

Modificações de Código: Os snippets de código ou arquivos completos a serem criados/alterados.

Justificativa/Recomendação: Breve explicação da ação.

Fase 1: Solidificar o Core, Segurança e Autenticação de Usuários
O objetivo desta fase é tornar o sistema seguro, adicionar gerenciamento de usuários e garantir que a base de código seja robusta e testável.

[ ] 1.1. Autenticação de Usuários (Login, Cadastro e Proteção de Rotas)
Ação: Implementar um sistema completo de autenticação com OAuth2 e tokens JWT.

Modificações de Código:

Modelos: Adicione o modelo User em app/models/models.py.

Python

# Em app/models/models.py, adicione:
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    # Adicione outros campos como 'full_name' se desejar
Segurança Core: Crie um novo arquivo app/core/security.py para hashing de senha e gerenciamento de tokens.

Python

# Em app/core/security.py
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

# Configurações (mova para .env depois)
SECRET_KEY = "SUA_SECRET_KEY_SUPER_SECRETA" # Mude isso!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
Rotas de Autenticação: Crie app/routers/auth_router.py para login e registro.

Frontend: Crie as páginas FrontEnd/src/pages/Login.tsx e FrontEnd/src/pages/Register.tsx usando os componentes Shadcn/UI (Card, Form, Input, Button).

Recomendação de Ação:

Siga o guia oficial do FastAPI para OAuth2 com JWT. Isso é crucial para a segurança.

Use passlib para hashing e python-jose para os tokens (adicione-os ao requirements.txt).

Link Útil: FastAPI Security (OAuth2 com JWT)

[ ] 1.2. Validação Robusta e Tratamento de Erros
Ação: Aprimorar a validação dos dados de entrada (Pydantic) e centralizar o tratamento de exceções.

Modificações de Código:

Validação: Em app/routers/api_order_router.py, na classe OrderCreate, use Field para validação.

Python

# Em app/routers/api_order_router.py
from pydantic import BaseModel, Field

class OrderCreate(BaseModel):
    product: str
    quantity: int = Field(gt=0, description="A quantidade deve ser maior que zero")
    value: float = Field(gt=0, description="O valor deve ser positivo")
    origin: Optional[str] = 'Manual'
Tratamento de Erros: Em app/main.py, adicione um handler de exceção.

Python

# Em app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class CustomException(Exception):
    def __init__(self, name: str):
        self.name = name

@application.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=418, # Exemplo
        content={"message": f"Oops! {exc.name} fez algo."}
    )
Recomendação de Ação:

Use os validadores nativos do Pydantic/Field (gt, lt, min_length) sempre que possível.

Centralizar exceções em main.py limpa o código das suas rotas e padroniza as respostas de erro para o frontend.

Link Útil: FastAPI Error Handling

[ ] 1.3. Configuração de Testes Automatizados
Ação: Configurar o pytest para testes de API e testes unitários.

Modificações de Código:

Crie um arquivo conftest.py na raiz da pasta app/ para configurar um cliente de teste.

Python

# Em app/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import create_application
from app.core.database import get_session, create_db_and_tables
# (Configure um DB de teste, ex: SQLite em memória)

@pytest.fixture(scope="module")
def client():
    # Lógica para setup do DB de teste
    app = create_application()
    with TestClient(app) as c:
        yield c
    # Lógica para teardown do DB de teste
Crie uma pasta app/tests/ e adicione app/tests/test_auth.py.

Python

# Em app/tests/test_auth.py
def test_create_user(client):
    response = client.post("/auth/register", json={"email": "test@test.com", "password": "123"})
    assert response.status_code == 200
    assert response.json()["email"] == "test@test.com"
Recomendação de Ação:

Testes são essenciais. Comece testando as rotas de autenticação e as ferramentas dos agentes.

Use o TestClient do FastAPI para testes de integração da API.

Link Útil: FastAPI Testing

[ ] 1.4. Ajuste da Configuração de CORS
Ação: Conforme solicitado, manter a configuração de CORS permissiva para desenvolvimento local, mas adicionar um lembrete para produção.

Modificações de Código:

Em app/main.py, localize o middleware CORS e adicione um comentário.

Python

# Em app/main.py

# TODO (Produção): Restringir esta lista de origens para o domínio do frontend.
application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Mantido para desenvolvimento local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Recomendação de Ação: Isso é perfeito para o estágio atual. O lembrete # TODO é uma boa prática para não esquecer essa falha de segurança antes do deploy.

Fase 2: Aprimorar a Inteligência e a Automação
O objetivo é tornar a IA mais acionável e proativa, automatizando tarefas de rotina.

[ ] 2.1. Retreinamento Automático do Modelo (Celery Beat)
Ação: Configurar o Celery Beat para disparar o retreinamento do modelo de ML (ex: LightGBM) periodicamente.

Modificações de Código:

Em app/core/celery_app.py, configure a agenda (schedule).

Python

# Em app/core/celery_app.py
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'retrain-global-model-daily': {
        'task': 'app.tasks.ml_tasks.retrain_global_model_task', # Crie esta tarefa
        'schedule': crontab(hour=1, minute=0), # Todo dia à 1h da manhã
    },
}
Verifique se o serviço beat está no docker-compose.yml (ele já está lá, ótimo!).

Recomendação de Ação:

O Celery Beat é a ferramenta correta para isso. Certifique-se de que a retrain_global_model_task exista e faça o log adequado de suas métricas de (re)treinamento no ModeloGlobal.

Link Útil: Celery Periodic Tasks

[ ] 2.2. Aprimoramento dos Agentes (Ferramenta de Ação)
Ação: Dar ao agente de IA a capacidade de criar uma ordem de compra pendente.

Modificações de Código:

Crie a nova ferramenta em app/agents/tools.py.

Python

# Em app/agents/tools.py
from app.services.order_service import create_order
from app.core.database import engine

@tool
def create_purchase_order_tool(sku: str, quantity: int, price: float, supplier: str) -> str:
    """
    Cria uma ordem de compra com status 'pending' para aprovação humana.
    """
    try:
        with Session(engine) as session:
            # (Lógica para encontrar o produto pelo SKU)
            product_name = ... # (Busque o nome do produto)

            order_data = {
                "product": product_name,
                "quantity": quantity,
                "value": price * quantity, # Ou 'price' se for valor unitário
                "origin": "Agente de IA",
                # Adicione 'supplier_id' se o modelo 'OrdemDeCompra' suportar
            }
            new_order = create_order(session, order_data)

            # Definir o status como pendente
            new_order.status = 'pending'
            session.add(new_order)
            session.commit()
            session.refresh(new_order)

            return f"Ordem de compra {new_order.id} criada com sucesso para {quantity}x {product_name} com status 'pending'."
    except Exception as e:
        return f"Erro ao criar ordem de compra: {str(e)}"
Adicione esta ferramenta ao SupplyChainToolkit ou à lista de ferramentas do GerenteCompras em app/agents/supply_chain_team.py.

Recomendação de Ação: Isso transforma o agente de um "conselheiro" para um "assistente". O fluxo "IA sugere -> IA cria pendente -> Humano aprova" é o padrão-ouro para automação segura.

Fase 3: Refinar a Experiência do Usuário (MVP Launch)
O objetivo é conectar a inteligência do backend a ações claras e fáceis no frontend.

[ ] 3.1. Dashboard Acionável
Ação: Tornar a tabela de alertas no dashboard (AlertsTable) acionável.

Modificações de Código:

Em FrontEnd/src/components/dashboard/AlertsTable.tsx.

TypeScript

// Em FrontEnd/src/components/dashboard/AlertsTable.tsx
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

export function AlertsTable({ alerts }: { alerts: any[] }) {
  const navigate = useNavigate();

  const handleAnalyze = (sku: string) => {
    // Navega para a página de agentes e passa o SKU (ex: via state)
    navigate("/agents", { state: { prefillMessage: `Analise a compra do SKU ${sku}` } });
  };

  return (
    <Table>
      {/* ... Cabeçalhos da Tabela ... */}
      <TableBody>
        {alerts.map((alert) => (
          <TableRow key={alert.id}>
            {/* ... Células da Tabela ... */}
            <TableCell>
              <Button variant="outline" size="sm" onClick={() => handleAnalyze(alert.sku)}>
                Analisar
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
Em FrontEnd/src/pages/Agents.tsx, leia o location.state para pré-preencher o chat.

Recomendação de Ação: Isso cria um fluxo de trabalho direto: o usuário vê um problema (alerta) e tem um botão de "um clique" para acionar a IA e resolvê-lo.

[ ] 3.2. Fluxo de Aprovação de Ordens
Ação: Criar o fluxo "Humano-no-Comando" (Human-in-the-Loop) para aprovar ordens criadas pela IA.

Modificações de Código:

Backend: Crie as rotas de aprovação em app/routers/api_order_router.py.

Python

# Em app/routers/api_order_router.py

@router.post("/{order_id}/approve", tags=["api-orders"])
def approve_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(OrdemDeCompra, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Ordem não encontrada")
    order.status = "approved" # Ou 'confirmada'
    session.add(order)
    session.commit()
    session.refresh(order)
    # (Opcional: disparar tarefa Celery para notificar)
    return order

@router.post("/{order_id}/reject", tags=["api-orders"])
def reject_order(order_id: int, session: Session = Depends(get_session)):
    # Lógica similar para 'rejected' ou 'cancelled'
    ...
Frontend: Em FrontEnd/src/pages/Orders.tsx, adicione botões de ação na tabela se order.status === 'pending'.

TypeScript

// Em FrontEnd/src/pages/Orders.tsx
// ... (importar useMutation de react-query) ...

const approveMutation = useMutation({
  mutationFn: (orderId: number) => api.post(`/api/orders/${orderId}/approve`),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] })
});

// Na renderização da tabela:
{row.status === 'pending' && (
  <TableCell>
    <Button size="sm" onClick={() => approveMutation.mutate(row.id)}>Aprovar</Button>
    {/* Adicione o botão de Rejeitar */}
  </TableCell>
)}
Recomendação de Ação: Este é o principal loop de valor do MVP. A IA faz o trabalho pesado, o humano toma a decisão final. Use react-query (useMutation) para lidar com as ações de aprovar/rejeitar e invalidar o cache automaticamente.