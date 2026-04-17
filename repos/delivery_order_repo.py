"""
Delivery Order repository — all database access for the Sales/Delivery Order module.
Every query is parameterized (no string interpolation).
"""

from db.connection import get_connection
from db.transaction import transactional, read_only
from datetime import datetime


# ── Dashboard KPIs ──────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Return counts by status for the Delivery Order dashboard KPIs."""
    sql = """
        SELECT
            COUNT(*)                                             AS total,
            SUM(CASE WHEN Status = 'DRAFT'           THEN 1 ELSE 0 END) AS drafts,
            SUM(CASE WHEN Status = 'SUBMITTED'       THEN 1 ELSE 0 END) AS submitted,
            SUM(CASE WHEN Status = 'NEED ATTACHMENT'  THEN 1 ELSE 0 END) AS need_attach,
            SUM(CASE WHEN Status = 'PRICE AGREED'    THEN 1 ELSE 0 END) AS price_agreed,
            SUM(CASE WHEN Status = 'CONFIRMED'       THEN 1 ELSE 0 END) AS confirmed,
            SUM(CASE WHEN Status = 'CUSTOMS DOCUMENT UPDATED' THEN 1 ELSE 0 END) AS customs_updated,
            SUM(CASE WHEN Status = 'DELIVERED'       THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN Status = 'REJECTED'        THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN Status = 'CANCELLED'       THEN 1 ELSE 0 END) AS cancelled
        FROM Intra_SalesOrder
    """
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        if not row:
            return {k: 0 for k in (
                "total", "drafts", "submitted", "need_attach",
                "price_agreed", "confirmed", "customs_updated",
                "delivered", "rejected", "cancelled",
            )}
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


# ── Order listing ───────────────────────────────────────────────

