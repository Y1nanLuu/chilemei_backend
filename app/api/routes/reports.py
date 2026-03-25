from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.report import AnnualReportResponse
from app.services.report import generate_annual_report

router = APIRouter()


@router.get('/annual/{year}', response_model=AnnualReportResponse)
def get_annual_report(
    year: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnnualReportResponse:
    return generate_annual_report(db, current_user.id, year)
