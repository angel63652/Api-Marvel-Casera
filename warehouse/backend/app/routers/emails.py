from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.config import settings
from app.models.email_model import EmailClient, EmailMessage, EmailPriority
from app.models.employee import Employee
from app.schemas.email_schema import (
    EmailClientCreate,
    EmailClientUpdate,
    EmailClientResponse,
    EmailMessageResponse,
    EmailFilterRequest,
    EmailFilterResponse,
    NotifyOfficeRequest,
    EmailSyncResponse,
)
from app.auth import require_role, get_current_employee
from app.services.email_service import EmailService

router = APIRouter(prefix="/emails", tags=["Correos"])

email_service = EmailService(anthropic_api_key=settings.ANTHROPIC_API_KEY)


def _client_resp(c: EmailClient) -> EmailClientResponse:
    return EmailClientResponse(
        id=c.id,
        customer_name=c.customer_name,
        customer_email=c.customer_email,
        folder_name=c.folder_name,
        gmail_label=c.gmail_label,
        is_active=c.is_active,
        auto_filter=c.auto_filter,
        ai_category=c.ai_category,
        created_at=c.created_at,
        message_count=len(c.messages) if c.messages is not None else 0,
    )


def _msg_resp(m: EmailMessage) -> EmailMessageResponse:
    return EmailMessageResponse(
        id=m.id,
        gmail_message_id=m.gmail_message_id,
        from_email=m.from_email,
        to_email=m.to_email,
        subject=m.subject,
        body_preview=m.body_preview,
        received_at=m.received_at,
        ai_category=m.ai_category,
        ai_summary=m.ai_summary,
        ai_priority=m.ai_priority,
        customer_id=m.customer_id,
        folder_assigned=m.folder_assigned,
        is_read=m.is_read,
        is_notified=m.is_notified,
        office_notified_at=m.office_notified_at,
        customer_name=m.email_client.customer_name if m.email_client else None,
    )


# ---- Client configuration --------------------------------------------------
@router.get("/clients", response_model=list[EmailClientResponse])
async def list_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailClient).order_by(EmailClient.customer_name))
    return [_client_resp(c) for c in result.scalars().all()]


@router.post("/clients", response_model=EmailClientResponse, status_code=201)
async def create_client(
    payload: EmailClientCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    existing = await db.execute(
        select(EmailClient).where(EmailClient.customer_email == payload.customer_email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe un cliente con ese email")
    client = EmailClient(**payload.model_dump())
    if not client.folder_name:
        client.folder_name = payload.customer_name
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return _client_resp(client)


@router.put("/clients/{client_id}", response_model=EmailClientResponse)
async def update_client(
    client_id: int,
    payload: EmailClientUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    client = await db.get(EmailClient, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    await db.flush()
    await db.refresh(client)
    return _client_resp(client)


# ---- Messages --------------------------------------------------------------
@router.get("/messages", response_model=list[EmailMessageResponse])
async def list_messages(
    folder: Optional[str] = None,
    priority: Optional[EmailPriority] = None,
    is_read: Optional[bool] = None,
    customer_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(EmailMessage)
    if folder:
        stmt = stmt.where(EmailMessage.folder_assigned == folder)
    if priority:
        stmt = stmt.where(EmailMessage.ai_priority == priority)
    if is_read is not None:
        stmt = stmt.where(EmailMessage.is_read.is_(is_read))
    if customer_id:
        stmt = stmt.where(EmailMessage.customer_id == customer_id)
    stmt = stmt.order_by(EmailMessage.received_at.desc().nullslast())
    result = await db.execute(stmt)
    return [_msg_resp(m) for m in result.scalars().all()]


@router.get("/messages/{message_id}", response_model=EmailMessageResponse)
async def get_message(message_id: int, db: AsyncSession = Depends(get_db)):
    msg = await db.get(EmailMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return _msg_resp(msg)


@router.post("/messages/{message_id}/read", response_model=EmailMessageResponse)
async def mark_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    msg = await db.get(EmailMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    msg.is_read = True
    await db.flush()
    await db.refresh(msg)
    return _msg_resp(msg)


@router.post("/messages/{message_id}/notify", response_model=EmailMessageResponse)
async def notify_office(
    message_id: int,
    payload: NotifyOfficeRequest,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    ok = await email_service.notify_office(message_id, payload.staff_emails, db)
    if not ok:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    msg = await db.get(EmailMessage, message_id)
    return _msg_resp(msg)


# ---- AI filtering & Gmail sync --------------------------------------------
@router.post("/filter", response_model=EmailFilterResponse)
async def filter_email(
    payload: EmailFilterRequest,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    result = await db.execute(
        select(EmailClient).where(EmailClient.is_active.is_(True))
    )
    clients = [
        {
            "id": c.id,
            "customer_name": c.customer_name,
            "customer_email": c.customer_email,
            "folder_name": c.folder_name,
        }
        for c in result.scalars().all()
    ]
    ai = await email_service.classify_email(
        payload.subject, payload.body, payload.from_email, clients
    )
    suggested_folder = None
    if ai.get("matched_customer_id"):
        for c in clients:
            if c["id"] == ai["matched_customer_id"]:
                suggested_folder = c["folder_name"]
                break
    return EmailFilterResponse(
        category=ai["category"],
        summary=ai["summary"],
        priority=ai["priority"],
        matched_customer_id=ai.get("matched_customer_id"),
        matched_customer_name=ai.get("matched_customer_name"),
        suggested_folder=suggested_folder,
    )


@router.post("/sync", response_model=EmailSyncResponse)
async def sync_gmail(
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    # Gmail OAuth credentials are wired in once the user connects an account.
    return await email_service.sync_gmail(db, credentials=None)