def get_all_orders(
    status: str | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """
    Retrieve delivery orders with optional filtering, search, and pagination.
    Returns (rows, total_count).
    """
    where_clauses: list[str] = []
    params: list = []

    if status and status != "ALL":
        where_clauses.append("t1.Status = ?")
        params.append(status)

    if search:
        where_clauses.append(
            "(CAST(t1.PO_Number AS VARCHAR(100)) LIKE ? OR CAST(t3.Name AS VARCHAR(200)) LIKE ? OR t6.FirstName LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    offset = (page - 1) * per_page

    # Count query needs JOINs when search references t3/t6
    if search:
        count_sql = f"""SELECT COUNT(*) FROM Intra_SalesOrder t1
            LEFT JOIN Intra_SalesOrder_BillTo t3 ON CAST(t3.SapCode AS VARCHAR(100)) = CAST(t1.Bill_To_SapCode AS VARCHAR(100))
            LEFT JOIN Intra_Users t6 ON t6.EmpID = t1.Created_by
            {where_sql}"""
    else:
        count_sql = f"SELECT COUNT(*) FROM Intra_SalesOrder t1{where_sql}"

    data_sql = f"""
        SELECT t1.id,
               CONVERT(VARCHAR(10), t1.PO_Date, 120)    AS order_date,
               t1.PO_Number                              AS order_no,
               ISNULL(t2.FirstName + ' ' + t2.LastName, '') AS on_behalf_of,
               CONVERT(VARCHAR(10), t1.Loading_Date, 120) AS loading_date,
               ISNULL(t3.Name, '')                       AS bill_to,
               t1.Ship_To_FinalDestination               AS final_destination,
               ISNULL(t6.FirstName, '')                  AS created_by,
               (SELECT COUNT(*) FROM Intra_SalesOrder_Items t7
                WHERE CAST(t1.PO_Number AS VARCHAR(100)) = CAST(t7.PO_Number AS VARCHAR(100)))  AS item_count,
               t1.Status                                 AS status
        FROM Intra_SalesOrder t1
        LEFT JOIN Intra_Users t2 ON t2.EmpID = t1.On_Behalf_Of
        LEFT JOIN Intra_SalesOrder_BillTo t3 ON CAST(t3.SapCode AS VARCHAR(100)) = CAST(t1.Bill_To_SapCode AS VARCHAR(100))
        LEFT JOIN Intra_Users t6 ON t6.EmpID = t1.Created_by
        {where_sql}
        ORDER BY t1.id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        cursor.execute(data_sql, params + [offset, per_page])
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

    return rows, total


# ── Single order ────────────────────────────────────────────────

def get_order_by_id(order_id: int) -> dict | None:
    """Load a single delivery order with all related lookups."""
    sql = """
        SELECT t1.*,
               ISNULL(t2.FirstName + ' ' + t2.LastName, '') AS on_behalf_of_name,
               t2.ReferenceName                             AS on_behalf_ref,
               ISNULL(t3.Name, '')    AS bill_to_name,
               ISNULL(t3.Address, '') AS bill_to_address,
               t3.SapCodeFromSAP     AS bill_to_sap,
               ISNULL(t4.Name, '')    AS ship_to_name,
               ISNULL(t4.Address, '') AS ship_to_address,
               t4.SapCodeFromSAP     AS bill_to_sap_ship,
               ISNULL(t5.ExitName, '') AS point_of_exit_name,
               ISNULL(t6.FirstName, '') AS creator_first,
               ISNULL(t6.LastName, '')  AS creator_last,
               ISNULL(t6.EmailAddress, '') AS creator_email,
               CONVERT(VARCHAR(10), t1.PO_Date, 120)       AS po_date_fmt,
               CONVERT(VARCHAR(10), t1.Loading_Date, 120)   AS loading_date_fmt,
               CONVERT(VARCHAR(19), t1.Created_on, 120)     AS created_on_fmt
        FROM Intra_SalesOrder t1
        LEFT JOIN Intra_Users t2 ON t2.EmpID = t1.On_Behalf_Of
        LEFT JOIN Intra_SalesOrder_BillTo t3 ON CAST(t3.SapCode AS VARCHAR(100)) = CAST(t1.Bill_To_SapCode AS VARCHAR(100))
        LEFT JOIN Intra_SalesOrder_BillTo t4 ON CAST(t4.SapCode AS VARCHAR(100)) = CAST(t1.Ship_To_SapCode AS VARCHAR(100))
        LEFT JOIN Intra_SalesOrder_PointOfExit t5 ON CAST(t5.ExitID AS VARCHAR(100)) = CAST(t1.Ship_To_PointOfExit AS VARCHAR(100))
        LEFT JOIN Intra_Users t6 ON t6.EmpID = t1.Created_by
        WHERE t1.id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [order_id])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def get_order_items(po_number: str) -> list[dict]:
    """Get all line items for a given PO number."""
    sql = """
        SELECT i.id, i.PO_Number, i.Product_ID,
               ISNULL(p.Name, '')           AS product_name,
               ISNULL(p.Market, '')         AS market,
               ISNULL(p.Unit_Of_Measure, '') AS Unit_Of_Measure,
               i.Quantity, i.Unit_Price, i.Total_Amount,
               i.Currency, i.Container, i.Truck,
               i.Loading_Sequence, i.Remarks
        FROM Intra_SalesOrder_Items i
        LEFT JOIN Intra_SalesOrder_Products p ON p.Product_ID = i.Product_ID
        WHERE CAST(i.PO_Number AS VARCHAR(100)) = ?
        ORDER BY i.Loading_Sequence, i.id
    """
    with read_only() as cursor:
        cursor.execute(sql, [po_number])
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


# ── Lookup data ─────────────────────────────────────────────────

def get_sales_managers() -> list[dict]:
    """Get users in GroupID 10 (sales managers) for On Behalf Of dropdown."""
    sql = """
        SELECT EmpID, FirstName, LastName, ReferenceName
        FROM Intra_Users
        WHERE GroupID IN (10, 12)
        ORDER BY FirstName
    """
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_bill_to_list() -> list[dict]:
    """Get all active Bill To / Ship To customers."""
    sql = """
        SELECT id, SapCode, SapCodeFromSAP, Name, Address
        FROM Intra_SalesOrder_BillTo
        WHERE ISNULL(Status, '1') = '1'
        ORDER BY Name
    """
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_point_of_exit_list() -> list[dict]:
    """Get all Points of Exit."""
    sql = "SELECT id, ExitID, ExitName FROM Intra_SalesOrder_PointOfExit ORDER BY id"
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_products() -> list[dict]:
    """Get all products for line item selection."""
    sql = """
        SELECT Product_ID, Name, Market, Unit_Of_Measure, Sales_Manager
        FROM Intra_SalesOrder_Products
        ORDER BY Name
    """
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_last_po_number() -> str:
    """Get the last PO number for reference display."""
    sql = "SELECT TOP 1 PO_Number FROM Intra_SalesOrder ORDER BY id DESC"
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        return row[0] if row else "—"


# ── Create order ────────────────────────────────────────────────

def create_order(data: dict) -> int:
    """Insert a new delivery order and return the new record ID."""
    now = datetime.now()
    month_abbr = now.strftime("%b")
    year_short = now.strftime("%y")

    with transactional() as (conn, cursor):
        # Get next ID-based sequence
        cursor.execute("SELECT ISNULL(MAX(id), 0) + 1 FROM Intra_SalesOrder")
        next_id = cursor.fetchone()[0]
        po_number = f"AWTFZC/{month_abbr}/{year_short}/DO{next_id}"

        sql = """
            INSERT INTO Intra_SalesOrder
            (PO_Date, PO_Number, Loading_Date, Delivery_Terms, Payment_Terms,
             Transportation_Mode, Bill_To_SapCode, Ship_To_SapCode,
             Ship_To_PointOfExit, Ship_To_PointOfDischarge,
             Ship_To_FinalDestination, Notify_Party, Shipping_Agent,
             On_Behalf_Of, Status, DOCurrency, Created_by, Created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
        """
        cursor.execute(sql, [
            data.get("po_date"),
            po_number,
            data.get("loading_date"),
            data.get("delivery_terms"),
            data.get("payment_terms"),
            data.get("transportation_mode"),
            data.get("bill_to"),
            data.get("ship_to"),
            data.get("point_of_exit"),
            data.get("point_of_discharge"),
            data.get("final_destination"),
            data.get("notify_party"),
            data.get("shipping_agent"),
            data.get("on_behalf_of"),
            data.get("currency", "USD"),
            data.get("created_by"),
            now,
        ])

        cursor.execute("SELECT @@IDENTITY")
        new_id = int(cursor.fetchone()[0])
        return new_id


# ── Update order ────────────────────────────────────────────────

def update_order(order_id: int, data: dict) -> bool:
    """Update an existing delivery order."""
    sql = """
        UPDATE Intra_SalesOrder SET
            PO_Date = ?, Loading_Date = ?, Delivery_Terms = ?,
            Payment_Terms = ?, Transportation_Mode = ?,
            Bill_To_SapCode = ?, Ship_To_SapCode = ?,
            Ship_To_PointOfExit = ?, Ship_To_PointOfDischarge = ?,
            Ship_To_FinalDestination = ?, Notify_Party = ?,
            Shipping_Agent = ?, On_Behalf_Of = ?, DOCurrency = ?,
            Modified_by = ?, Modified_on = ?
        WHERE id = ?
    """
    with transactional() as (conn, cursor):
        cursor.execute(sql, [
            data.get("po_date"),
            data.get("loading_date"),
            data.get("delivery_terms"),
            data.get("payment_terms"),
            data.get("transportation_mode"),
            data.get("bill_to"),
            data.get("ship_to"),
            data.get("point_of_exit"),
            data.get("point_of_discharge"),
            data.get("final_destination"),
            data.get("notify_party"),
            data.get("shipping_agent"),
            data.get("on_behalf_of"),
            data.get("currency", "USD"),
            data.get("modified_by"),
            datetime.now(),
            order_id,
        ])
        return cursor.rowcount > 0


def update_order_status(order_id: int, new_status: str, modified_by: int) -> bool:
    """Change only the status of an order."""
    sql = """
        UPDATE Intra_SalesOrder
        SET Status = ?, Modified_by = ?, Modified_on = ?
        WHERE id = ?
    """
    with transactional() as (conn, cursor):
        cursor.execute(sql, [new_status, modified_by, datetime.now(), order_id])
        return cursor.rowcount > 0


# ── Items CRUD ──────────────────────────────────────────────────

def add_order_item(data: dict) -> int:
    """Add a line item to a delivery order."""
    sql = """
        INSERT INTO Intra_SalesOrder_Items
        (PO_Number, Product_ID, Quantity, Unit_Price, Total_Amount,
         Currency, Container, Truck, Loading_Sequence, Remarks,
         Created_on, Created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with transactional() as (conn, cursor):
        qty = float(data.get("quantity", 0))
        price = float(data.get("unit_price", 0))
        cursor.execute(sql, [
            data.get("po_number"),
            data.get("product_id"),
            qty,
            price,
            qty * price,
            data.get("currency", "USD"),
            data.get("container", ""),
            data.get("truck", ""),
            data.get("loading_sequence", 0),
            data.get("remarks", ""),
            datetime.now(),
            data.get("created_by"),
        ])
        cursor.execute("SELECT @@IDENTITY")
        return int(cursor.fetchone()[0])


def delete_order_item(item_id: int) -> bool:
    """Remove a line item."""
    sql = "DELETE FROM Intra_SalesOrder_Items WHERE id = ?"
    with transactional() as (conn, cursor):
        cursor.execute(sql, [item_id])
        return cursor.rowcount > 0


# ── Pricing permission ──────────────────────────────────────────

def check_pricing_permission(emp_id: int) -> bool:
    """Check if a user has explicit pricing visibility permission."""
    sql = """
        SELECT COUNT(*) FROM Intra_SalesOrder_PricingPermission
        WHERE EmpID = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [emp_id])
        row = cursor.fetchone()
        return row[0] > 0 if row else False


