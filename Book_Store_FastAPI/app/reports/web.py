"""Reports — session web UI. Same Celery task as the JWT API, triggered from
an admin dashboard page instead of Postman/a mobile app."""

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from kombu.exceptions import OperationalError

from app.auth.dependencies import require_web_role
from app.auth.models import User
from app.core.celery_app import celery_app
from app.core.templating import render

from .tasks import generate_orders_report

router = APIRouter(prefix="/reports", tags=["web-reports"])
admin_role = require_web_role("admin")


@router.get("")
def index(request: Request, user: User = Depends(admin_role)):
    return render(request, "reports/index.html", {}, user=user)


@router.post("/orders/export")
def export_orders_report(user: User = Depends(admin_role)):
    try:
        task = generate_orders_report.delay()
    except OperationalError:
        return JSONResponse(
            {"state": "FAILURE", "error": "Redis/Celery isn't reachable."}, status_code=503
        )
    return JSONResponse({"task_id": task.id})


@router.get("/orders/export/{task_id}")
def export_orders_report_status(task_id: str, user: User = Depends(admin_role)):
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "SUCCESS":
        return JSONResponse({"state": "SUCCESS", **result.result})
    if result.state == "FAILURE":
        return JSONResponse({"state": "FAILURE", "error": str(result.result)})
    return JSONResponse({"state": result.state})
