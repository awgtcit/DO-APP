"""Repository for SMTP and workflow email configuration."""

import json

from db.transaction import read_only, transactional


_SCHEMA_READY = False


# ── helpers ─────────────────────────────────────────────────────

def _row_to_dict(cursor, row) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _rows_to_list(cursor, rows) -> list[dict]:
    return [_row_to_dict(cursor, r) for r in rows]


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _index_exists(cursor, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM sys.indexes
        WHERE object_id = OBJECT_ID(?)
          AND name = ?
        """,
        (table_name, index_name),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def ensure_email_schema() -> None:
    """Create email-config tables/indexes if they do not exist yet."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with transactional() as (conn, cursor):
        if not _table_exists(cursor, "Intra_Admin_SMTPConfig"):
            cursor.execute(
                """
                CREATE TABLE Intra_Admin_SMTPConfig (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    smtp_host NVARCHAR(255) NOT NULL,
                    smtp_port INT NOT NULL DEFAULT 587,
                    smtp_username NVARCHAR(255) NOT NULL,
                    smtp_password_encrypted NVARCHAR(MAX) NOT NULL,
                    sender_email NVARCHAR(255) NOT NULL,
                    sender_name NVARCHAR(255) NULL,
                    confirmation_subject NVARCHAR(500) NULL,
                    confirmation_body NVARCHAR(MAX) NULL,
                    use_tls BIT NOT NULL DEFAULT 1,
                    use_ssl BIT NOT NULL DEFAULT 0,
                    is_active BIT NOT NULL DEFAULT 1,
                    last_test_status NVARCHAR(50) NULL,
                    last_test_message NVARCHAR(2000) NULL,
                    last_tested_on DATETIME NULL,
                    created_on DATETIME NOT NULL DEFAULT GETDATE(),
                    created_by INT NOT NULL DEFAULT 0,
                    modified_on DATETIME NOT NULL DEFAULT GETDATE(),
                    modified_by INT NOT NULL DEFAULT 0
                )
                """
            )
        else:
            if not _column_exists(cursor, "Intra_Admin_SMTPConfig", "confirmation_subject"):
                cursor.execute("ALTER TABLE Intra_Admin_SMTPConfig ADD confirmation_subject NVARCHAR(500) NULL")
            if not _column_exists(cursor, "Intra_Admin_SMTPConfig", "confirmation_body"):
                cursor.execute("ALTER TABLE Intra_Admin_SMTPConfig ADD confirmation_body NVARCHAR(MAX) NULL")

        if not _table_exists(cursor, "Intra_Admin_WorkflowEmailSettings"):
            cursor.execute(
                """
                CREATE TABLE Intra_Admin_WorkflowEmailSettings (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    module_key NVARCHAR(120) NOT NULL,
                    status_key NVARCHAR(120) NOT NULL,
                    is_enabled BIT NOT NULL DEFAULT 1,
                    subject_template NVARCHAR(500) NOT NULL,
                    body_template NVARCHAR(MAX) NOT NULL,
                    include_default_attachment BIT NOT NULL DEFAULT 1,
                    created_on DATETIME NOT NULL DEFAULT GETDATE(),
                    created_by INT NOT NULL DEFAULT 0,
                    modified_on DATETIME NOT NULL DEFAULT GETDATE(),
                    modified_by INT NOT NULL DEFAULT 0,
                    CONSTRAINT UQ_WorkflowEmailStatus UNIQUE (module_key, status_key)
                )
                """
            )

        if not _table_exists(cursor, "Intra_Admin_WorkflowEmailRecipient"):
            cursor.execute(
                """
                CREATE TABLE Intra_Admin_WorkflowEmailRecipient (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    setting_id INT NOT NULL,
                    recipient_type NVARCHAR(40) NOT NULL,
                    recipient_value NVARCHAR(500) NOT NULL,
                    is_cc BIT NOT NULL DEFAULT 0,
                    is_bcc BIT NOT NULL DEFAULT 0,
                    created_on DATETIME NOT NULL DEFAULT GETDATE(),
                    created_by INT NOT NULL DEFAULT 0,
                    CONSTRAINT FK_WorkflowEmailRecipient_Setting
                        FOREIGN KEY (setting_id)
                        REFERENCES Intra_Admin_WorkflowEmailSettings(id)
                        ON DELETE CASCADE
                )
                """
            )

        if not _table_exists(cursor, "Intra_Admin_WorkflowEmailAttachment"):
            cursor.execute(
                """
                CREATE TABLE Intra_Admin_WorkflowEmailAttachment (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    setting_id INT NOT NULL,
                    file_name NVARCHAR(255) NOT NULL,
                    original_name NVARCHAR(255) NOT NULL,
                    storage_path NVARCHAR(700) NOT NULL,
                    mime_type NVARCHAR(120) NULL,
                    is_editable BIT NOT NULL DEFAULT 0,
                    is_active BIT NOT NULL DEFAULT 1,
                    created_on DATETIME NOT NULL DEFAULT GETDATE(),
                    created_by INT NOT NULL DEFAULT 0,
                    CONSTRAINT FK_WorkflowEmailAttachment_Setting
                        FOREIGN KEY (setting_id)
                        REFERENCES Intra_Admin_WorkflowEmailSettings(id)
                        ON DELETE CASCADE
                )
                """
            )

        if not _index_exists(cursor, "Intra_Admin_WorkflowEmailSettings", "IX_WorkflowEmailSettings_ModuleStatus"):
            cursor.execute(
                "CREATE INDEX IX_WorkflowEmailSettings_ModuleStatus "
                "ON Intra_Admin_WorkflowEmailSettings (module_key, status_key)"
            )

        if not _index_exists(cursor, "Intra_Admin_WorkflowEmailRecipient", "IX_WorkflowEmailRecipient_Setting"):
            cursor.execute(
                "CREATE INDEX IX_WorkflowEmailRecipient_Setting "
                "ON Intra_Admin_WorkflowEmailRecipient (setting_id)"
            )

        if not _index_exists(cursor, "Intra_Admin_WorkflowEmailAttachment", "IX_WorkflowEmailAttachment_Setting"):
            cursor.execute(
                "CREATE INDEX IX_WorkflowEmailAttachment_Setting "
                "ON Intra_Admin_WorkflowEmailAttachment (setting_id, is_active)"
            )

    _SCHEMA_READY = True


# ── smtp config ─────────────────────────────────────────────────

def get_active_smtp_config() -> dict | None:
    ensure_email_schema()
    sql = """
        SELECT TOP 1 *
        FROM Intra_Admin_SMTPConfig
        WHERE is_active = 1
        ORDER BY modified_on DESC, id DESC
    """
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def get_smtp_configs() -> list[dict]:
    ensure_email_schema()
    sql = "SELECT * FROM Intra_Admin_SMTPConfig ORDER BY modified_on DESC, id DESC"
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


def save_smtp_config(data: dict, actor_emp_id: int) -> int:
    ensure_email_schema()
    config_id = int(data.get("id") or 0)
    with transactional() as (conn, cursor):
        if data.get("is_active"):
            cursor.execute("UPDATE Intra_Admin_SMTPConfig SET is_active = 0")

        if config_id:
            cursor.execute(
                """
                UPDATE Intra_Admin_SMTPConfig
                SET smtp_host = ?, smtp_port = ?, smtp_username = ?,
                    smtp_password_encrypted = ?, sender_email = ?, sender_name = ?,
                    confirmation_subject = ?, confirmation_body = ?,
                    use_tls = ?, use_ssl = ?, is_active = ?,
                    modified_on = GETDATE(), modified_by = ?
                WHERE id = ?
                """,
                (
                    data["smtp_host"], data["smtp_port"], data["smtp_username"],
                    data["smtp_password_encrypted"], data["sender_email"], data["sender_name"],
                    data.get("confirmation_subject"), data.get("confirmation_body"),
                    int(bool(data.get("use_tls"))), int(bool(data.get("use_ssl"))),
                    int(bool(data.get("is_active"))), actor_emp_id, config_id,
                ),
            )
            return config_id

        cursor.execute(
            """
            INSERT INTO Intra_Admin_SMTPConfig
                (smtp_host, smtp_port, smtp_username, smtp_password_encrypted,
                 sender_email, sender_name, confirmation_subject, confirmation_body,
                 use_tls, use_ssl, is_active,
                 created_on, created_by, modified_on, modified_by)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?, GETDATE(), ?)
            """,
            (
                data["smtp_host"], data["smtp_port"], data["smtp_username"],
                data["smtp_password_encrypted"], data["sender_email"], data["sender_name"],
                data.get("confirmation_subject"), data.get("confirmation_body"),
                int(bool(data.get("use_tls"))), int(bool(data.get("use_ssl"))), int(bool(data.get("is_active"))),
                actor_emp_id, actor_emp_id,
            ),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def mark_smtp_test(config_id: int, status: str, message: str, actor_emp_id: int) -> None:
    ensure_email_schema()
    with transactional() as (conn, cursor):
        cursor.execute(
            """
            UPDATE Intra_Admin_SMTPConfig
            SET last_test_status = ?, last_test_message = ?, last_tested_on = GETDATE(),
                modified_on = GETDATE(), modified_by = ?
            WHERE id = ?
            """,
            (status, message[:2000], actor_emp_id, config_id),
        )


# ── workflow email settings ─────────────────────────────────────

def get_workflow_email_settings(module_key: str) -> list[dict]:
    ensure_email_schema()
    sql = """
        SELECT s.*, ws.display_name
        FROM Intra_Admin_WorkflowEmailSettings s
        LEFT JOIN Intra_Admin_WorkflowStatus ws
            ON ws.module_key = s.module_key AND ws.status_key = s.status_key
        WHERE s.module_key = ?
        ORDER BY ws.sort_order, s.status_key
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_key,))
        return _rows_to_list(cursor, cursor.fetchall())


def get_workflow_email_setting(module_key: str, status_key: str) -> dict | None:
    ensure_email_schema()
    sql = """
        SELECT TOP 1 *
        FROM Intra_Admin_WorkflowEmailSettings
        WHERE module_key = ? AND status_key = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_key, status_key))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def ensure_default_workflow_email_setting(
    module_key: str,
    status_key: str,
    subject_template: str,
    body_template: str,
    include_default_attachment: bool,
    actor_emp_id: int,
) -> int:
    """Idempotently create a default workflow email setting and return its id."""
    ensure_email_schema()
    with transactional() as (conn, cursor):
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM Intra_Admin_WorkflowEmailSettings
                WHERE module_key = ? AND status_key = ?
            )
            BEGIN
                INSERT INTO Intra_Admin_WorkflowEmailSettings
                    (module_key, status_key, is_enabled, subject_template, body_template,
                     include_default_attachment, created_on, created_by, modified_on, modified_by)
                VALUES (?, ?, 1, ?, ?, ?, GETDATE(), ?, GETDATE(), ?)
            END
            """,
            (
                module_key,
                status_key,
                module_key,
                status_key,
                subject_template,
                body_template,
                int(bool(include_default_attachment)),
                int(actor_emp_id or 0),
                int(actor_emp_id or 0),
            ),
        )

        cursor.execute(
            """
            SELECT TOP 1 id
            FROM Intra_Admin_WorkflowEmailSettings
            WHERE module_key = ? AND status_key = ?
            ORDER BY id DESC
            """,
            (module_key, status_key),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def upsert_workflow_email_setting(data: dict, actor_emp_id: int) -> int:
    ensure_email_schema()
    module_key = data["module_key"]
    status_key = data["status_key"]
    with transactional() as (conn, cursor):
        existing = get_workflow_email_setting(module_key, status_key)
        if existing:
            setting_id = int(existing["id"])
            cursor.execute(
                """
                UPDATE Intra_Admin_WorkflowEmailSettings
                SET is_enabled = ?, subject_template = ?, body_template = ?,
                    include_default_attachment = ?,
                    modified_on = GETDATE(), modified_by = ?
                WHERE id = ?
                """,
                (
                    int(bool(data.get("is_enabled"))), data["subject_template"], data["body_template"],
                    int(bool(data.get("include_default_attachment"))), actor_emp_id, setting_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO Intra_Admin_WorkflowEmailSettings
                    (module_key, status_key, is_enabled, subject_template, body_template,
                     include_default_attachment, created_on, created_by, modified_on, modified_by)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, GETDATE(), ?, GETDATE(), ?)
                """,
                (
                    module_key, status_key, int(bool(data.get("is_enabled"))),
                    data["subject_template"], data["body_template"],
                    int(bool(data.get("include_default_attachment"))),
                    actor_emp_id, actor_emp_id,
                ),
            )
            row = cursor.fetchone()
            setting_id = int(row[0]) if row else 0

        cursor.execute(
            "DELETE FROM Intra_Admin_WorkflowEmailRecipient WHERE setting_id = ?",
            (setting_id,),
        )
        for rec in data.get("recipients", []):
            cursor.execute(
                """
                INSERT INTO Intra_Admin_WorkflowEmailRecipient
                    (setting_id, recipient_type, recipient_value, is_cc, is_bcc,
                     created_on, created_by)
                VALUES (?, ?, ?, ?, ?, GETDATE(), ?)
                """,
                (
                    setting_id,
                    rec["recipient_type"],
                    rec["recipient_value"],
                    int(bool(rec.get("is_cc"))),
                    int(bool(rec.get("is_bcc"))),
                    actor_emp_id,
                ),
            )

        return setting_id