# ── Reject reason ───────────────────────────────────────────────

def update_order_status_with_reason(
    order_id: int,
    new_status: str,
    modified_by: int,
    reject_reason: str | None = None,
    reject_remarks: str | None = None,
) -> bool:
    """Change order status with optional reject reason and remarks."""
    if reject_reason or reject_remarks:
        sql = """
            UPDATE Intra_SalesOrder
            SET Status = ?, Modified_by = ?, Modified_on = ?,
                Reject_Reason = ?, Reject_Remarks = ?
            WHERE id = ?
        """
        params = [
            new_status, modified_by, datetime.now(),
            reject_reason or "", reject_remarks or "",
            order_id,
        ]
    else:
        sql = """
            UPDATE Intra_SalesOrder
            SET Status = ?, Modified_by = ?, Modified_on = ?
            WHERE id = ?
        """
        params = [new_status, modified_by, datetime.now(), order_id]

    with transactional() as (conn, cursor):
        cursor.execute(sql, params)
        return cursor.rowcount > 0


# ── Post-delivery tracking fields ───────────────────────────────

def update_logistics_fields(order_id: int, data: dict, modified_by: int,
                            new_status: str | None = None) -> bool:
    """Update Fujairah Logistics Team post-delivery fields and optionally change status."""
    if new_status:
        sql = """
            UPDATE Intra_SalesOrder
            SET Exit_Document_Number = ?,
                FTA_Declaration_Number = ?,
                SAP_Sales_Invoice_Number = ?,
                Status = ?,
                Modified_by = ?, Modified_on = ?
            WHERE id = ?
        """
        params = [
            data.get("exit_document_number", ""),
            data.get("fta_declaration_number", ""),
            data.get("sap_sales_invoice_number", ""),
            new_status,
            modified_by,
            datetime.now(),
            order_id,
        ]
    else:
        sql = """
            UPDATE Intra_SalesOrder
            SET Exit_Document_Number = ?,
                FTA_Declaration_Number = ?,
                SAP_Sales_Invoice_Number = ?,
                Modified_by = ?, Modified_on = ?
            WHERE id = ?
        """
        params = [
            data.get("exit_document_number", ""),
            data.get("fta_declaration_number", ""),
            data.get("sap_sales_invoice_number", ""),
            modified_by,
            datetime.now(),
            order_id,
        ]
    with transactional() as (conn, cursor):
        cursor.execute(sql, params)
        return cursor.rowcount > 0


