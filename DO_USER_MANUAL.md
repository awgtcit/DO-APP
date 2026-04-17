# 📘 Delivery Orders Application — User Manual

**Application:** AWGTC Delivery Orders Management System  
**Version:** 1.0  
**Last Updated:** June 2025

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
   - 2.1 [Accessing the Application](#21-accessing-the-application)
   - 2.2 [Logging In](#22-logging-in)
   - 2.3 [First-Time Login (ISP Acceptance)](#23-first-time-login-isp-acceptance)
3. [Understanding User Roles](#3-understanding-user-roles)
   - 3.1 [Order Workflow Roles](#31-order-workflow-roles)
   - 3.2 [Management Roles](#32-management-roles)
   - 3.3 [Administrator Roles](#33-administrator-roles)
   - 3.4 [Role Visibility Summary](#34-role-visibility-summary)
4. [Dashboard](#4-dashboard)
   - 4.1 [KPI Cards](#41-kpi-cards)
   - 4.2 [Overview Section](#42-overview-section)
   - 4.3 [Quick Actions](#43-quick-actions)
   - 4.4 [Management Section](#44-management-section)
5. [Delivery Orders — Full Workflow](#5-delivery-orders--full-workflow)
   - 5.1 [Creating a New Delivery Order](#51-creating-a-new-delivery-order)
   - 5.2 [Managing Line Items](#52-managing-line-items)
   - 5.3 [Managing Attachments](#53-managing-attachments)
   - 5.4 [Editing a Delivery Order](#54-editing-a-delivery-order)
   - 5.5 [Viewing Order Details](#55-viewing-order-details)
   - 5.6 [QR Code](#56-qr-code)
   - 5.7 [Printing a Delivery Order](#57-printing-a-delivery-order)
6. [Order Status Workflow](#6-order-status-workflow)
   - 6.1 [Status Definitions](#61-status-definitions)
   - 6.2 [Status Transitions](#62-status-transitions)
   - 6.3 [Rejecting an Order](#63-rejecting-an-order)
7. [Order List & Filtering](#7-order-list--filtering)
   - 7.1 [Viewing All Orders](#71-viewing-all-orders)
   - 7.2 [Filtering by Status](#72-filtering-by-status)
   - 7.3 [Searching Orders](#73-searching-orders)
   - 7.4 [Pagination](#74-pagination)
8. [Management Section](#8-management-section)
   - 8.1 [Products Management](#81-products-management)
   - 8.2 [Customers Management](#82-customers-management)
   - 8.3 [GRMS (Goods Receipt Management)](#83-grms-goods-receipt-management)
   - 8.4 [Reports](#84-reports)
9. [Admin Settings (Administrators Only)](#9-admin-settings-administrators-only)
   - 9.1 [User Management](#91-user-management)
   - 9.2 [Module Management](#92-module-management)
   - 9.3 [Module Access & Role Assignment](#93-module-access--role-assignment)
   - 9.4 [Restricted Words](#94-restricted-words)
   - 9.5 [Workflow Configuration](#95-workflow-configuration)
10. [Input Validation & Restricted Words](#10-input-validation--restricted-words)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)

---

## 1. Introduction

The **Delivery Orders Management System** is a web-based application built to streamline the creation, approval, and tracking of delivery orders within the organization. It provides:

- **End-to-end delivery order workflow** — from draft creation to final confirmation
- **Role-based access control** — each user sees only the features they need
- **Product & customer master data management** — maintain your product catalog and customer database
- **Goods receipt tracking** — view and manage GRMS receipts
- **Reporting** — generate reports on products sold over a date range
- **Administrative controls** — manage users, roles, modules, workflows, and restricted words

The application integrates with your organization's **Active Directory (LDAP)** for authentication, ensuring a seamless single sign-on experience.

---

## 2. Getting Started

### 2.1 Accessing the Application

Open your web browser and navigate to the application URL provided by your IT department. The application is compatible with all modern browsers (Chrome, Edge, Firefox, Safari).

### 2.2 Logging In

1. On the **Login** page, enter your **Username** and **Password**.
2. Click **Sign In**.
3. The system will first attempt to authenticate using your corporate Active Directory (AD) credentials. If AD is unavailable, it will fall back to the local database credentials.

> **Tip:** Your username is typically the same as your corporate/AD username.

If your credentials are incorrect, you will see an error message. Contact your administrator if you are locked out or have forgotten your password.

### 2.3 First-Time Login (ISP Acceptance)

On your first login, you may be required to accept the **Information Security Policy (ISP)**. This is a one-time acknowledgment. Read the policy carefully and click **Accept** to proceed.

---

## 3. Understanding User Roles

The application uses a **role-based access control** system. Your assigned role(s) determine which features and sections are visible to you.

### 3.1 Order Workflow Roles

These roles are involved in the delivery order lifecycle:

| Role | Description |
|------|-------------|
| **DO Creator** | Can create new delivery orders, edit drafts, submit orders for review, and re-submit rejected orders. |
| **DO Finance** | Reviews submitted orders. Can mark as **Price Agreed**, request **Need Attachment**, or **Reject** orders. |
| **DO Logistics** | Handles confirmed orders. Can mark orders as **Confirmed**, or **Cancelled**. Processes orders marked **Need Attachment**. |
| **DO Approver** | Has full visibility and can perform any order action. System administrators are automatically treated as approvers. |

### 3.2 Management Roles

These roles grant access to specific management sections on the dashboard:

| Role | Access Granted |
|------|---------------|
| **Manage Products** | Add, edit, and view the product catalog. |
| **Manage Customers** | Add, edit, and view the customer database. |
| **Manage GRMS** | View goods receipt records and details. |
| **Manage Reports** | Generate and view delivery order reports. |

> **Note:** A user with only management roles (and no order workflow roles) will see only the Management section on the dashboard — the KPI cards and order overview will be hidden.

### 3.3 Administrator Roles

| Role | Description |
|------|-------------|
| **Admin** | Full system access including user management, module configuration, workflow setup, and all DO features. |
| **IT Admin** | Same administrative capabilities as Admin for system configuration. |

### 3.4 Role Visibility Summary

| Dashboard Section | Who Can See It |
|-------------------|----------------|
| KPI Cards (Total Orders, Pending, etc.) | Users with any order workflow role (Creator, Finance, Logistics, Approver) or Admins |
| Overview (status breakdown, recent orders) | Users with any order workflow role or Admins |
| "New Order" Button | Users with Creator or Approver role |
| Management Section | Users with any management role or Admins |
| Products Button | Users with Manage Products role or Admins |
| Customers Button | Users with Manage Customers role or Admins |
| GRMS Button | Users with Manage GRMS role or Admins |
| Reports Button | Users with Manage Reports role or Admins |
| Admin Settings (sidebar) | Admins and IT Admins only |

---

## 4. Dashboard

The **Dashboard** is the home screen of the application. Its content adapts based on your assigned roles.

### 4.1 KPI Cards

If you have an order workflow role, you will see key performance indicator (KPI) cards at the top of the dashboard:

| KPI Card | Description |
|----------|-------------|
| **Total Orders** | The total number of delivery orders in the system. |
| **Pending Orders** | Orders awaiting action (not yet in a terminal status). |
| **Confirmed Orders** | Orders that have been fully confirmed. |
| **Rejected Orders** | Orders that have been rejected. |

Each card shows the current count, helping you quickly assess the workload.

### 4.2 Overview Section

Below the KPI cards, the **Overview** section provides:

- **Status breakdown** — A visual summary of how many orders are in each status (Draft, Submitted, Price Agreed, Confirmed, etc.).
- **Recent activity** — Quick access to recently created or updated orders.

### 4.3 Quick Actions

- **📋 View Orders** — Opens the full order list with filtering and search capabilities.
- **➕ New Order** — Creates a new delivery order (visible only to Creators and Approvers).

### 4.4 Management Section

If you have any management role, a **Management** section appears on the dashboard with buttons for:

- **📦 Products** — Manage the product catalog
- **👥 Customers** — Manage the customer database
- **📋 GRMS** — View goods receipt records
- **📊 Reports** — Generate reports

Each button is only visible if you have the corresponding management role.

---

## 5. Delivery Orders — Full Workflow

### 5.1 Creating a New Delivery Order

1. From the Dashboard, click the **➕ New Order** button, or navigate to **Delivery Orders → New Order**.
2. Fill in the required fields on the order form:

| Field | Description | Required |
|-------|-------------|----------|
| **PO Date** | The purchase order date. | ✅ |
| **On Behalf Of** | The person or department on whose behalf the order is placed. | ✅ |
| **Loading Date** | When the goods should be loaded. | ✅ |
| **Delivery Terms** | The agreed delivery terms (e.g., FOB, CIF). | ✅ |
| **Payment Terms** | How the customer will pay. | ✅ |
| **Transportation Mode** | Method of transportation (e.g., Sea, Air, Land). | ✅ |
| **Bill To** | The billing address/customer. Select from the dropdown. | ✅ |
| **Ship To** | The shipping address/customer. Select from the dropdown. | ✅ |
| **Point of Exit** | Where the goods leave your facility. | ✅ |
| **Point of Discharge** | Where the goods arrive at the destination. | ✅ |
| **Final Destination** | The ultimate destination of the goods. | ✅ |
| **Currency** | The transaction currency. | ✅ |
| **Notify Party** | The party to be notified upon delivery. | ✅ |
| **Shipping Agent** | The agent or company handling shipping. | ✅ |

3. Click **Save as Draft** to save the order without submitting it, or **Submit** to send it for review.

> **Important:** All text fields are validated against **restricted words**. If any field contains a restricted word, the system will block the submission and display a warning message. See [Section 10](#10-input-validation--restricted-words) for details.

### 5.2 Managing Line Items

After creating a delivery order, you can add products (line items) to it:

1. Open the delivery order detail page.
2. In the **Line Items** section, click **Add Item**.
3. Select a **Product** from the dropdown and enter the **Quantity**, **Unit Price**, and any other required fields.
4. Click **Save** to add the item.
5. To remove an item, click the **Delete** icon next to the item row.

> Line items can only be added/modified when the order is in **Draft** or editable status.

### 5.3 Managing Attachments

You can attach supporting documents (invoices, packing lists, certificates, etc.) to a delivery order:

1. Open the delivery order detail page.
2. In the **Attachments** section, click **Upload**.
3. Select the file from your computer and click **Upload**.
4. To remove an attachment, click the **Delete** icon next to it.

> Attachments are particularly important when an order is marked **Need Attachment** — the required documents must be uploaded before the order can proceed.

### 5.4 Editing a Delivery Order

1. Navigate to the order you want to edit.
2. Click the **Edit** button (available only when the order is in **Draft** status or has been returned/rejected).
3. Modify the fields as needed.
4. Click **Save** to update the order.

> **Note:** You can only edit orders that you created (or if you have Approver/Admin access).

### 5.5 Viewing Order Details

1. From the **Order List** or the **Dashboard**, click on any order number or the **View** button.
2. The detail page shows:
   - **Order header information** — all the fields from the creation form
   - **Line items** — the list of products in the order
   - **Attachments** — uploaded documents
   - **Status history** — the current status and available actions
   - **QR Code** — a scannable QR code for quick access

### 5.6 QR Code

Each delivery order has a unique **QR Code** that links directly to the order detail page. You can:
- View the QR code on the order detail page.
- Download it as a PNG image.
- Include it in printed documents for quick scanning.

### 5.7 Printing a Delivery Order

1. Open the order detail page.
2. Click the **Print** button.
3. A printer-friendly version of the delivery order will open in a new window.
4. Use your browser's print dialog (**Ctrl + P**) to print or save as PDF.

The printed view includes all order header information, line items, and the QR code.

---

## 6. Order Status Workflow

### 6.1 Status Definitions

| Status | Description | Terminal? |
|--------|-------------|-----------|
| **DRAFT** | The order has been created but not yet submitted. It can still be edited freely. | No |
| **SUBMITTED** | The order has been submitted for review by the Finance team. | No |
| **PRICE AGREED** | Finance has reviewed and agreed on the pricing. Awaiting Logistics confirmation. | No |
| **CONFIRMED** | The order has been fully confirmed by Logistics and is ready for processing. | Yes |
| **REJECTED** | The order has been rejected by Finance (with a reason). Can be re-submitted after correction. | No |
| **CANCELLED** | The order has been cancelled by Logistics. | Yes |
| **NEED ATTACHMENT** | Additional documents are required. Finance can request this at various stages. | No |

### 6.2 Status Transitions

The following diagram shows how an order moves through statuses:

```
                                    ┌─────────────┐
                                    │    DRAFT     │
                                    └──────┬──────┘
                                           │ Submit (Creator)
                                           ▼
                                    ┌─────────────┐
                              ┌─────│  SUBMITTED   │─────┐
                              │     └──────┬──────┘      │
                              │            │              │
                    Reject    │  Price Agree│    Need      │
                   (Finance)  │   (Finance) │  Attachment  │
                              │            │   (Finance)   │
                              ▼            ▼              ▼
                       ┌──────────┐  ┌───────────┐  ┌────────────────┐
                       │ REJECTED │  │PRICE AGREED│  │NEED ATTACHMENT │
                       └────┬─────┘  └─────┬─────┘  └───────┬────────┘
                            │              │                 │
                   Re-submit│    Confirm   │       Confirm   │
                   (Creator)│  (Logistics) │     (Logistics) │
                            │              │                 │
                            ▼              ▼                 ▼
                       ┌──────────┐  ┌───────────┐    ┌───────────┐
                       │  DRAFT   │  │ CONFIRMED  │    │ CONFIRMED │
                       └──────────┘  └───────────┘    └───────────┘
                                           │
                                     Cancel│ (Logistics)
                                           ▼
                                    ┌───────────┐
                                    │ CANCELLED  │
                                    └───────────┘
```

**Transition Summary:**

| From | To | Who Can Do It |
|------|----|---------------|
| DRAFT | SUBMITTED | Creator / Approver |
| SUBMITTED | PRICE AGREED | Finance / Approver |
| SUBMITTED | NEED ATTACHMENT | Finance / Approver |
| SUBMITTED | REJECTED | Finance / Approver |
| PRICE AGREED | CONFIRMED | Logistics / Approver |
| PRICE AGREED | CANCELLED | Logistics / Approver |
| CONFIRMED | NEED ATTACHMENT | Finance / Approver |
| NEED ATTACHMENT | CONFIRMED | Logistics / Approver |
| REJECTED | DRAFT | Creator / Approver |

### 6.3 Rejecting an Order

When a Finance user rejects an order, they must select a **rejection reason** from the predefined list:

- Bill to party change
- Ship to party change
- Loading date change
- Product item change
- Additional packing requirement
- DO Revision
- Price Not Agreed
- Selling price is less than the cost price
- Qty Shortage
- Order Cancelled by Sales Manager
- Unavailability of Vehicle

The rejection reason is recorded and visible to the order creator so they can make corrections and re-submit.

---

## 7. Order List & Filtering

### 7.1 Viewing All Orders

Navigate to **Delivery Orders → Orders** (or click **View Orders** on the Dashboard). This displays a paginated table of all delivery orders you have access to.

### 7.2 Filtering by Status

At the top of the order list, you'll find **status filter tabs** (e.g., All, Draft, Submitted, Price Agreed, Confirmed, Rejected, Cancelled). Click a tab to show only orders in that status.

### 7.3 Searching Orders

Use the **search box** above the table to search by:
- Order number
- Customer name
- Bill To / Ship To details
- Any other visible column data

The search filters results in real time as you type.

### 7.4 Pagination

If there are many orders, the table is paginated. Use the page navigation controls at the bottom of the table to move between pages. You can also adjust the number of rows shown per page.

---

## 8. Management Section

The Management section provides tools for maintaining master data. Access is controlled by management roles — you will only see buttons for sections you are authorized to use.

### 8.1 Products Management

**Access Required:** Manage Products role

#### Viewing Products
1. From the Dashboard, click **📦 Products** in the Management section.
2. A table lists all products with columns: Product ID, Name, Market, UOM (Unit of Measure), and Sales Manager.

#### Adding a New Product
1. Click **Add Product**.
2. Fill in the form:

| Field | Description |
|-------|-------------|
| **Product ID** | A unique identifier for the product. |
| **Product Name** | The full name of the product. |
| **Market** | The target market for this product. |
| **UOM** | Unit of Measure (e.g., KG, MT, PCS). |
| **Sales Manager** | The assigned sales manager for this product. |

3. Click **Save**.

#### Editing a Product
1. In the product list, click the **Edit** button next to the product you want to modify.
2. Update the fields as needed.
3. Click **Save**.

### 8.2 Customers Management

**Access Required:** Manage Customers role

#### Viewing Customers
1. From the Dashboard, click **👥 Customers**.
2. A table lists all customers with their SAP Code, Name, Address, Country, Region, and Contact Number.

#### Adding a New Customer
1. Click **Add Customer**.
2. Fill in the form:

| Field | Description |
|-------|-------------|
| **SAP Code** | Auto-generated by the system. You do not need to enter this. |
| **SAP Code (from SAP)** | Optional. If the customer already has a code in SAP, enter it here. |
| **Customer Name** | The full legal name of the customer. |
| **Address** | The customer's physical address. |
| **Postal Code** | The postal/ZIP code. |
| **Country** | Select from the searchable dropdown. Start typing to filter countries. |
| **Region** | The region or state. |
| **Contact Number** | Phone number only (digits, +, -, spaces, and parentheses allowed). |

3. Click **Save**.

> **Note:** The **Country** field uses a searchable dropdown — simply start typing the country name and select from the filtered list.

> **Note:** The **Contact Number** field only accepts phone characters. Letters and special characters will be automatically removed.

#### Editing a Customer
1. In the customer list, click the **Edit** button.
2. Update the fields.
3. Click **Save**.

### 8.3 GRMS (Goods Receipt Management)

**Access Required:** Manage GRMS role

#### Viewing GRMS Records
1. From the Dashboard, click **📋 GRMS**.
2. A table lists all goods receipt records with status indicators.
3. Use the **status filter** to view records by status (e.g., Pending, Completed).
4. Use **pagination** controls to navigate through large lists.

#### Viewing GRMS Details
1. Click on a receipt number or the **View** button to see the full details.
2. The detail page shows:
   - Receipt header information
   - Line items with quantities and product details

### 8.4 Reports

**Access Required:** Manage Reports role

#### Products Sold Report
1. From the Dashboard, click **📊 Reports**.
2. Set the **Date From** and **Date To** range to define the reporting period.
3. Click **Generate Report**.
4. The report displays a table of products sold within the date range, including quantities and values.

> **Tip:** You can export or print the report using your browser's built-in print function (**Ctrl + P**).

---

## 9. Admin Settings (Administrators Only)

The **Admin Settings** section is accessible only to users with the **Admin** or **IT Admin** role. It is available from the sidebar navigation.

### 9.1 User Management

#### Viewing Users
Navigate to **Admin Settings → Users** to see a list of all system users with their name, email, department, designation, and role group.

#### Creating a New User
1. Click **Add User**.
2. Fill in the form:

| Field | Description |
|-------|-------------|
| **First Name** | User's first name. |
| **Last Name** | User's last name. |
| **Email** | User's email address. |
| **Username** | Login username (must be unique). |
| **Password** | Initial password for the user. |
| **Department** | Select from available departments. |
| **Designation** | Select from available designations. |
| **Group** | User group (e.g., Admin, Standard User). |

3. Click **Save**.

> The system will automatically assign the next available Employee ID.

#### Editing a User
1. Click the **Edit** button next to the user.
2. Modify any field except the password (password has a separate reset function).
3. Click **Save**.

#### Resetting a User's Password
1. Open the user's edit page.
2. In the **Reset Password** section, enter the new password.
3. Click **Reset Password**.

#### Deleting a User
1. Click the **Delete** button next to the user.
2. Confirm the deletion when prompted.

> **Warning:** Deleting a user is permanent and cannot be undone.

#### Managing User Permissions
1. Click the **Permissions** button next to the user.
2. Toggle the permission switches:
   - **IT Admin** — Grants administrative privileges
   - **Uploader** — Can upload documents
   - **Approver** — General approval capabilities
   - **Reviewer 1 / Reviewer 2** — Review-level permissions
3. Select **Access Groups** — determines which modules and features the user can access.
4. Click **Save Permissions**.

### 9.2 Module Management

Navigate to **Admin Settings → Modules** to see all available application modules.

- Each module shows its **name**, **status** (enabled/disabled), and an **action** column.
- Use the **Enable/Disable** toggle to turn modules on or off for the entire organization.
- When a module is disabled, it will not appear in the sidebar for any user.

### 9.3 Module Access & Role Assignment

This is the most powerful configuration section, where you control who has access to each module and what roles they hold.

1. Navigate to **Admin Settings → Modules**.
2. Click **Manage Access** next to the module you want to configure (e.g., "Delivery Orders").

#### Group Access
- Toggle access on/off for each user group.
- When a group is enabled, all users in that group can access the module.

#### Individual User Access
- Grant or revoke module access for specific users, overriding group settings.

#### Role Assignment
This is where you assign **specific roles** within a module:

1. In the **Roles** section, you'll see all available roles for the module.
2. For the **Delivery Orders** module, the available roles are:

| Role Key | Display Name | Category |
|----------|-------------|----------|
| `do_creator` | DO Creator | Order Workflow |
| `do_finance` | DO Finance | Order Workflow |
| `do_logistics` | DO Logistics | Order Workflow |
| `do_approver` | DO Approver | Order Workflow |
| `do_mgmt_products` | Manage Products | Management |
| `do_mgmt_customers` | Manage Customers | Management |
| `do_mgmt_grms` | Manage GRMS | Management |
| `do_mgmt_reports` | Manage Reports | Management |

3. To assign a role to a user:
   - Select the user from the dropdown.
   - Check the roles you want to assign.
   - Click **Save Roles**.

4. To revoke a role, uncheck it and save.

> **Important:** A user can have multiple roles. For example, a user can be both a DO Creator and a Manage Products user. They will see all features corresponding to their combined roles.

#### Adding Custom Roles
1. Scroll to the **Custom Roles** section.
2. Enter a **Role Key** (lowercase, underscores allowed) and a **Display Label**.
3. Click **Add Role**.

#### Deleting Custom Roles
- Click **Delete** next to any custom role to remove it.
- Built-in roles cannot be deleted.

### 9.4 Restricted Words

The system maintains a list of **restricted words** that cannot be used in any text field throughout the application.

Navigate to **Admin Settings → Restricted Words**.

#### Adding a Restricted Word
1. Type the word in the input field.
2. Click **Add Word**.
3. The word will now be blocked in all form text fields across the application.

#### Removing a Restricted Word
1. Click **Delete** next to the word you want to remove.
2. The word will no longer be blocked.

#### How Restricted Words Work
- When a user types in any text field, the system checks in **real time** (client-side) whether the text contains any restricted word.
- A warning message appears immediately if a restricted word is detected.
- On form submission, the server also validates all text fields and **blocks the submission** if any restricted word is found.
- This applies to delivery order fields (Payment Terms, Point of Discharge, Final Destination, Notify Party, Shipping Agent) and customer management fields.

### 9.5 Workflow Configuration

Navigate to **Admin Settings → Workflow** to view and configure the order workflow.

#### Viewing the Workflow
- The page displays all **statuses** and **transitions** for the selected module.
- Select a module from the dropdown (e.g., "Delivery Orders") to see its workflow.

#### Managing Statuses
- **Add Status:** Enter a status key (e.g., `IN_REVIEW`), display name, sort order, and whether it's a terminal status.
- **Edit Status:** Click Edit to change the display name, sort order, or terminal flag.
- **Delete Status:** Click Delete to remove a status and all its related transitions.

> **Warning:** Deleting a status also removes all transitions associated with it. This could break the workflow if orders are currently in that status.

#### Managing Transitions
- **Add Transition:** Define a From Status, To Status, and the Required Role.
- **Edit Transition:** Change the required role for an existing transition.
- **Delete Transition:** Remove a transition rule.

> Transitions define the rules of the workflow — who can move an order from one status to another.

---

## 10. Input Validation & Restricted Words

The application enforces several validation rules to ensure data quality:

### Required Fields
All required fields are marked and must be filled before submission. If a required field is empty, the form will not submit and you will see a validation message.

### Restricted Words
- Certain words are blocked across all text input fields.
- If you type a restricted word, a **red warning banner** will appear below the field: *"Restricted word detected: [word]. Please remove it before submitting."*
- The form **cannot be submitted** until all restricted words are removed.
- The list of restricted words is managed by administrators (see [Section 9.4](#94-restricted-words)).

### Contact Number Validation
- The **Contact Number** field in customer management only accepts phone characters:
  - Digits (0-9)
  - Plus sign (+)
  - Hyphens (-)
  - Spaces
  - Parentheses ( )
- All other characters (letters, special symbols) are automatically stripped when typed.

### Country Selection
- The **Country** field uses a searchable dropdown powered by **Select2**.
- Start typing the country name to filter the list.
- You must select a country from the list — free-text entry is not allowed.

---

## 11. Troubleshooting & FAQ

### Q: I can't see the Dashboard KPI cards or order overview.
**A:** Your account likely only has management roles (e.g., Manage Products, Manage Reports) and no order workflow roles. The KPI cards and order overview are only visible to users with order workflow roles (Creator, Finance, Logistics, Approver). Contact your administrator if you need order workflow access.

### Q: I don't see the "New Order" button.
**A:** The "New Order" button is only visible to users with the **DO Creator** or **DO Approver** role. If you need to create orders, ask your administrator to assign you the Creator role.

### Q: I can see the Dashboard but not the Management section.
**A:** The Management section is only visible to users with management roles. If you need access to Products, Customers, GRMS, or Reports, contact your administrator to assign the appropriate management role(s).

### Q: I get a "Restricted word detected" error when filling a form.
**A:** One of the words you've typed matches a word on the restricted list. Remove or rephrase the text. The warning will indicate which specific word was flagged. If you believe the word should be allowed, contact your administrator to review the restricted words list.

### Q: I can't edit an order.
**A:** Orders can only be edited when they are in **Draft** status. If the order has been submitted or moved to another status, it cannot be edited. If it was rejected, it can be returned to Draft status for editing.

### Q: I submitted an order but it was rejected. What do I do?
**A:** Open the rejected order to see the rejection reason. Click **Re-submit** to return it to Draft status, make the necessary corrections, and submit it again.

### Q: How do I reset my password?
**A:** Contact your administrator. They can reset your password from the Admin Settings → Users section.

### Q: The page is loading slowly or shows an error.
**A:** Try the following:
1. Refresh the page (**F5** or **Ctrl + R**).
2. Clear your browser cache (**Ctrl + Shift + Delete**).
3. Try a different browser.
4. If the problem persists, contact your IT support team.

### Q: Can I use the application on my mobile device?
**A:** The application is responsive and can be used on tablets and smartphones. However, for the best experience with data tables and forms, a desktop or laptop screen is recommended.

### Q: How do I export data?
**A:** Use your browser's print function (**Ctrl + P**) on any page to save it as a PDF. For the Reports section, generate the report first, then use the browser print to export.

---

## Quick Reference Card

| Action | Where to Find It | Role Required |
|--------|-------------------|---------------|
| Create a delivery order | Dashboard → New Order | Creator, Approver |
| View all orders | Dashboard → View Orders | Any order role |
| Submit a draft order | Order Detail → Submit | Creator, Approver |
| Approve pricing | Order Detail → Price Agreed | Finance, Approver |
| Reject an order | Order Detail → Reject | Finance, Approver |
| Confirm an order | Order Detail → Confirm | Logistics, Approver |
| Add line items | Order Detail → Line Items | Creator (Draft only) |
| Upload attachments | Order Detail → Attachments | Creator |
| Print an order | Order Detail → Print | Any order role |
| Manage products | Dashboard → Products | Manage Products |
| Manage customers | Dashboard → Customers | Manage Customers |
| View GRMS records | Dashboard → GRMS | Manage GRMS |
| Generate reports | Dashboard → Reports | Manage Reports |
| Manage users | Sidebar → Admin Settings → Users | Admin, IT Admin |
| Assign roles | Admin Settings → Modules → Access | Admin, IT Admin |
| Add restricted words | Admin Settings → Restricted Words | Admin, IT Admin |
| Configure workflow | Admin Settings → Workflow | Admin, IT Admin |

---

*© 2025 AWGTC — Delivery Orders Management System. All rights reserved.*
