"""Analytics & ETL endpoints (employee-gated). Powered by Polars."""
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_role
from app.models.employee import Employee
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analítica"])


@router.get("/sales-summary")
async def sales_summary(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    top: int = 10,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    """Units sold and estimated revenue per product (from completed orders)."""
    return await analytics_service.sales_summary(db, start_date, end_date, top)


@router.post("/import-tier-prices")
async def import_tier_prices(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    """Bulk upsert tier prices from a CSV (columns: niu, tier, price)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    result = await analytics_service.import_tier_prices(db, content)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