def update_sales_fields(order_id: int, data: dict, modified_by: int,
                        new_status: str | None = None) -> bool:
    """Update Sales Team post-delivery fields and optionally change status."""
    if new_status:
        sql = """
            UPDATE Intra_SalesOrder
            SET Customs_BOE_Number = ?,
                Airway_Bill_Number = ?,
                IEC_Code = ?,
                Status = ?,
                Modified_by = ?, Modified_on = ?
            WHERE id = ?
        """
        params = [
            data.get("customs_boe_number", ""),
            data.get("airway_bill_number", ""),
            data.get("iec_code", ""),
            new_status,
            modified_by,
            datetime.now(),
            order_id,
        ]
    else:
        sql = """
            UPDATE Intra_SalesOrder
            SET Customs_BOE_Number = ?,
                Airway_Bill_Number = ?,
                IEC_Code = ?,
                Modified_by = ?, Modified_on = ?
            WHERE id = ?
        """
        params = [
            data.get("customs_boe_number", ""),
            data.get("airway_bill_number", ""),
            data.get("iec_code", ""),
            modified_by,
            datetime.now(),
            order_id,
        ]
    with transactional() as (conn, cursor):
        cursor.execute(sql, params)
        return cursor.rowcount > 0


# ── Attachments (NEED ATTACHMENT status) ────────────────────────

