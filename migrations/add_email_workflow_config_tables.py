"""
Migration: create SMTP + workflow email configuration tables.

Run:
    python .\migrations\add_email_workflow_config_tables.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection


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


def run() -> None:
    conn = get_connection()
    cur = conn.cursor()

    if not _table_exists(cur, "Intra_Admin_SMTPConfig"):
        cur.execute(
            """
            CREATE TABLE Intra_Admin_SMTPConfig (
                id INT IDENTITY(1,1) PRIMARY KEY,
                smtp_host NVARCHAR(255) NOT NULL,
                smtp_port INT NOT NULL DEFAULT 587,
                smtp_username NVARCHAR(255) NOT NULL,
                smtp_password_encrypted NVARCHAR(MAX) NOT NULL,
                sender_email NVARCHAR(255) NOT NULL,
                sender_name NVARCHAR(255) NULL,
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
        print("[ADD] Intra_Admin_SMTPConfig")
    else:
        print("[SKIP] Intra_Admin_SMTPConfig")

    if not _table_exists(cur, "Intra_Admin_WorkflowEmailSettings"):
        cur.execute(
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
        print("[ADD] Intra_Admin_WorkflowEmailSettings")
    else:
        print("[SKIP] Intra_Admin_WorkflowEmailSettings")

    if not _table_exists(cur, "Intra_Admin_WorkflowEmailRecipient"):
        cur.execute(
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
        print("[ADD] Intra_Admin_WorkflowEmailRecipient")
    else:
        print("[SKIP] Intra_Admin_WorkflowEmailRecipient")

    if not _table_exists(cur, "Intra_Admin_WorkflowEmailAttachment"):
        cur.execute(
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
        print("[ADD] Intra_Admin_WorkflowEmailAttachment")
    else:
        print("[SKIP] Intra_Admin_WorkflowEmailAttachment")

    if not _index_exists(cur, "Intra_Admin_WorkflowEmailSettings", "IX_WorkflowEmailSettings_ModuleStatus"):
        cur.execute(
            "CREATE INDEX IX_WorkflowEmailSettings_ModuleStatus "
            "ON Intra_Admin_WorkflowEmailSettings (module_key, status_key)"
        )
        print("[ADD] IX_WorkflowEmailSettings_ModuleStatus")

    if not _index_exists(cur, "Intra_Admin_WorkflowEmailRecipient", "IX_WorkflowEmailRecipient_Setting"):
        cur.execute(
            "CREATE INDEX IX_WorkflowEmailRecipient_Setting "
            "ON Intra_Admin_WorkflowEmailRecipient (setting_id)"
        )
        print("[ADD] IX_WorkflowEmailRecipient_Setting")

    if not _index_exists(cur, "Intra_Admin_WorkflowEmailAttachment", "IX_WorkflowEmailAttachment_Setting"):
        cur.execute(
            "CREATE INDEX IX_WorkflowEmailAttachment_Setting "
            "ON Intra_Admin_WorkflowEmailAttachment (setting_id, is_active)"
        )
        print("[ADD] IX_WorkflowEmailAttachment_Setting")

    conn.commit()
    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