def list_workflow_recipients(setting_id: int) -> list[dict]:
    ensure_email_schema()
    sql = """
        SELECT *
        FROM Intra_Admin_WorkflowEmailRecipient
        WHERE setting_id = ?
        ORDER BY id
    """
    with read_only() as cursor:
        cursor.execute(sql, (setting_id,))
        return _rows_to_list(cursor, cursor.fetchall())


def add_workflow_attachment(data: dict, actor_emp_id: int) -> int:
    ensure_email_schema()
    with transactional() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO Intra_Admin_WorkflowEmailAttachment
                (setting_id, file_name, original_name, storage_path, mime_type,
                 is_editable, is_active, created_on, created_by)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, 1, GETDATE(), ?)
            """,
            (
                data["setting_id"], data["file_name"], data["original_name"], data["storage_path"],
                data.get("mime_type") or "application/octet-stream",
                int(bool(data.get("is_editable"))),
                actor_emp_id,
            ),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def list_workflow_attachments(setting_id: int) -> list[dict]:
    ensure_email_schema()
    sql = """
        SELECT *
        FROM Intra_Admin_WorkflowEmailAttachment
        WHERE setting_id = ? AND is_active = 1
        ORDER BY id DESC
    """
    with read_only() as cursor:
        cursor.execute(sql, (setting_id,))
        return _rows_to_list(cursor, cursor.fetchall())


def get_workflow_attachment(attachment_id: int) -> dict | None:
    ensure_email_schema()
    sql = "SELECT TOP 1 * FROM Intra_Admin_WorkflowEmailAttachment WHERE id = ?"
    with read_only() as cursor:
        cursor.execute(sql, (attachment_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def deactivate_workflow_attachment(attachment_id: int) -> None:
    ensure_email_schema()
    with transactional() as (conn, cursor):
        cursor.execute(
            """
            UPDATE Intra_Admin_WorkflowEmailAttachment
            SET is_active = 0
            WHERE id = ?
            """,
            (attachment_id,),
        )


def get_workflow_email_payload(module_key: str, status_key: str) -> dict | None:
    setting = get_workflow_email_setting(module_key, status_key)
    if not setting:
        return None

    recipients = list_workflow_recipients(int(setting["id"]))
    attachments = list_workflow_attachments(int(setting["id"]))
    payload = dict(setting)
    payload["recipients"] = recipients
    payload["attachments"] = attachments
    return payload


def to_json(value: list[str]) -> str:
    return json.dumps(value or [])