def get_order_attachments(order_id: int) -> list[dict]:
    """Get all attachments for a delivery order."""
    sql = """
        SELECT id, SalesOrder_ID, FileName, WebPath, DirPath,
               Status, Created_on, Created_by, Modified_on, Modified_by
        FROM Intra_SalesOrder_Approved_Attachments
        WHERE SalesOrder_ID = ?
        ORDER BY id DESC
    """
    with read_only() as cursor:
        cursor.execute(sql, [order_id])
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def add_order_attachment(data: dict) -> int:
    """Add an attachment to a delivery order (binary stored in DB)."""
    sql = """
        INSERT INTO Intra_SalesOrder_Approved_Attachments
        (SalesOrder_ID, FileName, WebPath, DirPath, FileData, ContentType,
         Status, Created_on, Created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with transactional() as (conn, cursor):
        cursor.execute(sql, [
            data.get("order_id"),
            data.get("file_name"),
            data.get("web_path", ""),
            data.get("dir_path", ""),
            data.get("file_data"),
            data.get("content_type", "application/octet-stream"),
            data.get("status", "Active"),
            datetime.now(),
            data.get("uploaded_by"),
        ])
        cursor.execute("SELECT @@IDENTITY")
        return int(cursor.fetchone()[0])


def get_attachment_by_id(attachment_id: int) -> dict | None:
    """Retrieve a single attachment with its binary content."""
    sql = """
        SELECT id, SalesOrder_ID, FileName, ContentType, FileData
        FROM Intra_SalesOrder_Approved_Attachments
        WHERE id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [attachment_id])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def delete_order_attachment(attachment_id: int) -> bool:
    """Delete an attachment."""
    sql = "DELETE FROM Intra_SalesOrder_Approved_Attachments WHERE id = ?"
    with transactional() as (conn, cursor):
        cursor.execute(sql, [attachment_id])
        return cursor.rowcount > 0


# ── User-filtered dashboard stats ──────────────────────────────

