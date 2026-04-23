import html
import secrets
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Invoice, InvoiceStatus, Order, OrderStatus, Promocode, PromocodeUsage
from models.enums import UserRole
from schemas import CreateInvoice, InvoiceResponse
from utils.auth.auth import get_current_user
from utils.database.database import get_db

router = APIRouter()


@router.post("/courier/create", response_model=InvoiceResponse)
async def create_invoice_by_courier(
    invoice_data: CreateInvoice,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new invoice for an order by courier. Only assigned courier can create invoice.
    """
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can create invoices")

    result = await db.execute(select(Order).where(Order.id == invoice_data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    result = await db.execute(
        select(Invoice).where(Invoice.order_id == invoice_data.order_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invoice already exists for this order")

    invoice_id = f"INV-{secrets.token_hex(6).upper()}"

    # Store amounts as floats directly (no multiplication by 1000)
    new_invoice = Invoice(
        invoice_id=invoice_id,
        order_id=invoice_data.order_id,
        full_amount=invoice_data.full_amount,
        service_fee=invoice_data.service_fee,
        order_only_price=invoice_data.order_only_price,
        courier_fee=invoice_data.courier_fee,
        description=invoice_data.description,
        comment=invoice_data.comment,
        due_date=invoice_data.due_date,
        tax_amount=invoice_data.tax_amount,
        discount_amount=invoice_data.discount_amount,
        status=InvoiceStatus.NEW,
        created_by_user_id=current_user.id,  # Track who created the invoice
    )

    db.add(new_invoice)
    order.status = OrderStatus.INVOICE_CREATED
    await db.commit()
    await db.refresh(new_invoice)

    from utils.websocket.websocket_events import (
        emit_invoice_requires_approval,
        emit_order_status_change,
    )

    await emit_order_status_change(order.id, OrderStatus.INVOICE_CREATED.value)
    await emit_invoice_requires_approval(new_invoice.id, order.id)

    return new_invoice


@router.put("/courier/update/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice_by_courier(
    invoice_id: str,
    invoice_data: CreateInvoice,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an existing invoice by courier. Only the assigned courier can update the invoice.
    """
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can update invoices")

    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Cannot update a paid or cancelled invoice")

    result = await db.execute(select(Order).where(Order.id == invoice.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    invoice.full_amount = invoice_data.full_amount
    invoice.service_fee = invoice_data.service_fee
    invoice.order_only_price = invoice_data.order_only_price
    invoice.courier_fee = invoice_data.courier_fee
    invoice.description = invoice_data.description
    invoice.comment = invoice_data.comment
    invoice.due_date = invoice_data.due_date
    invoice.tax_amount = invoice_data.tax_amount
    invoice.discount_amount = invoice_data.discount_amount
    invoice.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(invoice)

    from utils.websocket.websocket_events import emit_invoice_requires_approval

    await emit_invoice_requires_approval(invoice.id, order.id)

    return invoice


@router.get("/id/{invoice_db_id}", response_model=InvoiceResponse)
async def get_invoice_by_id(
    invoice_db_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get invoice by database ID. Authenticated users can view their own invoices.
    """
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_db_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await db.execute(
        select(Order).where(
            Order.id == invoice.order_id,
            or_(
                Order.created_by_user_id == current_user.id,
                Order.assigned_to_user_id == current_user.id,
            ),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")

    return invoice


def generate_invoice_pdf(invoice: InvoiceResponse, order: Order = None) -> BytesIO:
    """Generate PDF invoice with proper Arabic text"""
    buffer = BytesIO()

    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center alignment
    )

    normal_style = styles["Normal"]
    normal_style.fontSize = 12

    # Build the PDF content
    content = []

    # Title
    content.append(Paragraph("INVOICE", title_style))
    content.append(Spacer(1, 12))

    # Company info
    content.append(Paragraph("Hadiyati Services", styles["Heading2"]))
    content.append(Spacer(1, 12))

    # Invoice details
    status_text = "Paid" if invoice.status == "paid" else "Unpaid"
    invoice_data = [
        ["Invoice Number:", invoice.invoice_id],
        ["Invoice Date:", invoice.created_at.strftime("%Y-%m-%d %H:%M")],
        ["Status:", status_text],
    ]

    # Add description if available
    if invoice.description:
        invoice_data.append(["Description:", invoice.description])

    invoice_table = Table(invoice_data, colWidths=[2 * inch, 4 * inch])
    invoice_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    content.append(invoice_table)
    content.append(Spacer(1, 20))

    # Items table — amounts stored as halalas, display as SAR (÷100)
    items_data = [
        ["Item", "Qty", "Price"],
        ["Order Value", "1", f"{invoice.order_only_price / 100:.2f} SAR"],
        ["Service Fee", "1", f"{invoice.service_fee / 100:.2f} SAR"],
        ["Tax", "1", f"{invoice.tax_amount / 100:.2f} SAR"],
    ]

    items_table = Table(items_data, colWidths=[3.5 * inch, 1 * inch, 2 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    content.append(items_table)
    content.append(Spacer(1, 20))

    # Total
    total_data = [
        ["Total Amount:", f"{invoice.full_amount / 100:.2f} SAR"],
    ]

    total_table = Table(total_data, colWidths=[4 * inch, 2 * inch])
    total_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ]
        )
    )
    content.append(total_table)

    # Footer
    content.append(Spacer(1, 30))
    content.append(Paragraph("Thank you for using our services", normal_style))

    # Build the PDF
    doc.build(content)
    buffer.seek(0)
    return buffer


@router.get("/order/{order_id}/pdf")
async def download_invoice_pdf(
    order_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and stream PDF invoice for an order."""
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            or_(
                Order.created_by_user_id == current_user.id,
                Order.assigned_to_user_id == current_user.id,
            ),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or access denied")

    result = await db.execute(select(Invoice).where(Invoice.order_id == order_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found for this order")

    pdf_buffer = generate_invoice_pdf(invoice, order)
    return StreamingResponse(
        iter([pdf_buffer.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_id}.pdf"'},
    )


@router.get("/id/{invoice_db_id}/pdf")
async def download_invoice_pdf_by_id(
    invoice_db_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and stream PDF invoice by database ID."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_db_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await db.execute(
        select(Order).where(
            Order.id == invoice.order_id,
            or_(
                Order.created_by_user_id == current_user.id,
                Order.assigned_to_user_id == current_user.id,
            ),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")

    pdf_buffer = generate_invoice_pdf(invoice, order)
    return StreamingResponse(
        iter([pdf_buffer.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_id}.pdf"'},
    )


@router.get("/order/{order_id}", response_model=InvoiceResponse)
async def get_invoice_by_order(
    order_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get invoice by order ID. Authenticated users can view their own invoices.
    """
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            or_(
                Order.created_by_user_id == current_user.id,
                Order.assigned_to_user_id == current_user.id,
            ),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or access denied")

    result = await db.execute(select(Invoice).where(Invoice.order_id == order_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found for this order")

    return invoice


@router.post("/verify-coupon")
async def verify_coupon(
    coupon_code: str = Form(..., max_length=50),
    invoice_id: int = Form(..., ge=1),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify coupon code and calculate discount for an invoice.
    """
    # Get invoice and check ownership
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if invoice belongs to current user
    result = await db.execute(
        select(Order).where(
            Order.id == invoice.order_id, Order.created_by_user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if invoice is already paid
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    # Find the coupon
    result = await db.execute(
        select(Promocode).where(Promocode.code == coupon_code.upper())
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid coupon code")

    if not coupon.active or coupon.valid_until.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Coupon is expired or inactive")

    # Check usage limit
    if coupon.usage_count >= coupon.usage_limit and coupon.usage_limit > 0:
        raise HTTPException(status_code=400, detail="Coupon usage limit exceeded")

    if invoice.full_amount < coupon.minimum_order_value:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order value for this coupon is {coupon.minimum_order_value}",
        )

    # Per-user one-use enforcement (same as pay_with_wallet)
    usage_check = await db.execute(
        select(PromocodeUsage).where(
            PromocodeUsage.user_id == current_user.id,
            PromocodeUsage.promocode_id == coupon.id,
        )
    )
    if usage_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already used this promocode")

    # Calculate discount using integer arithmetic to avoid float precision issues
    discount_amount = 0
    if coupon.applicable_to == "order_total":
        base = invoice.full_amount
    elif coupon.applicable_to == "service_fee":
        base = invoice.service_fee
    elif coupon.applicable_to == "delivery_fee":
        base = invoice.courier_fee
    else:
        base = 0

    if coupon.percentage > 0:
        discount_amount = int(base * coupon.percentage / 100)
    if coupon.max_value > 0 and discount_amount > coupon.max_value:
        discount_amount = coupon.max_value

    final_amount = max(0, invoice.full_amount - discount_amount)

    return {
        "coupon_id": coupon.id,
        "discount_amount": discount_amount,
        "final_amount": final_amount,
        "description": html.escape(coupon.description or f"{coupon.percentage}% discount"),
    }


# Wildcard route — must be LAST so fixed-segment paths (/id/, /order/, /courier/) match first
@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get invoice by invoice_id string (e.g. INV-XXXXXX). Customer or assigned courier only."""
    result = await db.execute(
        select(Invoice)
        .join(Order, Invoice.order_id == Order.id)
        .where(
            Invoice.invoice_id == invoice_id,
            or_(
                Order.created_by_user_id == current_user.id,
                Order.assigned_to_user_id == current_user.id,
            ),
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice
