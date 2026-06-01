"""Email ingestion and AI classification.

Uses the Anthropic Claude API to classify incoming customer emails: category,
summary, priority and which configured client they belong to. Gmail sync is
implemented against the Gmail API but degrades gracefully when no OAuth
credentials are configured (returns an empty sync result).
"""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_model import EmailClient, EmailMessage, EmailPriority
from app.schemas.email_schema import EmailSyncResponse

CLASSIFY_MODEL = "claude-sonnet-4-6"

CLASSIFY_SYSTEM = (
    "Eres un asistente de una empresa de distribución y almacén. Clasificas "
    "correos entrantes de clientes y proveedores. Respondes SIEMPRE en JSON "
    "válido, sin texto adicional."
)


def _build_classify_prompt(subject: str, body: str, from_email: str, clients: list[dict]) -> str:
    client_lines = "\n".join(
        f"- id={c['id']} | {c['customer_name']} <{c['customer_email']}>"
        for c in clients
    ) or "(sin clientes configurados)"
    return f"""Clasifica el siguiente correo.

Clientes conocidos:
{client_lines}

Correo:
- De: {from_email}
- Asunto: {subject}
- Cuerpo: {body[:2000]}

Devuelve un JSON con exactamente estas claves:
{{
  "category": "pedido|incidencia|factura|consulta|devolucion|reclamacion|spam|otro",
  "summary": "resumen en una frase (máx 140 caracteres)",
  "priority": "HIGH|MEDIUM|LOW",
  "matched_customer_id": <id del cliente que coincide o null>
}}"""