def get_dashboard_stats_for_user(emp_id: int) -> dict:
    """Return counts filtered to orders created by a specific user."""
    sql = """
        SELECT
            COUNT(*)                                             AS total,
            SUM(CASE WHEN Status = 'DRAFT'           THEN 1 ELSE 0 END) AS drafts,
            SUM(CASE WHEN Status = 'SUBMITTED'       THEN 1 ELSE 0 END) AS submitted,
            SUM(CASE WHEN Status = 'NEED ATTACHMENT'  THEN 1 ELSE 0 END) AS need_attach,
            SUM(CASE WHEN Status = 'PRICE AGREED'    THEN 1 ELSE 0 END) AS price_agreed,
            SUM(CASE WHEN Status = 'CONFIRMED'       THEN 1 ELSE 0 END) AS confirmed,
            SUM(CASE WHEN Status = 'CUSTOMS DOCUMENT UPDATED' THEN 1 ELSE 0 END) AS customs_updated,
            SUM(CASE WHEN Status = 'DELIVERED'       THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN Status = 'REJECTED'        THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN Status = 'CANCELLED'       THEN 1 ELSE 0 END) AS cancelled
        FROM Intra_SalesOrder
        WHERE Created_by = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [emp_id])
        row = cursor.fetchone()
        if not row:
            return {k: 0 for k in (
                "total", "drafts", "submitted", "need_attach",
                "price_agreed", "confirmed", "customs_updated",
                "delivered", "rejected", "cancelled",
            )}
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


# ── User-filtered order listing ─────────────────────────────────

def get_orders_for_user(
    emp_id: int,
    status: str | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """Retrieve delivery orders created by a specific user."""
    where_clauses: list[str] = ["t1.Created_by = ?"]
    params: list = [emp_id]

    if status and status != "ALL":
        where_clauses.append("t1.Status = ?")
        params.append(status)

    if search:
        where_clauses.append(
            "(CAST(t1.PO_Number AS VARCHAR(100)) LIKE ? OR CAST(t3.Name AS VARCHAR(200)) LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term])

    where_sql = " WHERE " + " AND ".join(where_clauses)
    offset = (page - 1) * per_page

    count_sql = f"""SELECT COUNT(*) FROM Intra_SalesOrder t1
        LEFT JOIN Intra_SalesOrder_BillTo t3 ON CAST(t3.SapCode AS VARCHAR(100)) = CAST(t1.Bill_To_SapCode AS VARCHAR(100))
        {where_sql}"""

    data_sql = f"""
        SELECT t1.id,
               CONVERT(VARCHAR(10), t1.PO_Date, 120)    AS order_date,
               t1.PO_Number                              AS order_no,
               ISNULL(t2.FirstName + ' ' + t2.LastName, '') AS on_behalf_of,
               CONVERT(VARCHAR(10), t1.Loading_Date, 120) AS loading_date,
               ISNULL(t3.Name, '')                       AS bill_to,
               t1.Ship_To_FinalDestination               AS final_destination,
               ISNULL(t6.FirstName, '')                  AS created_by,
               (SELECT COUNT(*) FROM Intra_SalesOrder_Items t7
                WHERE CAST(t1.PO_Number AS VARCHAR(100)) = CAST(t7.PO_Number AS VARCHAR(100)))  AS item_count,
               t1.Status                                 AS status
        FROM Intra_SalesOrder t1
        LEFT JOIN Intra_Users t2 ON t2.EmpID = t1.On_Behalf_Of
        LEFT JOIN Intra_SalesOrder_BillTo t3 ON CAST(t3.SapCode AS VARCHAR(100)) = CAST(t1.Bill_To_SapCode AS VARCHAR(100))
        LEFT JOIN Intra_Users t6 ON t6.EmpID = t1.Created_by
        {where_sql}
        ORDER BY t1.id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        cursor.execute(data_sql, params + [offset, per_page])
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

    return rows, total


# ── Customer detail by SapCode ──────────────────────────────────

