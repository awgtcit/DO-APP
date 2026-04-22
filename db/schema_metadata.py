"""Schema metadata lists for DB migration and bootstrap flows."""

# Core authentication/authorization tables - required for login to work
CORE_AUTH_TABLES = [
    "Intra_Users",
    "Intra_UserCredentials",
    "Isp_Status",
]

# Admin configuration and permission management tables
ADMIN_CONFIG_TABLES = [
    "Intra_Admin_ModuleConfig",
    "Intra_Admin_ModuleGroupAccess",
    "Intra_Admin_UserModuleAccess",
    "Intra_Admin_UserModuleRole",
    "Intra_Admin_ModuleRoleConfig",
    "Intra_Admin_WorkflowStatus",
    "Intra_Admin_WorkflowTransition",
    "Intra_Admin_RestrictedWords",
    "Intra_Admin_SMTPConfig",
    "Intra_Admin_WorkflowEmailSettings",
    "Intra_Admin_WorkflowEmailRecipient",
    "Intra_Admin_WorkflowEmailAttachment",
]

# Reference/master data tables
REFERENCE_TABLES = [
    "Intra_Department",
    "Intra_Designation",
    "Intra_Module_UserAccess",
    "Intra_Module_AccessGroup",
    "Intra_AnnouncementsSubMenu",
]

# Delivery Order tables in dependency order (parents before children)
DO_TABLES = [
    "Intra_SalesOrder_PointOfExit",
    "Intra_SalesOrder_Products",
    "Intra_SalesOrder_BillTo",
    "Intra_SalesOrder_AWTFZC_Customer",
    "Intra_SalesOrder_PricingPermission",
    "Intra_SalesOrder_UnitPrice",
    "Intra_SalesOrder_Forecast",
    "Intra_SalesOrder",
    "Intra_SalesOrder_Items",
    "Intra_SalesOrder_Approved_Attachments",
    "Intra_SalesOrder_Receipts",
    "Intra_SalesOrder_ReceiptItems",
]

# Operational/transactional tables (non-reference data)
TRANSACTION_TABLES = [
    "Intra_Announcements",
    "Intra_DMS_Permission",
    "Intra_TechFacility",
    "Intra_UserActivityLog",
    "Intra_DBLog",
]

# All tables for discovery/listing
ALL_TABLES = (CORE_AUTH_TABLES + ADMIN_CONFIG_TABLES + REFERENCE_TABLES +
              DO_TABLES + TRANSACTION_TABLES)

# Static/reference tables that should carry seed/master data during migration
MASTER_TABLES = (CORE_AUTH_TABLES + ADMIN_CONFIG_TABLES + REFERENCE_TABLES +
                 DO_TABLES)

# Operational tables that default to schema-only migration (no data copy)
SCHEMA_ONLY_TABLES = TRANSACTION_TABLES
