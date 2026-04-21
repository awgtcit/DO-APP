from services import admin_settings_service as svc


def test_get_auth_users_prefers_local_emp_id(monkeypatch):
    svc.clear_auth_users_cache()

    monkeypatch.setattr(
        svc.repo,
        "get_all_users_full",
        lambda: [
            {
                "EmpID": 7001,
                "EmailAddress": "emp1@example.com",
                "CredEmail": None,
            }
        ],
    )

    def fake_get_app_users(app_id, page=1, per_page=500):
        return ([
            {
                "employee_id": "Emp1",
                "first_name": "Test",
                "last_name": "User",
                "email": "emp1@example.com",
            }
        ], 1)

    monkeypatch.setattr("sdk.auth_client.get_app_users", fake_get_app_users)

    users = svc.get_auth_users("demo-app")

    assert users[0]["emp_id"] == "7001"
    assert users[0]["local_emp_id"] == "7001"
    assert users[0]["auth_emp_id"] == "Emp1"


def test_resolve_or_create_local_emp_id_creates_shadow_user(monkeypatch):
    svc.clear_auth_users_cache()

    monkeypatch.setattr(svc, "get_auth_users", lambda app_id: [
        {
            "emp_id": "Emp9",
            "local_emp_id": None,
            "auth_emp_id": "Emp9",
            "first_name": "Shadow",
            "last_name": "User",
            "email": "shadow@example.com",
            "group_id": 10,
        }
    ])
    monkeypatch.setattr(svc.repo, "get_user_by_email", lambda email: None)
    monkeypatch.setattr(
        svc.repo,
        "ensure_auth_shadow_user",
        lambda first_name, last_name, email, group_id=10: 81234,
    )

    resolved = svc.resolve_or_create_local_emp_id(
        "demo-app",
        "Emp9",
        create_if_missing=True,
    )

    assert resolved == 81234
