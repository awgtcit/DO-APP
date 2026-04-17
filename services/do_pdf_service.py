"""
Delivery Order PDF generation service.

Renders the print-view HTML template to an A4-landscape PDF
suitable for email attachment.  Uses xhtml2pdf (pure-Python).

The legacy PHP system used mPDF with the same approach:
render HTML → convert to PDF → attach to email → discard.
"""

import io
import logging
from flask import render_template
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


# Statuses that should include a PDF attachment (matches legacy PHP)
_ATTACH_STATUSES = {"SUBMITTED", "PRICE AGREED", "CONFIRMED"}


def should_attach_pdf(status: str) -> bool:
    """Return True if this status transition warrants a PDF attachment."""
    return status.upper() in _ATTACH_STATUSES


def generate_order_pdf(order: dict) -> bytes | None:
    """
    Render the delivery-order print template to a PDF byte string.

    Returns the PDF bytes on success, or None on failure.
    The caller is responsible for providing a valid Flask app context.
    """
    try:
        html = render_template(
            "delivery_orders/print_pdf.html",
            order=order,
            can_see_prices=True,   # PDF always includes prices
        )

        buf = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html), dest=buf)

        if result.err:
            logger.error("xhtml2pdf reported %d errors for %s",
                         result.err, order.get("PO_Number", "?"))
            return None

        pdf_bytes = buf.getvalue()
        logger.info("PDF generated for %s (%d bytes)",
                    order.get("PO_Number", "?"), len(pdf_bytes))
        return pdf_bytes

    except Exception:
        logger.exception("PDF generation failed for %s",
                         order.get("PO_Number", "?"))
        return None


def pdf_filename(po_number: str) -> str:
    """
    Build the PDF attachment filename from the PO number.
    Replaces ``/`` with ``_`` to match legacy behaviour.
    Example: ``AWGTC/Feb/26/DO6013`` → ``AWGTC_Feb_26_DO6013.pdf``
    """
    safe = po_number.replace("/", "_").replace("\\", "_")
    return f"{safe}.pdf"
