"""Corporate SMTP service to distribute retraining reports."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Optional, Tuple

import structlog
from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.database import engine
from app.models.models import ModeloPredicao, Produto

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SMTPConfig:
    """Structured SMTP configuration retrieved from environment variables."""

    host: str
    port: int
    username: str
    password: str
    sender: str
    default_recipient: Optional[str]
    use_tls: bool = True


def send_training_report(to_email: str, produto_id: int, pdf_path: str) -> None:
    """Send the Prophet retraining report PDF to the configured corporate address."""

    try:
        config = _load_smtp_config()
    except RuntimeError as exc:
        LOGGER.warning("email.config.missing", error=str(exc), produto_id=produto_id)
        return

    recipient = to_email or config.default_recipient
    if not recipient:
        LOGGER.warning(
            "email.recipient.missing",
            produto_id=produto_id,
            destinatario_informado=to_email,
        )
        return

    attachment = _validate_pdf(pdf_path)
    produto_nome, metricas, treinado_em = _fetch_training_context(produto_id)

    subject = f"Relatório de Re-Treino de Modelo — Produto {produto_nome}"
    body = _render_email_body(
        produto_nome=produto_nome,
        treinado_em=treinado_em,
        metricas=metricas,
    )

    email_content = EmailContent(
        subject=subject,
        body=body,
        sender=config.sender,
        recipient=recipient,
        attachment_path=attachment,
    )
    message = _build_email_message(email_content)

    LOGGER.info(
        "email.report.preparing",
        produto_id=produto_id,
        destinatario=recipient,
        pdf=str(attachment),
        metricas=metricas,
    )

    try:
        _dispatch_email(config=config, message=message)
    except Exception as exc:  # noqa: BLE001 - surfacing generic SMTP issues
        LOGGER.error("email.report.failed", error=str(exc), produto_id=produto_id)
        raise

    LOGGER.info(
        "email.report.sent",
        produto_id=produto_id,
        destinatario=recipient,
        metricas=metricas,
    )


def send_bulk_training_report(
    *, to_email: Optional[str], pdf_path: str, total_treinados: int, total_ignorados: int
) -> None:
    """Send the consolidated training report covering the entire catalogue."""

    try:
        config = _load_smtp_config()
    except RuntimeError as exc:
        LOGGER.warning("email.bulk.config.missing", error=str(exc))
        return

    recipient = to_email or config.default_recipient
    if not recipient:
        LOGGER.warning(
            "email.bulk.recipient.missing",
            destinatario_informado=to_email,
        )
        return

    attachment = _validate_pdf(pdf_path)
    body = _render_bulk_email_body(
        total_treinados=total_treinados,
        total_ignorados=total_ignorados,
    )

    email_content = EmailContent(
        subject="Relatório de Re-Treino — Catálogo Completo",
        body=body,
        sender=config.sender,
        recipient=recipient,
        attachment_path=attachment,
    )
    message = _build_email_message(email_content)

    LOGGER.info(
        "email.bulk.preparing",
        destinatario=recipient,
        pdf=str(attachment),
        total_treinados=total_treinados,
        total_ignorados=total_ignorados,
    )

    try:
        _dispatch_email(config=config, message=message)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("email.bulk.failed", error=str(exc))
        raise

    LOGGER.info(
        "email.bulk.sent",
        destinatario=recipient,
        total_treinados=total_treinados,
        total_ignorados=total_ignorados,
    )


def _load_smtp_config() -> SMTPConfig:
    """Load SMTP credentials from environment variables and validate them."""

    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", username).strip()
    default_recipient = os.getenv("SMTP_DEFAULT_RECIPIENT")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:  # noqa: B904 - include context
        raise RuntimeError("Valor inválido para SMTP_PORT.") from exc

    required_fields = {
        "SMTP_HOST": host,
        "SMTP_USER": username,
        "SMTP_PASSWORD": password,
        "SMTP_FROM": sender,
    }
    missing_fields = [field for field, value in required_fields.items() if not value]
    if missing_fields:
        raise RuntimeError("Variáveis SMTP_HOST, SMTP_USER, SMTP_PASSWORD e SMTP_FROM são obrigatórias.")

    return SMTPConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        default_recipient=default_recipient.strip() if default_recipient else None,
        use_tls=use_tls,
    )


def _validate_pdf(pdf_path: str) -> Path:
    """Ensure the generated report exists before attempting to send it."""

    attachment = Path(pdf_path)
    if not attachment.is_file():
        raise FileNotFoundError(f"Relatório PDF não encontrado em {pdf_path}.")
    return attachment


def _fetch_training_context(produto_id: int) -> Tuple[str, Dict[str, float], datetime]:
    """Collect product metadata, metrics and training timestamp for the e-mail body."""

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            raise RuntimeError(f"Produto {produto_id} não encontrado para envio do relatório.")

        metadata = session.exec(
            select(ModeloPredicao)
            .where(ModeloPredicao.produto_id == produto_id)
            .order_by(ModeloPredicao.treinado_em.desc())
        ).first()

    metricas_raw = metadata.metricas if metadata and metadata.metricas else {}
    metricas = {chave: float(valor) for chave, valor in metricas_raw.items()}
    treino_em = metadata.treinado_em if metadata else datetime.now(timezone.utc)

    produto_nome = produto.nome or f"ID {produto.id}"

    return produto_nome, metricas, treino_em


def _render_email_body(*, produto_nome: str, treinado_em: datetime, metricas: Dict[str, float]) -> str:
    """Render the stakeholder-approved email body with dynamic data."""

    mse = metricas.get("mse")
    rmse = metricas.get("rmse")
    metricas_text = "N/D"
    if mse is not None or rmse is not None:
        metricas_text = " | ".join(
            [
                f"MSE: {mse:.4f}" if mse is not None else "MSE: N/D",
                f"RMSE: {rmse:.4f}" if rmse is not None else "RMSE: N/D",
            ]
        )

    data_treino = treinado_em.strftime("%d/%m/%Y %H:%M UTC")

    linhas = [
        "Prezados(as),",
        "",
        f"Informamos que o modelo preditivo para o produto {produto_nome} foi atualizado com sucesso.",
        "",
        f"• Produto: {produto_nome}",
        f"• Data do treino: {data_treino}",
        f"• Precisão (MSE/RMSE): {metricas_text}",
        "• Relatório detalhado em anexo (PDF)",
        "",
        "Atenciosamente,",
        "Equipe de IA - Automação da Cadeia de Suprimentos",
    ]

    return "\n".join(linhas)


def _render_bulk_email_body(*, total_treinados: int, total_ignorados: int) -> str:
    """Render the email body for the consolidated training report."""

    linhas = [
        "Prezados(as),",
        "",
        "O ciclo completo de re-treino dos modelos de previsão foi concluído com sucesso.",
        "",
        f"• Modelos treinados: {total_treinados}",
        f"• Produtos sem dados suficientes: {total_ignorados}",
        "• Relatório consolidado em anexo",
        "",
        "Atenciosamente,",
        "Equipe de IA - Automação da Cadeia de Suprimentos",
    ]

    return "\n".join(linhas)


@dataclass(frozen=True)
class EmailContent:
    """Encapsulates email message content and attachment information."""
    
    subject: str
    body: str
    sender: str
    recipient: str
    attachment_path: Path


def _build_email_message(email_content: EmailContent) -> EmailMessage:
    """Compose the MIME message with the PDF attachment."""

    message = EmailMessage()
    message["Subject"] = email_content.subject
    message["From"] = email_content.sender
    message["To"] = email_content.recipient
    message.set_content(email_content.body)

    with email_content.attachment_path.open("rb") as file_handle:
        message.add_attachment(
            file_handle.read(),
            maintype="application",
            subtype="pdf",
            filename=email_content.attachment_path.name,
        )

    return message

@retry(reraise=True, wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def _dispatch_email(*, config: SMTPConfig, message: EmailMessage) -> None:
    """Send the message using SMTP with exponential backoff on failure."""

    with smtplib.SMTP(host=config.host, port=config.port, timeout=30) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(user=config.username, password=config.password)
        smtp.send_message(message)


__all__ = ["send_training_report", "send_bulk_training_report"]
