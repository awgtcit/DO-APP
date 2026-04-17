# Intranet Portal — Full Modernization Report

---

## Section A — Feature & Entity Map

### A.1 Feature List (Reverse-Engineered)

| # | Feature | Legacy Files | Status |
|---|---------|-------------|--------|
| 1 | **Authentication (LDAP + DB fallback)** | `loginUser.php`, `checkUser.php`, `Includes/Class/Login.php`, `Includes/Class/session.php` | Active |
| 2 | **Information Security Policy (ISP) Gate** | `Information_security_policy.php`, `Includes/Database/Tables/ispStatus.php` | Active |
| 3 | **Dashboard Shell** | `Dashboard/index.php`, `Dashboard/HOME.php` | Active |
| 4 | **Company Announcements** | `Dashboard/Company_Announcements.php`, `Dashboard/Announcements/` | Active |
| 5 | **Document Management System (DMS)** | `Dashboard/Document_Management_System.php`, `Dashboard/DMS/` | Active |
| 6 | **IT Support Ticketing** | `Dashboard/IT_Support.php`, `Dashboard/IT_Support/` | Active |
| 7 | **Sales Order Management** | `Dashboard/WebApplication/SalesOrder/` | Active |
| 8 | **Tech Facility Requests** | `Includes/Database/Tables/IntraTechFacility.php` | Active |
| 9 | **Employee Forum** | `Dashboard/EmployeeForum/` | Active |
| 10 | **New User Registration** | `Dashboard/New_User_Reg.php` | Active |
| 11 | **Time & Attendance** | `Includes/Database/Tables/IntraTimeAttendanceOffice.php` | Active |
| 12 | **Email Notifications** | `Dashboard/mail.php` (PHPMailer + Office365 SMTP) | Active |
| 13 | **Audit Logging** | `Includes/Database/Tables/IntraUserActivityLog.php`, `IntraDBLog.php` | Active |
| 14 | **ISP Admin** | `Dashboard/ISP_Status.php` | Active |
| 15 | **Web Applications Hub** | `Dashboard/Web_Application.php` | Active |

### A.2 Entity Map (27 Tables)

**Core Entities:**
- `Intra_Users` — Employee master (EmpID, names, email, department, designation)
- `Intra_UserCredentials` — Login credentials (username, MD5 password, EmpID FK)
- `Intra_Department` — Department master
- `Isp_Status` — ISP acceptance tracking

**DMS Module (8 tables):**
- `Intra_DMS_Document` — Main documents (type, dept, dates, confidentiality, status)
- `Intra_DMS_DocumentAttachment` — File attachments per document
- `Intra_DMS_Permission` — Role-based access (Uploader/Approver/Reviewer1/Reviewer2/ITAdmin)
- `Intra_DMS_Department`, `_DocumentType`, `_DocumentStatus`, `_Company`, `_Party` — Lookup tables

**Sales Order Module (10 tables):**
- `Intra_SalesOrder` — Orders (PO number, dates, terms, status workflow)
- `Intra_SalesOrder_Items` — Line items per order
- `Intra_SalesOrder_Products` — Product catalog
- `Intra_SalesOrder_BillTo` — Billing addresses (SAP codes)
- `Intra_SalesOrder_ShipTo` — Shipping addresses
- `Intra_SalesOrder_PointOfExit` — Exit points
- `Intra_SalesOrder_Receipts` — Receipt headers
- `Intra_SalesOrder_ReceiptItems` — Receipt line items
- `Intra_SalesOrder_UnitPrice`, `_ProductPrice`, `_PricingPermission`, `_ApprovedAttachment`

**Support:**
- `Intra_ITSupport` — IT tickets
- `Intra_TechFacility` — Facility requests (with hex tracking)
- `Intra_TechFacility_Comments` — Ticket comments
- `Intra_Announcements` + `_AnnouncementsSubMenu` — Company communications
- `Intra_TimeAttendanceOffice` — Clock in/out records

**Audit:**
- `Intra_UserActivityLog` — User activity tracking
- `Intra_DBLog` — Every SQL mutation logged

---

## Section B — Security Findings

### CRITICAL (5)
1. **SA Account Usage** — Production DB accessed with `sa` (sysadmin). All credentials in `Includes/config.php`.
2. **SQL Injection in Auth** — `loginUser.php` concatenates user input into SQL: `WHERE CredEmail='{$Email}'`
3. **Hardcoded Credentials** — 5 credential sets plaintext in config: DB (sa/MTC@123456), FTDP (finger/finger@123), LDAP, SMTP (Puj49474), SAP (Mtc@123)
4. **Zero Parameterized Queries** — All 120+ SQL queries use string interpolation
5. **MD5 Password Hashing** — `md5()` used for password comparison, no salt

### HIGH (10)
1. Path traversal risk in DMS file uploads
2. No CSRF protection on any form
3. Session fixation (no regeneration after login)
4. Error disclosure (`die(print_r(sqlsrv_errors()))`)
5. 5-minute session timeout is extremely short AND uses sliding window
6. Authorization by hardcoded email checks (not role-based)
7. POST-only auth gate easily bypassed
8. `DataLog/` writes plaintext login attempts with hashed passwords
9. No input sanitization on announcements (XSS via HTML body)
10. No rate limiting on login attempts

### MEDIUM (8)
1. `magic_quotes_gpc` checks (deprecated since PHP 5.4)
2. Custom escape function instead of parameterized queries
3. No password complexity requirements
4. Console.log leaking data in JS
5. Mixed HTTP/HTTPS handling
6. No Content-Security-Policy headers
7. Upload directories under web root
8. DB connection errors exposed to users