class EmailService:
    def __init__(self, anthropic_api_key: str | None = None):
        self.anthropic_api_key = anthropic_api_key or settings.ANTHROPIC_API_KEY

    # ---- AI classification -------------------------------------------------
    async def classify_email(
        self,
        subject: str,
        body: str,
        from_email: str,
        client_list: list[dict],
    ) -> dict:
        """Classify an email via Claude. Falls back to a heuristic if no key."""
        if not self.anthropic_api_key:
            return self._heuristic_classify(subject, body, from_email, client_list)

        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.anthropic_api_key)
            message = await client.messages.create(
                model=CLASSIFY_MODEL,
                max_tokens=500,
                system=CLASSIFY_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": _build_classify_prompt(
                            subject, body, from_email, client_list
                        ),
                    }
                ],
            )
            text = "".join(
                block.text for block in message.content if hasattr(block, "text")
            ).strip()
            # Strip code fences if the model added them.
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            matched_id = data.get("matched_customer_id")
            matched_name = None
            if matched_id is not None:
                for c in client_list:
                    if c["id"] == matched_id:
                        matched_name = c["customer_name"]
                        break
            return {
                "category": data.get("category", "otro"),
                "summary": data.get("summary", ""),
                "priority": data.get("priority", "MEDIUM"),
                "matched_customer_id": matched_id,
                "matched_customer_name": matched_name,
            }
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            fallback = self._heuristic_classify(subject, body, from_email, client_list)
            fallback["summary"] = fallback["summary"] or f"(IA no disponible: {exc})"
            return fallback

    def _heuristic_classify(
        self, subject: str, body: str, from_email: str, client_list: list[dict]
    ) -> dict:
        """Keyword-based fallback when the AI key is unavailable."""
        text = f"{subject} {body}".lower()
        category = "otro"
        priority = "MEDIUM"
        # Urgent categories are checked first so they win over generic keywords.
        if any(k in text for k in ("reclamación", "reclamacion", "queja")):
            category = "reclamacion"
            priority = "HIGH"
        elif any(k in text for k in ("incidencia", "problema", "rotura", "roto", "rota", "dañad", "averi")):
            category = "incidencia"
            priority = "HIGH"
        elif any(k in text for k in ("devolución", "devolucion", "return")):
            category = "devolucion"
        elif any(k in text for k in ("factura", "invoice", "pago", "abono")):
            category = "factura"
        elif any(k in text for k in ("pedido", "order", "compra", "encargo")):
            category = "pedido"
        # "urgente" raises priority regardless of category.
        if "urgente" in text and priority != "HIGH":
            priority = "HIGH"

        matched_id = None
        matched_name = None
        sender = from_email.lower().strip()
        for c in client_list:
            if c["customer_email"].lower() == sender:
                matched_id = c["id"]
                matched_name = c["customer_name"]
                break

        return {
            "category": category,
            "summary": subject[:140] if subject else "(sin asunto)",
            "priority": priority,
            "matched_customer_id": matched_id,
            "matched_customer_name": matched_name,
        }

    # ---- Gmail sync --------------------------------------------------------
    async def sync_gmail(self, db: AsyncSession, credentials=None) -> EmailSyncResponse:
        """Fetch unread Gmail messages, classify and store them.

        Requires OAuth credentials. When unavailable, returns an empty result
        with an explanatory error so the UI can prompt the user to connect.
        """
        if credentials is None:
            return EmailSyncResponse(
                synced_count=0,
                classified_count=0,
                errors=["Gmail no conectado: faltan credenciales OAuth."],
            )

        synced = 0
        classified = 0
        errors: list[str] = []
        try:
            from googleapiclient.discovery import build

            service = build("gmail", "v1", credentials=credentials)
            listing = (
                service.users()
                .messages()
                .list(userId="me", q="is:unread", maxResults=25)
                .execute()
            )
            clients = await self._client_dicts(db)
            for ref in listing.get("messages", []):
                gmail_id = ref["id"]
                existing = await db.execute(
                    select(EmailMessage).where(
                        EmailMessage.gmail_message_id == gmail_id
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                full = (
                    service.users()
                    .messages()
                    .get(userId="me", id=gmail_id, format="full")
                    .execute()
                )
                headers = {
                    h["name"].lower(): h["value"]
                    for h in full.get("payload", {}).get("headers", [])
                }
                subject = headers.get("subject", "")
                from_email = headers.get("from", "")
                snippet = full.get("snippet", "")

                ai = await self.classify_email(subject, snippet, from_email, clients)
                msg = EmailMessage(
                    gmail_message_id=gmail_id,
                    from_email=from_email,
                    to_email=headers.get("to"),
                    subject=subject,
                    body_preview=snippet,
                    received_at=datetime.now(timezone.utc),
                    ai_category=ai["category"],
                    ai_summary=ai["summary"],
                    ai_priority=EmailPriority(ai["priority"]),
                    customer_id=ai.get("matched_customer_id"),
                )
                if ai.get("matched_customer_id"):
                    client = await db.get(EmailClient, ai["matched_customer_id"])
                    if client and client.folder_name:
                        msg.folder_assigned = client.folder_name
                db.add(msg)
                synced += 1
                classified += 1
            await db.flush()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Error sincronizando Gmail: {exc}")

        return EmailSyncResponse(
            synced_count=synced, classified_count=classified, errors=errors
        )

    async def _client_dicts(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(EmailClient).where(EmailClient.is_active.is_(True))
        )
        return [
            {
                "id": c.id,
                "customer_name": c.customer_name,
                "customer_email": c.customer_email,
                "folder_name": c.folder_name,
            }
            for c in result.scalars().all()
        ]

    # ---- Office notification ----------------------------------------------
    async def notify_office(
        self, message_id: int, staff_emails: list[str], db: AsyncSession
    ) -> bool:
        """Mark a message as notified to office staff.

        Sending the actual notification email is left to the SMTP/Gmail layer;
        here we record who was notified and when so the UI reflects it.
        """
        msg = await db.get(EmailMessage, message_id)
        if msg is None:
            return False
        msg.is_notified = True
        msg.office_notified_at = datetime.now(timezone.utc)
        msg.office_notified_to = ", ".join(staff_emails)
        await db.flush()
        return True
