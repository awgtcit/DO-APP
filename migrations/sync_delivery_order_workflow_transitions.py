"""
Migration: Align Delivery Order workflow transitions with rejection/resubmission rules
shown in the Workflow Editor.

This migration is additive and updates the plain DRAFT->SUBMITTED creator row
into a condition-aware rule set.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection

MODULE_KEY = "delivery_orders"

TARGET_TRANSITIONS = [
    ("DRAFT", "CANCELLED", "do_creator"),
    ("DRAFT", "PENDING CUSTOMER APPROVAL", "do_creator|ownership_required"),
    ("DRAFT", "SUBMITTED", "do_creator|standard_submit"),
    ("DRAFT", "PRICE AGREED", "do_creator|rejected_by_logistics_no_price_change"),
    ("PENDING CUSTOMER APPROVAL", "SUBMITTED", "do_customer_manager"),
    ("PENDING CUSTOMER APPROVAL", "REJECTED", "do_customer_manager"),
    ("PENDING CUSTOMER APPROVAL", "DRAFT", "do_creator"),
    ("SUBMITTED", "PRICE AGREED", "do_finance"),
    ("SUBMITTED", "REJECTED", "do_finance"),
    ("PRICE AGREED", "CONFIRMED", "do_logistics"),
    ("PRICE AGREED", "REJECTED", "do_logistics"),
]


def transition_exists(cursor, from_status: str, to_status: str, required_role: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM Intra_Admin_WorkflowTransition
        WHERE module_key = ? AND from_status = ? AND to_status = ? AND ISNULL(required_role, '') = ?
        """,
        [MODULE_KEY, from_status, to_status, required_role],
    )
    return cursor.fetchone()[0] > 0


def plain_creator_submit_exists(cursor) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM Intra_Admin_WorkflowTransition
        WHERE module_key = ? AND from_status = 'DRAFT' AND to_status = 'SUBMITTED'
          AND ISNULL(required_role, '') IN ('do_creator', 'creator')
        """,
        [MODULE_KEY],
    )
    return cursor.fetchone()[0] > 0


def upgrade_plain_creator_submit(cursor):
    cursor.execute(
        """
        UPDATE Intra_Admin_WorkflowTransition
        SET required_role = 'do_creator|standard_submit'
        WHERE module_key = ? AND from_status = 'DRAFT' AND to_status = 'SUBMITTED'
          AND ISNULL(required_role, '') IN ('do_creator', 'creator')
        """,
        [MODULE_KEY],
    )
    return cursor.rowcount


def main():
    conn = get_connection()
    cursor = conn.cursor()

    if plain_creator_submit_exists(cursor):
        updated = upgrade_plain_creator_submit(cursor)
        conn.commit()
        print(f"  [UPDATE] normalized {updated} plain DRAFT->SUBMITTED creator transition(s)")

    for from_status, to_status, required_role in TARGET_TRANSITIONS:
        if transition_exists(cursor, from_status, to_status, required_role):
            print(f"  [SKIP] {from_status} -> {to_status} ({required_role})")
            continue
        cursor.execute(
            """
            INSERT INTO Intra_Admin_WorkflowTransition (module_key, from_status, to_status, required_role)
            VALUES (?, ?, ?, ?)
            """,
            [MODULE_KEY, from_status, to_status, required_role],
        )
        conn.commit()
        print(f"  [ADD]  {from_status} -> {to_status} ({required_role})")

    cursor.close()
    conn.close()
    print("\nWorkflow transition sync complete.")


if __name__ == "__main__":
    main()
