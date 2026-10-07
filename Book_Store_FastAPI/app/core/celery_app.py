"""The shared Celery application (Feature: Celery background jobs).

FastAPI handles a request and must answer quickly; anything slow (building an
Excel report from thousands of rows with Pandas) is handed off to a separate
**worker process** instead of blocking the request. This module wires that
worker up:

* ``broker``  — where FastAPI *drops off* a task description. We reuse Redis.
* ``backend`` — where the worker *writes the result* so FastAPI can poll it.

Run the worker (a second process, alongside ``python run.py``) with::

    celery -A app.core.celery_app worker --loglevel=info --pool=solo

(``--pool=solo`` is required on Windows; Celery's default prefork pool needs
``fork()``, which Windows doesn't have.)
"""

from __future__ import annotations

from celery import Celery

from .config import settings

celery_app = Celery(
    "book_store",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.reports.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Keep results around long enough for the client to poll and download.
    result_expires=60 * 60,
)
