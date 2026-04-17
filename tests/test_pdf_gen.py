"""Quick test: generate a PDF from an existing order and save to disk."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DB_SERVER", "172.50.35.75")
os.environ.setdefault("DB_NAME", "mtcintranet")
os.environ.setdefault("DB_USER", "sa")
os.environ.setdefault("DB_PASSWORD", "Admin@123")
os.environ.setdefault("SMTP_SERVER", "smtp.office365.com")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USER", "notification@awgtc.com")
os.environ.setdefault("SMTP_PASSWORD", "Eauth@2032")
os.environ.setdefault("FLASK_SECRET_KEY", "test")

from run import create_app
from repos.delivery_order_repo import get_order_by_id, get_order_items
from services.do_pdf_service import generate_order_pdf, pdf_filename, should_attach_pdf

app = create_app()
with app.app_context():
    # Try a few recent order IDs
    for oid in [6013, 6012, 6011, 6010]:
        order = get_order_by_id(oid)
        if order:
            po = order.get("PO_Number", "?")
            status = order.get("Status", "?")
            print(f"Order {oid}: PO={po}  Status={status}")
            order["line_items"] = get_order_items(po)
            print(f"  Line items: {len(order['line_items'])}")
            print(f"  Should attach PDF: {should_attach_pdf(status)}")

            pdf = generate_order_pdf(order)
            if pdf:
                fname = pdf_filename(po)
                out_dir = os.path.join(os.path.dirname(__file__), "..", "screenshots")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, fname)
                with open(out_path, "wb") as f:
                    f.write(pdf)
                print(f"  PDF saved: {out_path} ({len(pdf):,} bytes)")
            else:
                print("  PDF generation FAILED")
            break
    else:
        print("No orders found in range 6010-6013")