def get_customer_by_sap_code(sap_code: str) -> dict | None:
    """Get a single customer by SapCode."""
    sql = """
        SELECT id, SapCode, SapCodeFromSAP, Name, Address
        FROM Intra_SalesOrder_BillTo
        WHERE CAST(SapCode AS VARCHAR(100)) = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [sap_code])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


# ══════════════════════════════════════════════════════════════════
# ── Products Management CRUD ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

def get_all_products() -> list[dict]:
    """Return full product list for the management table."""
    sql = """
        SELECT p.id, p.Product_ID, p.Name, p.Market,
               p.Unit_Of_Measure, p.Sales_Manager,
               ISNULL(u.FirstName + ' ' + u.LastName, '') AS manager_name,
               p.Created_on
        FROM Intra_SalesOrder_Products p
        LEFT JOIN Intra_Users u ON u.EmpID = p.Sales_Manager
        ORDER BY p.id DESC
    """
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_product_by_id(product_id: int) -> dict | None:
    """Fetch a single product by PK."""
    sql = "SELECT * FROM Intra_SalesOrder_Products WHERE id = ?"
    with read_only() as cursor:
        cursor.execute(sql, [product_id])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def product_exists(product_code: str, exclude_id: int | None = None) -> bool:
    """Check if a Product_ID already exists (for duplicate check)."""
    sql = "SELECT COUNT(*) FROM Intra_SalesOrder_Products WHERE Product_ID = ?"
    params: list = [product_code]
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    with read_only() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0] > 0


def create_product(data: dict) -> int:
    """Insert a new product. Returns new ID."""
    with transactional() as (conn, cursor):
        sql = """
            INSERT INTO Intra_SalesOrder_Products
                (Product_ID, Name, Market, Unit_Of_Measure, Sales_Manager,
                 Created_on, Created_by)
            VALUES (?, ?, ?, ?, ?, GETDATE(), ?)
        """
        cursor.execute(sql, [
            data["product_id"], data["name"], data.get("market", ""),
            data.get("uom", ""), data.get("sales_manager"),
            data.get("created_by"),
        ])
        cursor.execute("SELECT @@IDENTITY")
        return int(cursor.fetchone()[0])


def update_product(pk: int, data: dict) -> bool:
    """Update an existing product."""
    with transactional() as (conn, cursor):
        sql = """
            UPDATE Intra_SalesOrder_Products
            SET Product_ID = ?, Name = ?, Market = ?,
                Unit_Of_Measure = ?, Sales_Manager = ?,
                Modified_on = GETDATE(), Modified_by = ?
            WHERE id = ?
        """
        cursor.execute(sql, [
            data["product_id"], data["name"], data.get("market", ""),
            data.get("uom", ""), data.get("sales_manager"),
            data.get("modified_by"), pk,
        ])
        return cursor.rowcount > 0


# ══════════════════════════════════════════════════════════════════
# ── Customer (BillTo) Management CRUD ────────────────────────────
# ══════════════════════════════════════════════════════════════════

def get_all_customers() -> list[dict]:
    """Return all active customers for the management table."""
    sql = """
        SELECT id, SapCode, SapCodeFromSAP, Name, Address,
               Postal_Code, Country_ISO_Code, Region,
               Contact_Number, Status, Created_on
        FROM Intra_SalesOrder_BillTo
        WHERE Status = '1'
        ORDER BY id DESC
    """
    with read_only() as cursor:
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def get_customer_by_pk(pk: int) -> dict | None:
    """Fetch a single customer by PK."""
    sql = "SELECT * FROM Intra_SalesOrder_BillTo WHERE id = ?"
    with read_only() as cursor:
        cursor.execute(sql, [pk])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def customer_sap_exists(sap_code: str, exclude_id: int | None = None) -> bool:
    """Check if SapCode already exists (duplicate guard)."""
    sql = "SELECT COUNT(*) FROM Intra_SalesOrder_BillTo WHERE CAST(SapCode AS VARCHAR(100)) = ?"
    params: list = [sap_code]
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    with read_only() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0] > 0


def next_customer_sap_code() -> str:
    """Generate the next SapCode (max + 1)."""
    sql = "SELECT ISNULL(MAX(CAST(SapCode AS INT)), 0) + 1 FROM Intra_SalesOrder_BillTo"
    with read_only() as cursor:
        cursor.execute(sql)
        return str(cursor.fetchone()[0])


def create_customer(data: dict) -> int:
    """Insert a new BillTo customer. Returns new ID."""
    with transactional() as (conn, cursor):
        sql = """
            INSERT INTO Intra_SalesOrder_BillTo
                (SapCode, SapCodeFromSAP, Name, Address, Postal_Code,
                 Country_ISO_Code, Region, Contact_Number, Status,
                 Created_on, Created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '1', GETDATE(), ?)
        """
        cursor.execute(sql, [
            data["sap_code"], data.get("sap_code_from_sap", ""),
            data["name"], data.get("address", ""),
            data.get("postal_code", ""), data.get("country_iso", ""),
            data.get("region", ""), data.get("contact_number", ""),
            data.get("created_by"),
        ])
        cursor.execute("SELECT @@IDENTITY")
        return int(cursor.fetchone()[0])


def update_customer(pk: int, data: dict) -> bool:
    """Update an existing customer."""
    with transactional() as (conn, cursor):
        sql = """
            UPDATE Intra_SalesOrder_BillTo
            SET SapCodeFromSAP = ?, Name = ?, Address = ?,
                Postal_Code = ?, Country_ISO_Code = ?, Region = ?,
                Contact_Number = ?,
                Modified_on = GETDATE(), Modified_by = ?
            WHERE id = ?
        """
        cursor.execute(sql, [
            data.get("sap_code_from_sap", ""), data["name"],
            data.get("address", ""), data.get("postal_code", ""),
            data.get("country_iso", ""), data.get("region", ""),
            data.get("contact_number", ""), data.get("modified_by"), pk,
        ])
        return cursor.rowcount > 0


# ══════════════════════════════════════════════════════════════════
# ── GRMS (Receipts) ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

def get_all_receipts(
    status: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[dict], int]:
    """Paginated receipt listing with optional status filter."""
    where_parts: list[str] = []
    params: list = []

    if status and status != "ALL":
        where_parts.append("r.Status = ?")
        params.append(status)

    where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    offset = (page - 1) * per_page

    count_sql = f"SELECT COUNT(*) FROM Intra_SalesOrder_Receipts r {where_sql}"

    data_sql = f"""
        SELECT r.id, r.Receipt_Number, r.PO_Number,
               ISNULL(u.FirstName + ' ' + u.LastName, '') AS on_behalf_of,
               CONVERT(VARCHAR(10), r.Received_On, 120) AS received_on,
               r.SAP_Material_Document_Number,
               r.FTA_Declaration_Number,
               r.Remarks, r.Status,
               ISNULL(u2.FirstName, '') AS created_by,
               (SELECT COUNT(*) FROM Intra_SalesOrder_ReceiptItems ri
                WHERE ri.Receipt_Number = r.Receipt_Number) AS item_count
        FROM Intra_SalesOrder_Receipts r
        LEFT JOIN Intra_Users u  ON u.EmpID  = r.On_Behalf_Of
        LEFT JOIN Intra_Users u2 ON u2.EmpID = r.Created_by
        {where_sql}
        ORDER BY r.id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]
        cursor.execute(data_sql, params + [offset, per_page])
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    return rows, total


