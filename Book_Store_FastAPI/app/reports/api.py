"""Reports API — admin-only. Kicks off the Celery report task and lets the
client poll for its result (Features: Celery, Pandas, OpenPyXL)."""

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from kombu.exceptions import OperationalError

from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.core.celery_app import celery_app

from .tasks import generate_orders_report

router = APIRouter(prefix="/reports", tags=["reports"])
admin_role = require_api_role("admin")


@router.post("/orders/export", status_code=202)
def export_orders_report(_: User = Depends(admin_role)):
    """Enqueue the report and return immediately — 202 Accepted, not 201/200,
    because the work isn't done yet, only scheduled."""
    try:
        task = generate_orders_report.delay()
    except OperationalError as exc:
        # Redis (the broker) is unreachable — a very different failure from
        # "the report failed to build", so it gets its own status code rather
        # than a generic 500.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Report generation is unavailable — Redis/Celery isn't reachable.",
        ) from exc
    return {"status": 202, "task_id": task.id}


@router.get("/orders/export/{task_id}")
def export_orders_report_status(task_id: str, _: User = Depends(admin_role)):
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "PENDING":
        return {"status": 200, "state": "PENDING"}
    if result.state == "FAILURE":
        return {"status": 200, "state": "FAILURE", "error": str(result.result)}
    if result.state == "SUCCESS":
        return {"status": 200, "state": "SUCCESS", **result.result}
    return {"status": 200, "state": result.state}
