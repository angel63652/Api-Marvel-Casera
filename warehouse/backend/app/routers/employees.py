from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone, date

from app.database import get_db
from app.models.employee import (
    Employee,
    Payroll,
    CalendarEvent,
    PayrollStatus,
    CalendarEventType,
)
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    PayrollCreate,
    PayrollResponse,
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
    LoginRequest,
    TokenResponse,
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_employee,
    require_role,
)

router = APIRouter(prefix="/employees", tags=["Empleados"])

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _emp_resp(e: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=e.id,
        employee_number=e.employee_number,
        name=e.name,
        surname=e.surname,
        full_name=f"{e.name} {e.surname}",
        dni=e.dni,
        email=e.email,
        phone=e.phone,
        position=e.position,
        department=e.department,
        hire_date=e.hire_date,
        salary_base=e.salary_base,
        is_active=e.is_active,
        is_driver=e.is_driver,
        role=e.role,
        created_at=e.created_at,
    )


def _payroll_resp(p: Payroll) -> PayrollResponse:
    return PayrollResponse(
        id=p.id,
        employee_id=p.employee_id,
        employee_name=(
            f"{p.employee.name} {p.employee.surname}" if p.employee else None
        ),
        year=p.year,
        month=p.month,
        month_name=MONTH_NAMES[p.month] if 1 <= p.month <= 12 else None,
        salary_base=p.salary_base,
        bonuses=p.bonuses,
        deductions=p.deductions,
        net_salary=p.net_salary,
        paid_at=p.paid_at,
        paid_by=p.paid_by,
        notes=p.notes,
        status=p.status,
        created_at=p.created_at,
    )


# ---- Auth ------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.email == payload.email))
    employee = result.scalar_one_or_none()
    if employee is None or not verify_password(payload.password, employee.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not employee.is_active:
        raise HTTPException(status_code=403, detail="Empleado inactivo")
    role = employee.role.value if hasattr(employee.role, "value") else employee.role
    token = create_access_token({"sub": str(employee.id), "role": role})
    return TokenResponse(
        access_token=token, token_type="bearer", employee=_emp_resp(employee)
    )


@router.get("/me", response_model=EmployeeResponse)
async def get_me(current: Employee = Depends(get_current_employee)):
    return _emp_resp(current)


# ---- Calendar (declared before /{employee_id}) ----------------------------
@router.get("/calendar", response_model=list[CalendarEventResponse])
async def list_calendar(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    type: Optional[CalendarEventType] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CalendarEvent)
    if start_date:
        stmt = stmt.where(CalendarEvent.date >= start_date)
    if end_date:
        stmt = stmt.where(CalendarEvent.date <= end_date)
    if type:
        stmt = stmt.where(CalendarEvent.type == type)
    stmt = stmt.order_by(CalendarEvent.date, CalendarEvent.time)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/calendar", response_model=CalendarEventResponse, status_code=201)
async def create_calendar_event(
    payload: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    event = CalendarEvent(**payload.model_dump())
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


@router.put("/calendar/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: int,
    payload: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    event = await db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.flush()
    await db.refresh(event)
    return event


@router.delete("/calendar/{event_id}")
async def delete_calendar_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    event = await db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    await db.delete(event)
    return {"detail": "Evento eliminado"}


# ---- Payroll reporting (declared before /{employee_id}) --------------------
@router.get("/payrolls/report/{year}/{month}", response_model=list[PayrollResponse])
async def payroll_report(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    stmt = select(Payroll).where(Payroll.year == year, Payroll.month == month)
    result = await db.execute(stmt)
    return [_payroll_resp(p) for p in result.scalars().all()]


@router.put("/payrolls/{payroll_id}/pay", response_model=PayrollResponse)
async def pay_payroll(
    payroll_id: int,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER")),
):
    p = await db.get(Payroll, payroll_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Nómina no encontrada")
    p.status = PayrollStatus.PAID
    p.paid_at = datetime.now(timezone.utc)
    p.paid_by = current.id
    await db.flush()
    await db.refresh(p)
    return _payroll_resp(p)


# ---- Employees -------------------------------------------------------------
@router.get("", response_model=list[EmployeeResponse])
async def list_employees(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    stmt = select(Employee)
    if active_only:
        stmt = stmt.where(Employee.is_active.is_(True))
    stmt = stmt.order_by(Employee.surname, Employee.name)
    result = await db.execute(stmt)
    return [_emp_resp(e) for e in result.scalars().all()]


@router.post("", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("ADMIN")),
):
    existing = await db.execute(
        select(Employee).where(Employee.email == payload.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe un empleado con ese email")
    data = payload.model_dump(exclude={"password"})
    employee = Employee(**data, hashed_password=hash_password(payload.password))
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    return _emp_resp(employee)


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return _emp_resp(employee)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    role = current.role.value if hasattr(current.role, "value") else current.role
    is_self = current.id == employee_id
    if role not in ("ADMIN", "MANAGER") and not is_self:
        raise HTTPException(status_code=403, detail="No autorizado")

    data = payload.model_dump(exclude_unset=True)
    # Only ADMIN/MANAGER may change sensitive fields.
    if role not in ("ADMIN", "MANAGER"):
        for sensitive in ("role", "salary_base", "is_active"):
            data.pop(sensitive, None)

    if "password" in data and data["password"]:
        employee.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)

    for field, value in data.items():
        setattr(employee, field, value)
    await db.flush()
    await db.refresh(employee)
    return _emp_resp(employee)


@router.get("/{employee_id}/payrolls", response_model=list[PayrollResponse])
async def employee_payrolls(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    stmt = (
        select(Payroll)
        .where(Payroll.employee_id == employee_id)
        .order_by(Payroll.year.desc(), Payroll.month.desc())
    )
    result = await db.execute(stmt)
    return [_payroll_resp(p) for p in result.scalars().all()]


@router.post("/{employee_id}/payrolls", response_model=PayrollResponse, status_code=201)
async def create_payroll(
    employee_id: int,
    payload: PayrollCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    existing = await db.execute(
        select(Payroll).where(
            Payroll.employee_id == employee_id,
            Payroll.year == payload.year,
            Payroll.month == payload.month,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400, detail="Ya existe una nómina para ese período"
        )

    net = (payload.salary_base or employee.salary_base) + payload.bonuses - payload.deductions
    payroll = Payroll(
        employee_id=employee_id,
        year=payload.year,
        month=payload.month,
        salary_base=payload.salary_base or employee.salary_base,
        bonuses=payload.bonuses,
        deductions=payload.deductions,
        net_salary=net,
        notes=payload.notes,
        status=PayrollStatus.PENDING,
    )
    db.add(payroll)
    await db.flush()
    await db.refresh(payroll)
    return _payroll_resp(payroll)
