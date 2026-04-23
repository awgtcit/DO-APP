import pytest

pytest.importorskip("flask")
from flask import Flask, session

import services.delivery_order_service as svc


class _Capture:
    def __init__(self):
        self.status = None
        self.history_payload = None


def _setup_common(monkeypatch, capture, order, items, latest_reject=None):
    monkeypatch.setattr(svc, "get_order_by_id", lambda _order_id: dict(order))
    monkeypatch.setattr(svc, "get_order_items", lambda _po: list(items))
    monkeypatch.setattr(svc, "_get_status_flow", lambda: {"DRAFT": ["SUBMITTED"]})
    monkeypatch.setattr(svc, "can_transition", lambda _order, _new_status: True)
    monkeypatch.setattr(svc, "validate_order_for_submit", lambda _order: [])
    monkeypatch.setattr(svc, "send_do_status_email", lambda **kwargs: None)
    monkeypatch.setattr(svc, "get_do_role", lambda: svc.DO_ROLE_CREATOR)
    monkeypatch.setattr(svc, "get_latest_rejection_status_history", lambda _id: latest_reject)

    def _update_status(_order_id, new_status, _emp_id):
        capture.status = new_status
        return True

    monkeypatch.setattr(svc, "update_order_status", _update_status)
    monkeypatch.setattr(svc, "update_order_status_with_reason", lambda *args, **kwargs: True)

    def _add_history(payload):
        capture.history_payload = payload
        return 1

    monkeypatch.setattr(svc, "add_order_status_history", _add_history)


def test_resubmit_after_finance_reject_goes_to_finance(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"

    order = {
        "id": 10,
        "Status": "DRAFT",
        "PO_Number": "PO-10",
        "Created_by": 100,
        "creator_email": "creator@example.com",
        "bill_to_ownership_sole_prop": "No",
        "ship_to_ownership_sole_prop": "No",
    }
    items = [{"Product_ID": "P1", "Quantity": 10, "Unit_Price": 5, "Currency": "USD", "Total_Amount": 50}]

    latest_reject = {
        "to_status": "REJECTED",
        "actor_role": svc.DO_ROLE_FINANCE,
        "price_signature": "sig-prev",
    }

    capture = _Capture()
    _setup_common(monkeypatch, capture, order, items, latest_reject=latest_reject)

    with app.test_request_context("/"):
        session["emp_id"] = 100
        session["first_name"] = "Jane"
        session["last_name"] = "Creator"
        session["email"] = "jane@example.com"

        ok, errors, actual = svc.change_order_status(10, "SUBMITTED", 100)

    assert ok is True
    assert errors == []
    assert actual == "SUBMITTED"
    assert capture.status == "SUBMITTED"
    assert capture.history_payload is not None
    assert capture.history_payload["action_type"] == "SUBMITTED"


def test_resubmit_after_logistics_reject_without_price_change_goes_direct_logistics(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"

    order = {
        "id": 11,
        "Status": "DRAFT",
        "PO_Number": "PO-11",
        "Created_by": 101,
        "creator_email": "creator@example.com",
        "bill_to_ownership_sole_prop": "No",
        "ship_to_ownership_sole_prop": "No",
    }
    items = [{"Product_ID": "P2", "Quantity": 3, "Unit_Price": 12, "Currency": "USD", "Total_Amount": 36}]

    # Compute deterministic current signature from controlled items.
    monkeypatch.setattr(svc, "get_order_items", lambda _po: list(items))
    current_sig, _ = svc._build_price_signature(order)

    latest_reject = {
        "to_status": "REJECTED",
        "actor_role": svc.DO_ROLE_LOGISTICS,
        "price_signature": current_sig,
    }

    capture = _Capture()
    _setup_common(monkeypatch, capture, order, items, latest_reject=latest_reject)

    with app.test_request_context("/"):
        session["emp_id"] = 101
        session["first_name"] = "Sam"
        session["last_name"] = "Creator"
        session["email"] = "sam@example.com"

        ok, errors, actual = svc.change_order_status(11, "SUBMITTED", 101)

    assert ok is True
    assert errors == []
    assert actual == "PRICE AGREED"
    assert capture.status == "PRICE AGREED"
    assert "Logistics" in (capture.history_payload.get("remarks") or "")


def test_resubmit_after_logistics_reject_with_price_change_returns_finance(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"

    order = {
        "id": 12,
        "Status": "DRAFT",
        "PO_Number": "PO-12",
        "Created_by": 102,
        "creator_email": "creator@example.com",
        "bill_to_ownership_sole_prop": "No",
        "ship_to_ownership_sole_prop": "No",
    }
    items = [{"Product_ID": "P3", "Quantity": 7, "Unit_Price": 20, "Currency": "USD", "Total_Amount": 140}]

    latest_reject = {
        "to_status": "REJECTED",
        "actor_role": svc.DO_ROLE_LOGISTICS,
        "price_signature": "old-signature",
    }

    capture = _Capture()
    _setup_common(monkeypatch, capture, order, items, latest_reject=latest_reject)

    with app.test_request_context("/"):
        session["emp_id"] = 102
        session["first_name"] = "Alex"
        session["last_name"] = "Creator"
        session["email"] = "alex@example.com"

        ok, errors, actual = svc.change_order_status(12, "SUBMITTED", 102)

    assert ok is True
    assert errors == []
    assert actual == "SUBMITTED"
    assert capture.status == "SUBMITTED"
    assert "pricing changed" in (capture.history_payload.get("remarks") or "").lower()
