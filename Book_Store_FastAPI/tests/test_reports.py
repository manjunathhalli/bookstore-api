"""Reports: the Celery-task-backed Excel export (Features: Celery, Pandas,
OpenPyXL). ``celery_app.conf.task_always_eager`` (set in conftest.py) makes
``.delay()`` run synchronously here — no Redis broker or separate worker
process required, so this test alone exercises the whole pipeline: enqueue ->
run the Pandas/OpenPyXL task -> poll the result -> a real .xlsx on disk.
"""

from pathlib import Path


def test_export_orders_report_end_to_end(client, admin_headers):
    enqueue = client.post("/api/reports/orders/export", headers=admin_headers)
    assert enqueue.status_code == 202
    task_id = enqueue.json()["task_id"]

    status = client.get(f"/api/reports/orders/export/{task_id}", headers=admin_headers)
    assert status.status_code == 200
    body = status.json()
    assert body["state"] == "SUCCESS"
    assert body["filename"].endswith(".xlsx")

    report_path = Path(__file__).resolve().parents[1] / "app" / "static" / body["download_url"].split("/static/")[1]
    assert report_path.exists()
    report_path.unlink()  # tests shouldn't leave files behind


def test_non_admin_cannot_export_report(client, user_headers):
    response = client.post("/api/reports/orders/export", headers=user_headers)
    assert response.status_code == 403
