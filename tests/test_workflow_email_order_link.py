import pytest

pytest.importorskip("flask")

import services.email_admin_service as svc
from run import create_app


def test_resolve_workflow_email_uses_do_detail_url(monkeypatch):
    app = create_app()

    monkeypatch.setattr(
        svc.repo,
        "get_workflow_email_payload",
        lambda module_key, status_key: {
            "id": 1,
            "is_enabled": True,
            "subject_template": "Order {{do_number}}",
            "body_template": "Open {{order_link}}",
            "recipients": [
                {
                    "recipient_type": "EMAIL",
                    "recipient_value": "m.nizar@awgtc.com",
                    "is_cc": False,
                    "is_bcc": False,
                }
            ],
            "attachments": [],
            "include_default_attachment": False,
        },
    )

    order = {
        "id": 6027,
        "PO_Number": "AWTFZC/Apr/26/DO6027",
        "creator_first": "Admin",
    }

    with app.test_request_context("/", base_url="http://127.0.0.1:5080"):
        result = svc.resolve_workflow_email_for_do(
            order=order,
            new_status="CONFIRMED",
            creator_first_name="Admin",
            reject_reason=None,
            reject_remarks=None,
        )

    assert result is not None
    assert result["to"] == ["m.nizar@awgtc.com"]
    assert result["body"] == "Open http://127.0.0.1:5080/delivery-orders/6027"