---

## Section C — UX Specification

### C.1 Information Architecture

```
┌─────────────────────────────────────────────────┐
│  TOP BAR: Logo | Search | Notifications | User  │
├────────┬────────────────────────────────────────┤
│        │                                        │
│  SIDE  │   MAIN CONTENT AREA                    │
│  NAV   │                                        │
│        │   ┌──────────────────────────────────┐  │
│  Home  │   │  Page Header + Breadcrumbs       │  │
│  DMS   │   ├──────────────────────────────────┤  │
│  Sales │   │  Filters / Actions Bar           │  │
│  IT    │   ├──────────────────────────────────┤  │
│  Facil │   │  Data Table / Cards / Content    │  │
│  Annc  │   │                                  │  │
│  Time  │   │                                  │  │
│  Users │   ├──────────────────────────────────┤  │
│  Audit │   │  Pagination                      │  │
│        │   └──────────────────────────────────┘  │
│        │                                        │
├────────┴────────────────────────────────────────┤
│  FOOTER: Version | Copyright                     │
└─────────────────────────────────────────────────┘
```

### C.2 Screen Breakdown

| Screen | Components | Interaction |
|--------|-----------|-------------|
| **Login** | Centered card, email+password, "Remember me", error toast | Submit → loading spinner → redirect |
| **ISP Acceptance** | Full-page policy text, "I Accept" button | Must accept before dashboard access |
| **Dashboard Home** | KPI cards (tickets, orders, docs), recent activity feed, charts | Click card → navigate to module |
| **Announcements** | Category tabs, card list, detail modal | Filter by category, search, create modal |
| **DMS** | Table with filters (dept, type, status), detail drawer, upload modal | CRUD + workflow status transitions |
| **IT Support** | Ticket list, priority badges, detail view, comment thread | Create ticket, add comments, change status |
| **Sales Orders** | Table with date range filter, status pills, detail page with items | Full CRUD, status workflow, receipt tracking |
| **Facility Requests** | Kanban or table view, priority tags, comment thread | Create, assign, status toggle, comment |
| **Time & Attendance** | Calendar view + table, date range picker | View/edit attendance records |
| **User Management** | User table, create/edit form, department filter | CRUD users, assign departments |
| **Audit Log** | Searchable table, date range, user filter | Read-only, export capability |

### C.3 Component System

**Atoms:** Button (primary/secondary/danger/ghost), Input, Select, Checkbox, Badge, Avatar, Icon, Spinner
**Molecules:** Form Group, Search Bar, Filter Chip, Status Pill, Toast, Empty State, Skeleton Loader, Stat Card
**Organisms:** Data Table, Detail Drawer, Modal Dialog, Comment Thread, File Upload Zone, Nav Sidebar, Top Bar
**Templates:** List Page, Detail Page, Form Page, Dashboard Page, Auth Page

### C.4 Design System

| Token | Value |
|-------|-------|
| **Primary** | `#2563EB` (Blue 600) |
| **Success** | `#16A34A` (Green 600) |
| **Warning** | `#D97706` (Amber 600) |
| **Danger** | `#DC2626` (Red 600) |
| **Neutral 50–900** | Slate scale |
| **Font** | Inter (body), JetBrains Mono (code) |
| **Base size** | 14px body, 1.5 line-height |
| **Spacing scale** | 4px base (4, 8, 12, 16, 20, 24, 32, 40, 48, 64) |
| **Border radius** | 6px (sm), 8px (md), 12px (lg) |
| **Shadows** | `0 1px 2px rgba(0,0,0,.05)` (sm) → `0 20px 25px rgba(0,0,0,.1)` (xl) |
| **Grid** | 12-column, 24px gutter, max-width 1440px |
| **Breakpoints** | 640 / 768 / 1024 / 1280 / 1536px |

---

## Section D — Flask Architecture & File Tree

```
app/
├── run.py                    # Entry point
├── config.py                 # Env-based configuration
├── requirements.txt          # Dependencies
├── setup_credentials.ps1     # PowerShell credential setup
├── auth/
│   ├── __init__.py
│   ├── middleware.py          # Auth middleware (login_required, role_required)
│   └── ldap_auth.py          # LDAP authentication helper
├── controllers/
│   ├── __init__.py
│   ├── auth_controller.py     # Login/Logout/ISP endpoints
│   ├── dashboard_controller.py
│   ├── it_support_controller.py  # First full module
│   └── ...
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── it_support_service.py
│   └── ...
├── rules/
│   ├── __init__.py
│   ├── auth_rules.py
│   ├── it_support_rules.py
│   └── ...
├── repos/
│   ├── __init__.py
│   ├── user_repo.py
│   ├── it_support_repo.py
│   └── ...
├── db/
│   ├── __init__.py
│   ├── connection.py          # pyodbc connection helper
│   └── transaction.py         # Transaction context manager
├── audit/
│   ├── __init__.py
│   └── logger.py              # Audit logging to DB
├── templates/
│   ├── base.html              # Master layout (sidebar + topbar)
│   ├── auth/
│   │   ├── login.html
│   │   └── isp_accept.html
│   ├── dashboard/
│   │   └── home.html
│   └── it_support/
│       ├── list.html
│       ├── detail.html
│       └── create.html
└── static/
    ├── css/
    │   └── app.css            # Modern design system
    ├── js/
    │   └── app.js             # Client interactions
    └── img/
```
