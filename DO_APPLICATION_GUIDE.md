# Delivery Orders (DO) Application — Complete Guide

> **Al Wahdania General Trading Co. LLC — Fujairah Branch**
>
> Internal web application for managing Sales/Delivery Orders, master data
> (Products, Customers), GRMS receipts, and reports.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Getting Started](#3-getting-started)
4. [Authentication & Login](#4-authentication--login)
5. [Role-Based Access Control (RBAC)](#5-role-based-access-control-rbac)
6. [Dashboard](#6-dashboard)
7. [Delivery Orders — Full Lifecycle](#7-delivery-orders--full-lifecycle)
8. [Management Section](#8-management-section)
   - [Products](#81-products)
   - [Customers (Bill To)](#82-customers-bill-to)
   - [GRMS (Goods Receipt)](#83-grms-goods-receipt)
   - [Reports](#84-reports)
9. [Admin Settings](#9-admin-settings)
10. [Restricted Words](#10-restricted-words)
11. [Database Schema](#11-database-schema)
12. [Configuration & Environment Variables](#12-configuration--environment-variables)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Overview

The **DO Application** is a Flask-based internal web application that digitalises the
Delivery Order workflow for Al Wahdania General Trading. It replaces legacy manual
processes with a role-controlled, multi-step order pipeline:

| Capability | Description |
|---|---|
| **Order Management** | Create, submit, approve, reject, confirm delivery orders |
| **Master Data** | Manage Products, Customers (Bill To / Ship To) |
| **GRMS** | View Goods Receipt / Material Shipment records |
| **Reporting** | Products-sold reports with date filters |
| **RBAC** | Granular role-based access per user per feature |
| **Restricted Words** | System-wide blocked-word enforcement on all text fields |
| **LDAP + DB Auth** | Active Directory login with database fallback |
| **PDF / Print** | Generate printable delivery orders with QR codes |

**Tech Stack:**

- **Backend:** Python 3.11+, Flask 3.x
- **Database:** Microsoft SQL Server (via pyodbc / ODBC Driver 17)
- **Auth:** LDAP (Active Directory) with DB fallback
- **Frontend:** Jinja2 templates, jQuery, DataTables, Select2, pdfmake
- **Design:** Custom CSS design system (green brand `#006633`, glassmorphism)

---

## 2. Architecture

```
DoApp/
├── run.py                  # Entry-point + Flask app factory (create_app)
├── config.py               # Config class (env vars)
├── auth/
│   ├── ldap_auth.py        # LDAP bind against AD
│   └── middleware.py        # @login_required, @role_required, check_session
├── controllers/
│   ├── auth_controller.py           # Login / logout / ISP acceptance
│   ├── dashboard_controller.py      # Main home dashboard
│   ├── delivery_order_controller.py # DO CRUD, status transitions, QR, print
│   ├── do_management_controller.py  # Products, Customers, GRMS, Reports
│   ├── admin_settings_controller.py # Users, modules, roles, restricted words
│   ├── webapp_controller.py         # Web Application hub menu
│   ├── dms_controller.py            # Document Management
│   ├── it_support_controller.py     # IT Support tickets
│   └── ...
├── services/
│   ├── do_permission_service.py     # Role resolution & permission checks
│   ├── delivery_order_service.py    # DO business logic
│   ├── admin_settings_service.py    # Module roles, restricted words
│   ├── do_email_service.py          # Email notifications for DO events
│   ├── do_pdf_service.py            # PDF generation
│   └── ...
├── repos/
│   ├── delivery_order_repo.py       # SQL queries for DO, products, customers
│   ├── admin_settings_repo.py       # SQL queries for admin config, roles
│   └── user_repo.py                 # User queries, role resolution
├── rules/                           # Validation rules
├── templates/
│   ├── base.html                    # Master layout (sidebar + topbar)
│   ├── delivery_orders/
│   │   ├── dashboard.html           # KPI cards + Management section
│   │   ├── create.html / edit.html  # Order form
│   │   ├── order_list.html          # Order listing with filters
│   │   ├── detail.html              # Order detail view
│   │   ├── print.html / print_pdf.html
│   │   └── manage/
│   │       ├── products.html / product_form.html
│   │       ├── customers.html / customer_form.html
│   │       ├── grms.html / grms_detail.html
│   │       └── reports.html
│   └── admin_settings/
├── static/
│   ├── css/app.css                  # Design system tokens & components
│   └── img/
├── db/                              # Database connection helpers
└── migrations/                      # SQL migration scripts
```

### Request Flow

```
Browser → Flask → check_session (middleware) → Blueprint Route
  ↓
  @login_required → @role_required (optional)
  ↓
  Controller → Service (business logic) → Repo (SQL Server)
  ↓
  render_template() with permission context from get_do_context()
```

---

## 3. Getting Started

### Prerequisites

- Python 3.11+
- Microsoft ODBC Driver 17 for SQL Server
- SQL Server instance with the required tables
- (Optional) Active Directory for LDAP authentication

### Setup

```powershell
cd DoApp

# 1. Create & activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
.\setup_credentials.ps1
# This sets: DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, LDAP_SERVER, SMTP_HOST, etc.

# 4. Run the application
$env:FLASK_DEBUG = "1"
python run.py
# → Server starts on http://localhost:5080
```

### Required Environment Variables

| Variable | Description | Required |
|---|---|---|
| `DB_SERVER` | SQL Server host | ✅ |
| `DB_NAME` | Database name | ✅ |
| `DB_USER` | SQL login user | ✅ |
| `DB_PASSWORD` | SQL login password | ✅ |
| `LDAP_SERVER` | AD server for LDAP auth | Optional |
| `LDAP_PORT` | LDAP port (default 389) | Optional |
| `LDAP_BASE_DN` | AD base DN | Optional |
| `SMTP_HOST` | Mail server for notifications | Optional |
| `SMTP_USER` | SMTP username | Optional |
| `SMTP_PASSWORD` | SMTP password | Optional |
| `FLASK_SECRET_KEY` | Session signing key | Auto-generated |

---

## 4. Authentication & Login

### Login Flow

1. User enters **username** and **password** on `/auth/login`
2. System attempts **LDAP bind** against configured AD domains:
   - `@moderntobacco.ae`
   - `@universal.moderntobacco.ae`
   - `@alwahdania.com`
3. If LDAP fails, falls back to **database authentication** (hashed password in `Intra_Users`)
4. On success, the session is populated:
   - `email`, `emp_id`, `user_name`, `department_id`, `group_id`
   - `roles` — computed from DMS permissions, module access groups, and GroupID
5. If ISP (Information Security Policy) has not been accepted, user is redirected to `/auth/isp`
6. After ISP acceptance, user lands on the **Delivery Orders Dashboard**

### Session

- Cookie-based (Flask `session`)
- `SESSION_COOKIE_HTTPONLY = True`, `SAMESITE = Lax`
- Timeout: 30 minutes (configurable via `SESSION_LIFETIME` env var)
- All routes except login, ISP, and static files require authentication

---

## 5. Role-Based Access Control (RBAC)

The DO module uses a **two-tier role system**:

### Tier 1: Order-Flow Roles

These control what a user can do with delivery orders:

| Role Key | Display Name | Capabilities |
|---|---|---|
| `do_creator` | Creator | Create orders, edit own drafts, submit, resubmit rejected |
| `do_finance` | Finance | Agree prices, request attachments, reject orders |
| `do_logistics` | Logistics | Confirm orders after price agreement, cancel |
| `do_approver` | Approver | **Full access** — can do everything above + manage all sections |

### Tier 2: Management Roles

These control access to individual management pages independently:

| Role Key | Display Name | Grants Access To |
|---|---|---|
| `do_mgmt_products` | Manage Products | Products list, create, edit |
| `do_mgmt_customers` | Manage Customers | Customers list, create, edit |
| `do_mgmt_grms` | Manage GRMS | GRMS receipts list, detail view |
| `do_mgmt_reports` | Manage Reports | Reports page with date filters |

> **Note:** The `do_approver` role automatically grants access to ALL management
> sections. Other roles must be explicitly assigned.

### Role Resolution Priority

1. **Per-module role** from `Intra_Admin_UserModuleRole` table (most specific, admin-assigned)
2. **System admin** (`GroupID = 1` or `it_admin` role) → automatically becomes `do_approver`
3. **Fallback** → `do_creator`

### Dashboard Visibility Rules

| User Has | Sees |
|---|---|
| Any order-flow role (`do_creator`, `do_finance`, `do_logistics`, `do_approver`) | KPI cards, Overview, New Order / View Orders buttons |
| Any management role (`do_mgmt_products`, etc.) | Management section with only their permitted buttons |
| Only management roles (no order-flow role) | **Only** Management section; KPI dashboard is hidden |
| `do_approver` | Everything (full dashboard + all management buttons) |

### How to Assign Roles

1. Go to **Admin Settings → Modules**
2. Click **Access** next to "Delivery Orders"
3. In the **Per-Module Roles** section:
   - Select a user from the dropdown
   - Check the roles you want to assign (e.g. `Manage Products`, `Finance`)
   - Click **Save**

---

## 6. Dashboard

**URL:** `/delivery-orders/`

The dashboard is the landing page of the DO module. It displays:

### Company Banner
- Company logo and name at the top

### KPI Cards (visible if user has order-flow role)
- **Total Orders** — count of all orders, links to full order list
- **Draft Orders** — orders in DRAFT status
- **Submitted Orders** — orders pending review
- **Confirmed Orders** — approved and confirmed orders
- **Price Agreed** — (visible to Finance/Logistics/Approver only)
- **Need Attachment** — (visible to Finance/Logistics/Approver only)

Each card shows the count, a percentage bar relative to total, and links to the
filtered order list.

### Overview Section (visible if user has order-flow role)
- **Rejected** count with percentage
- **Cancelled** count with percentage

### Management Section (visible per role)
Shows only the buttons the user has been granted:
- **Products** — requires `do_mgmt_products` or `do_approver`
- **Customers** — requires `do_mgmt_customers` or `do_approver`
- **GRMS** — requires `do_mgmt_grms` or `do_approver`
- **Reports** — requires `do_mgmt_reports` or `do_approver`

---

## 7. Delivery Orders — Full Lifecycle

### Order Statuses

```
DRAFT → SUBMITTED → PRICE AGREED → CONFIRMED
  ↕         ↓            ↓
  ↕      REJECTED     CANCELLED
  ↕         ↓
  ← ← ← ← ← (resubmit)

Any status → NEED ATTACHMENT → CONFIRMED
```

| Status | Description |
|---|---|
| `DRAFT` | Order created but not yet submitted |
| `SUBMITTED` | Order submitted for review |
| `PRICE AGREED` | Finance has agreed on the pricing |
| `CONFIRMED` | Order fully approved and confirmed |
| `NEED ATTACHMENT` | Additional documents required |
| `REJECTED` | Order rejected (can be resubmitted as draft) |
| `CANCELLED` | Order permanently cancelled |

### Status Transition Permissions

| From → To | Who Can Do It |
|---|---|
| DRAFT → SUBMITTED | Creator (owner) or Approver |
| DRAFT → CANCELLED | Creator (owner) or Approver |
| SUBMITTED → PRICE AGREED | Finance or Approver |
| SUBMITTED → NEED ATTACHMENT | Finance or Approver |
| SUBMITTED → REJECTED | Finance or Approver |
| PRICE AGREED → CONFIRMED | Logistics or Approver |
| PRICE AGREED → CANCELLED | Logistics or Approver |
| CONFIRMED → NEED ATTACHMENT | Finance or Approver |
| NEED ATTACHMENT → CONFIRMED | Logistics or Approver |
| REJECTED → DRAFT | Creator (owner) or Approver |

### Reject Reasons (predefined)

1. Bill to party change
2. Ship to party change
3. Loading date change
4. Product item change
5. Additional packing requirement
6. DO Revision
7. Price Not Agreed
8. Selling price is less than the cost price
9. Qty Shortage
10. Order Cancelled by Sales Manager
11. Unavailability of Vehicle

### Creating an Order

1. Click **+ New Order** on the dashboard
2. Fill in the required fields:
   - Date, Loading Date
   - On Behalf Of (Sales Manager)
   - Delivery Terms, Payment Terms
   - Transportation Mode
   - Bill To, Ship To (customer selection)
   - Point of Exit, Point of Discharge
   - Final Destination, Currency
   - Notify Party, Shipping Agent
3. All text fields are checked against **Restricted Words** (see [Section 10](#10-restricted-words))
4. Click **Save** → order is created in DRAFT status

### Order Detail View

Shows all order information including:
- Order header (DO number, dates, parties)
- Line items (products, quantities, prices)
- Status history / audit trail
- QR code for the order
- Attachments
- Available actions based on user role and current status

### Print / PDF

- **Print View:** `/delivery-orders/<id>/print` — browser print-friendly layout
- **PDF Export:** Generated server-side via `do_pdf_service.py`

---

## 8. Management Section

### 8.1 Products

**URL:** `/delivery-orders/manage/products`
**Required Role:** `do_mgmt_products` or `do_approver`

Manage the product master data used in delivery orders.

| Field | Description |
|---|---|
| Product ID | Unique identifier (e.g. SKU) |
| Name | Product name |
| Market | Target market |
| Unit of Measure | UOM (e.g. KG, TON, PCS) |
| Sales Manager | Assigned sales manager |

**Operations:**
- View all products in a DataTable with search/filter/export
- Create new product
- Edit existing product
- Duplicate product ID check (prevents duplicates)

### 8.2 Customers (Bill To)

**URL:** `/delivery-orders/manage/customers`
**Required Role:** `do_mgmt_customers` or `do_approver`

Manage customer master data. Customers are used as "Bill To" and "Ship To"
parties in delivery orders.

| Field | Description |
|---|---|
| Ahlaan Vendor Code | **Auto-generated** sequential number (e.g. 100000088) |
| SAP Code (from SAP) | External SAP customer code |
| Name | Customer / company name |
| Address | Full address |
| Postal Code | Postal / ZIP code |
| Country ISO Code | Country selection (searchable dropdown with Select2) |
| Region / State | Region or state |
| Contact Number | Phone number (digits, +, -, spaces only) |

**Features:**
- Ahlaan Vendor Code auto-increments from `MAX(SapCode) + 1`
- Country dropdown is searchable (Select2 with 120+ countries)
- Contact Number field only allows phone characters
- All fields are validated against **Restricted Words** (both client-side real-time and server-side)
- DataTable with export (Excel, CSV, PDF, Print, Copy)

### 8.3 GRMS (Goods Receipt)

**URL:** `/delivery-orders/manage/grms`
**Required Role:** `do_mgmt_grms` or `do_approver`

View Goods Receipt / Material Shipment records with:
- Status filter (ALL / specific statuses)
- Pagination (25 per page)
- Detail view for each receipt showing line items

### 8.4 Reports

**URL:** `/delivery-orders/manage/reports`
**Required Role:** `do_mgmt_reports` or `do_approver`

Products Sold Report:
- Filter by date range (From / To)
- Shows product quantities sold in the period

---

## 9. Admin Settings

**URL:** `/admin/settings/`
**Required Role:** `admin` or `it_admin`

### User Management
- Create, edit, delete users
- Set department, designation, group
- Reset passwords
- Manage DMS permissions (IT Admin, Uploader, Approver, Reviewer)
- Assign access groups

### Module Management
- Enable/disable application modules
- Configure group-based access per module
- Assign per-user per-module roles (see [Section 5](#5-role-based-access-control-rbac))
- Create custom roles for any module

### Restricted Words
- Add/remove words to the system-wide blocked list
- Applied to all text inputs across the application

### Workflow Management
- Configure status flows per module
- Define allowed transitions between statuses

---

## 10. Restricted Words

The application enforces a system-wide list of blocked words that cannot be entered
in any text field.

### How It Works

1. **Admin** adds words via Admin Settings → Restricted Words
2. Words are stored in the `Intra_Admin_RestrictedWords` table
3. Validation happens at **two levels**:

#### Client-Side (Real-Time)
- On page load, the blocked words list is fetched via AJAX from
  `/admin/settings/api/restricted-words-list`
- Every text input has `input` and `blur` event listeners
- If a blocked word is detected:
  - The field border turns red with a glow effect
  - An inline error message appears: "⚠ Contains blocked word: [word]"
  - Form submission is blocked (`e.preventDefault()`)
- The country dropdown (Select2) is also checked — if a blocked country is
  selected, it is automatically cleared

#### Server-Side (Backup)
- On form POST, the controller checks each text field using
  `check_text_for_restricted_words(text)` from `admin_settings_service.py`
- Uses word-boundary regex (`\b\w+\b`) to extract words and compare against
  the blocked set
- If blocked words are found, the form is re-rendered with a flash error message

### Fields Checked (Customer Form)
- SAP Code (from SAP)
- Name
- Address
- Postal Code
- Region / State
- Contact Number
- Country ISO Code (dropdown text)

### Fields Checked (Delivery Order Form)
- Payment Terms
- Point of Discharge
- Final Destination
- Notify Party
- Shipping Agent

---

## 11. Database Schema

### Core Tables

| Table | Purpose |
|---|---|
| `Intra_Users` | User accounts (EmpID, name, email, credentials) |
| `Intra_DMS_Permission` | DMS role permissions per user |
| `Intra_Module_AccessGroup` | Access groups (e.g. "Sales", "Finance") |
| `Intra_Module_UserAccess` | User ↔ access group mapping |
| `Intra_Admin_ModuleConfig` | Module definitions (id, module_key, display_name, enabled) |
| `Intra_Admin_UserModuleRole` | Per-user per-module role assignments |
| `Intra_Admin_RestrictedWords` | Blocked words list |

### Delivery Order Tables

| Table | Purpose |
|---|---|
| `Intra_SalesOrder` | Main delivery order header |
| `Intra_SalesOrder_Items` | Order line items (products, qty, price) |
| `Intra_SalesOrder_BillTo` | Customer master data (Bill To parties) |
| `Intra_SalesOrder_Products` | Product master data |
| `Intra_SalesOrder_Attachments` | File attachments for orders |
| `Intra_SalesOrder_StatusHistory` | Audit trail of status changes |
| `Intra_SalesOrder_GRMS` | Goods Receipt records |
| `Intra_SalesOrder_GRMS_Items` | GRMS line items |

### Key Columns — `Intra_SalesOrder_BillTo`

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK, auto-increment) | Primary key |
| `SapCode` | NVARCHAR | Ahlaan Vendor Code (auto-generated) |
| `SapCodeFromSAP` | NVARCHAR | External SAP code |
| `Name` | NVARCHAR | Customer name |
| `Address` | NVARCHAR | Address |
| `Postal_Code` | NVARCHAR | Postal code |
| `Country_ISO_Code` | NVARCHAR | ISO country code |
| `Region` | NVARCHAR | Region / state |
| `Contact_Number` | NVARCHAR | Phone number |
| `Status` | INT | Active (1) / Inactive (0) |
| `Created_on` | DATETIME | Creation timestamp |
| `Created_by` | INT | Creator employee ID |
| `Modified_on` | DATETIME | Last modified timestamp |
| `Modified_by` | INT | Last modifier employee ID |

### Key Columns — `Intra_Admin_UserModuleRole`

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK) | Primary key |
| `module_id` | INT (FK) | References `Intra_Admin_ModuleConfig.id` |
| `emp_id` | INT | Employee ID |
| `role_key` | VARCHAR | Role identifier (e.g. `do_mgmt_products`) |
| `assigned_by` | INT | Who assigned this role |
| `assigned_at` | DATETIME | When the role was assigned |

---

## 12. Configuration & Environment Variables

All configuration is loaded from environment variables via `config.py`:

```python
class Config:
    SECRET_KEY          # Flask session key (auto-generated if not set)
    DB_SERVER           # SQL Server host
    DB_NAME             # Database name
    DB_USER             # DB login
    DB_PASSWORD         # DB password
    DB_DRIVER           # ODBC driver (default: {ODBC Driver 17 for SQL Server})
    LDAP_SERVER         # AD server
    LDAP_PORT           # LDAP port (default: 389)
    LDAP_BASE_DN        # AD base DN
    LDAP_DOMAINS        # Comma-separated domain suffixes
    SMTP_HOST           # Mail server
    SMTP_USER           # SMTP username
    SMTP_PASSWORD       # SMTP password
    SMTP_PORT           # SMTP port (default: 587)
```

### Running in Debug Mode

```powershell
$env:FLASK_DEBUG = "1"
python run.py
```

This enables:
- Auto-reload on file changes
- Detailed error pages
- Debug logging to stdout

### Production

```powershell
# Use a proper WSGI server like Gunicorn or Waitress
waitress-serve --port=5080 "run:create_app()"
```

---

## 13. Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---|---|---|
| "Missing required environment variables" | `.env` not configured | Run `.\setup_credentials.ps1` |
| Port 5080 already in use | Old server process still running | `netstat -ano \| Select-String ":5080"` → `Stop-Process -Id <PID>` |
| Template changes not reflecting | Not running in debug mode | Set `$env:FLASK_DEBUG = "1"` and restart |
| "N/A" for Ahlaan Vendor Code | Stale server without code changes | Kill old process, restart with debug mode |
| LDAP login fails | Wrong domain suffix or AD unreachable | Check `LDAP_SERVER`, `LDAP_DOMAINS`; falls back to DB auth |
| Restricted words not blocking | Client-side JS not loaded | Check browser console for errors; server-side always validates |
| Management buttons not visible | User lacks management roles | Assign roles in Admin Settings → Modules → Delivery Orders → Access |
| "Permission denied" on management page | User has wrong role | Check user's assigned roles match the section they're accessing |
| Country dropdown not searchable | Select2 not loaded | Check CDN links in template; requires jQuery + Select2 CSS/JS |

### Logs

- Server logs print to stdout when running with `FLASK_DEBUG=1`
- Check `server.log` / `server2.log` for historical output
- Python errors include full traceback in debug mode

### Database Connectivity

The app uses two connection modes from `db/`:
- `read_only()` — for SELECT queries
- `transactional()` — for INSERT/UPDATE/DELETE with commit/rollback

Both use `pyodbc` with ODBC Driver 17 for SQL Server.

---

## Appendix: Route Map

| Route | Method | Controller | Description |
|---|---|---|---|
| `/auth/login` | GET/POST | `auth_controller` | Login page |
| `/auth/logout` | GET | `auth_controller` | Logout |
| `/auth/isp` | GET/POST | `auth_controller` | ISP acceptance |
| `/` | GET | `dashboard_controller` | Main home dashboard |
| `/delivery-orders/` | GET | `delivery_order_controller` | DO dashboard |
| `/delivery-orders/orders` | GET | `delivery_order_controller` | Order list |
| `/delivery-orders/create` | GET/POST | `delivery_order_controller` | Create order |
| `/delivery-orders/<id>/edit` | GET/POST | `delivery_order_controller` | Edit order |
| `/delivery-orders/<id>` | GET | `delivery_order_controller` | Order detail |
| `/delivery-orders/<id>/status` | POST | `delivery_order_controller` | Change status |
| `/delivery-orders/<id>/items` | POST | `delivery_order_controller` | Add/remove items |
| `/delivery-orders/<id>/print` | GET | `delivery_order_controller` | Print view |
| `/delivery-orders/<id>/attachments` | POST | `delivery_order_controller` | Manage attachments |
| `/delivery-orders/manage/products` | GET | `do_management_controller` | Products list |
| `/delivery-orders/manage/products/create` | GET/POST | `do_management_controller` | Create product |
| `/delivery-orders/manage/products/<pk>/edit` | GET/POST | `do_management_controller` | Edit product |
| `/delivery-orders/manage/customers` | GET | `do_management_controller` | Customers list |
| `/delivery-orders/manage/customers/create` | GET/POST | `do_management_controller` | Create customer |
| `/delivery-orders/manage/customers/<pk>/edit` | GET/POST | `do_management_controller` | Edit customer |
| `/delivery-orders/manage/grms` | GET | `do_management_controller` | GRMS list |
| `/delivery-orders/manage/grms/<id>` | GET | `do_management_controller` | GRMS detail |
| `/delivery-orders/manage/reports` | GET | `do_management_controller` | Reports |
| `/admin/settings/` | GET | `admin_settings_controller` | Admin home |
| `/admin/settings/users` | GET | `admin_settings_controller` | User list |
| `/admin/settings/users/<id>/permissions` | GET/POST | `admin_settings_controller` | User permissions |
| `/admin/settings/modules` | GET | `admin_settings_controller` | Module list |
| `/admin/settings/modules/<id>/access` | GET/POST | `admin_settings_controller` | Module access & roles |
| `/admin/settings/restricted-words` | GET/POST | `admin_settings_controller` | Restricted words |

---

## Appendix: Available DO Roles Summary

```
delivery_orders module roles:
├── Order-Flow Roles
│   ├── do_creator        → Create orders, edit own, submit/resubmit
│   ├── do_finance        → Price agree, reject, request attachments
│   ├── do_logistics      → Confirm orders, cancel after price agreed
│   └── do_approver       → Full access (all of the above + management)
│
└── Management Roles (independent per-section access)
    ├── do_mgmt_products  → Products list/create/edit
    ├── do_mgmt_customers → Customers list/create/edit
    ├── do_mgmt_grms      → GRMS receipts list/detail
    └── do_mgmt_reports   → Reports page
```

A user can have **multiple roles**. For example, a user with `do_creator` +
`do_mgmt_products` can create orders AND manage products, but cannot access
Customers, GRMS, or Reports management pages.

---

*Document generated: March 2026*
*Application: DoApp v2.0 — Delivery Orders Management System*
