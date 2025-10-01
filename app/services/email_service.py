"""SMTP-based e-mail notification service for training reports."""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Mapping, Optional
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


@dataclass
class TrainingReportData:
    """Data structure for training report information."""
    produto_id: int
    pdf_path: str
    metricas: Mapping[str, float]
    to_email: Optional[str] = None
    produto_nome: Optional[str] = None


def send_training_report(report_data: TrainingReportData) -> None:
    """Send the Prophet training report via SMTP with the provided PDF attachment."""
    smtp_config = _get_smtp_config()
    _validate_smtp_config(smtp_config)
    
    attachment_path = _validate_pdf_attachment(report_data.pdf_path)
    recipient = _get_recipient_email(report_data.to_email, smtp_config)
    
    message = _create_email_message(report_data, smtp_config, recipient, attachment_path)
    _send_email(message, smtp_config, report_data)


def _get_smtp_config() -> dict:
    """Get SMTP configuration from environment variables."""
    smtp_username = os.getenv("SMTP_USERNAME")
    return {
        "server": os.getenv("SMTP_SERVER"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": smtp_username,
        "password": os.getenv("SMTP_PASSWORD"),
        "email_from": os.getenv("EMAIL_FROM", smtp_username or ""),
        "default_email_to": os.getenv("EMAIL_TO"),
        "subject": os.getenv("EMAIL_SUBJECT", "Relatório de Re-Treino de Modelo"),
    }


def _validate_smtp_config(config: dict) -> None:
    """Validate SMTP configuration completeness."""
    required_fields = ["server", "username", "password", "email_from"]
    if not all(config.get(field) for field in required_fields):
        raise RuntimeError("Configuração de SMTP incompleta. Verifique variáveis de ambiente.")


def _validate_pdf_attachment(pdf_path: str) -> Path:
    """Validate PDF attachment exists."""
    attachment_path = Path(pdf_path)
    if not attachment_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
    return attachment_path


def _get_recipient_email(to_email: Optional[str], smtp_config: dict) -> str:
    """Get recipient email address."""
    recipient = (to_email or smtp_config["default_email_to"] or smtp_config["email_from"]).strip()
    if not recipient:
        raise RuntimeError("Nenhum destinatário de e-mail configurado.")
    return recipient


def _create_email_message(
    report_data: TrainingReportData,
    smtp_config: dict,
    recipient: str,
    attachment_path: Path,
) -> EmailMessage:
    """Create email message with content and attachment."""
    metricas_formatadas = {
        chave: float(valor) for chave, valor in report_data.metricas.items()
    } if report_data.metricas else {}

    produto_nome = report_data.produto_nome or f"ID {report_data.produto_id}"
    corpo_email = _build_email_body(
        produto_nome=produto_nome,
        produto_id=report_data.produto_id,
        metricas=metricas_formatadas,
    )

    mensagem = EmailMessage()
    mensagem["Subject"] = smtp_config["subject"]
    mensagem["From"] = smtp_config["email_from"]
    mensagem["To"] = recipient
    mensagem.set_content(corpo_email)

    with attachment_path.open("rb") as arquivo_pdf:
        mensagem.add_attachment(
            arquivo_pdf.read(),
            maintype="application",
            subtype="pdf",
            filename=attachment_path.name,
        )

    return mensagem


def _send_email(message: EmailMessage, smtp_config: dict, report_data: TrainingReportData) -> None:
    """Send email via SMTP."""
    recipient = message["To"]
    attachment_name = None
    
    # Extract attachment name from message
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            attachment_name = part.get_filename()
            break
    
    LOGGER.info(
        "Enviando relatório de treinamento",
        extra={
            "produto_id": report_data.produto_id,
            "destinatario": recipient,
            "anexo_pdf": attachment_name,
        },
    )

    try:
        with smtplib.SMTP(host=smtp_config["server"], port=smtp_config["port"]) as smtp:
            smtp.starttls()
            smtp.login(user=smtp_config["username"], password=smtp_config["password"])
            smtp.send_message(message)
    except Exception:  # noqa: BLE001 - Propagate failure after logging
        LOGGER.exception("Falha ao enviar e-mail de relatório")
        raise

    metricas_formatadas = {
        chave: float(valor) for chave, valor in report_data.metricas.items()
    } if report_data.metricas else {}

    LOGGER.info(
        "E-mail enviado com sucesso",
        extra={
            "produto_id": report_data.produto_id,
            "destinatario": recipient,
            "metricas": metricas_formatadas,
        },
    )


def _build_email_body(*, produto_nome: str, produto_id: int, metricas: Mapping[str, float]) -> str:
    """Return the structured e-mail body requested by the business stakeholders."""

    data_geracao = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    linhas: list[str] = [
        "Prezados(as),",
        "",
        "Informamos que o modelo preditivo foi atualizado com sucesso.",
        "",
        "Resumo do re-treino:",
        f"• Produto: {produto_nome}",
        f"• ID do produto: {produto_id}",
        f"• Data do treino: {data_geracao}",
    ]

    if metricas:
        linhas.append("• Indicadores de desempenho:")
        for chave, valor in metricas.items():
            linhas.append(f"  ◦ {chave.upper()}: {valor:.2f}")
    else:
        linhas.append("• Indicadores de desempenho: Métricas não disponíveis nesta execução.")

    linhas.extend(
        [
            "• Próxima previsão disponível em anexo (PDF)",
            "",
            "Recomendações:",
            "1. Avaliem o impacto das novas projeções no planejamento de compras.",
            "2. Ajustem parâmetros de estoque mínimo caso necessário.",
            "",
            "Atenciosamente,",
            "Equipe de IA - Automação da Cadeia de Suprimentos",
        ]
    )

    return "\n".join(linhas)