def get_receipt_by_id(receipt_id: int) -> dict | None:
    """Get a single receipt header."""
    sql = """
        SELECT r.*, ISNULL(u.FirstName + ' ' + u.LastName, '') AS on_behalf_of_name,
               ISNULL(u2.FirstName, '') AS creator_first
        FROM Intra_SalesOrder_Receipts r
        LEFT JOIN Intra_Users u  ON u.EmpID  = r.On_Behalf_Of
        LEFT JOIN Intra_Users u2 ON u2.EmpID = r.Created_by
        WHERE r.id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, [receipt_id])
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def get_receipt_items(receipt_number: str) -> list[dict]:
    """Get line items for a receipt."""
    sql = """
        SELECT ri.id, ri.Product_ID, ri.Quantity, ri.Remarks,
               ISNULL(p.Name, '') AS product_name,
               ISNULL(p.Unit_Of_Measure, '') AS uom
        FROM Intra_SalesOrder_ReceiptItems ri
        LEFT JOIN Intra_SalesOrder_Products p ON p.Product_ID = ri.Product_ID
        WHERE ri.Receipt_Number = ?
        ORDER BY ri.id
    """
    with read_only() as cursor:
        cursor.execute(sql, [receipt_number])
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


# ── Reports ──────────────────────────────────────────────────────

def get_products_sold_report(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Products sold summary — aggregated by product from confirmed orders."""
    where_parts = ["so.Status IN ('CONFIRMED', 'PRICE AGREED', 'NEED ATTACHMENT')"]
    params: list = []

    if date_from:
        where_parts.append("so.PO_Date >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("so.PO_Date <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT p.Product_ID, p.Name AS product_name,
               ISNULL(p.Unit_Of_Measure, '') AS uom,
               SUM(si.Quantity) AS total_qty,
               COUNT(DISTINCT so.id) AS order_count
        FROM Intra_SalesOrder_Items si
        JOIN Intra_SalesOrder so
          ON CAST(so.PO_Number AS VARCHAR(100)) = CAST(si.PO_Number AS VARCHAR(100))
        LEFT JOIN Intra_SalesOrder_Products p ON p.Product_ID = si.Product_ID
        WHERE {where_sql}
        GROUP BY p.Product_ID, p.Name, p.Unit_Of_Measure
        ORDER BY total_qty DESC
    """
    with read_only() as cursor:
        cursor.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

