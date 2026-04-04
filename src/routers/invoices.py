import os
import tempfile
import time
import uuid
from datetime import datetime
from io import BytesIO
from threading import Timer

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, status
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models import Invoice, InvoiceStatus, Order
from schemas import CreateInvoice, InvoiceResponse
from utils.auth.auth import get_current_user
from utils.database.database import get_db

router = APIRouter()


@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: CreateInvoice, db: AsyncSession = Depends(get_db)
):
    """
    Create a new invoice for an order. Admin only endpoint.
    """
    # Check if order exists
    result = await db.execute(select(Order).where(Order.id == invoice_data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found")

    # Check if invoice already exists for this order
    result = await db.execute(
        select(Invoice).where(Invoice.order_id == invoice_data.order_id)
    )
    existing_invoice = result.scalar_one_or_none()
    if existing_invoice:
        raise HTTPException(
            status_code=400, detail="Invoice already exists for this order"
        )

    # Generate unique invoice ID
    result = await db.execute(select(Invoice))
    invoice_count = len(result.scalars().all())
    invoice_id = f"INV-{invoice_count + 1:06d}"

    # Create the invoice
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
    )

    db.add(new_invoice)
    await db.commit()
    await db.refresh(new_invoice)

    # Update order status to indicate invoice is created
    order.status = (
        "invoice_created"  # You might want to add this status to your OrderStatus enum
    )
    await db.commit()

    # Emit order status change event
    from utils.websocket.websocket_events import emit_order_status_change

    await emit_order_status_change(order.id, order.status)

    # Emit invoice creation event
    from utils.websocket.websocket_events import emit_invoice_created

    await emit_invoice_created(new_invoice.id, new_invoice.order_id)

    # Send chat message about invoice creation
    from utils.websocket.websocket_events import emit_chat_message

    await emit_chat_message(
        conversation_id=None,  # Will be found by order
        sender_id=current_user.id,
        content=f"تم إنشاء فاتورة جديدة بمبلغ {new_invoice.full_amount:.2f} ريال",
        message_type="invoice_created",
        order_id=new_invoice.order_id,
        invoice_data={
            "id": new_invoice.id,
            "invoice_id": new_invoice.invoice_id,
            "full_amount": new_invoice.full_amount,
            "description": new_invoice.description,
        },
    )

    return new_invoice


@router.post("/courier/create", response_model=InvoiceResponse)
async def create_invoice_by_courier(
    invoice_data: CreateInvoice,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new invoice for an order by courier. Only assigned courier can create invoice.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can create invoices")

    # Check if order exists and is assigned to this courier
    result = await db.execute(select(Order).where(Order.id == invoice_data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    # Check if invoice already exists for this order
    result = await db.execute(
        select(Invoice).where(Invoice.order_id == invoice_data.order_id)
    )
    existing_invoice = result.scalar_one_or_none()
    if existing_invoice:
        raise HTTPException(
            status_code=400, detail="Invoice already exists for this order"
        )

    # Generate unique invoice ID
    result = await db.execute(select(Invoice))
    invoice_count = len(result.scalars().all())
    invoice_id = f"INV-{invoice_count + 1:06d}"

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
    await db.commit()
    await db.refresh(new_invoice)

    # Emit invoice creation event
    from utils.websocket.websocket_events import emit_invoice_created

    await emit_invoice_created(new_invoice.id, new_invoice.order_id)

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
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can update invoices")

    # Check if invoice exists
    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if order exists and is assigned to this courier
    result = await db.execute(select(Order).where(Order.id == invoice.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    # Store amounts as floats directly (no multiplication by 1000)
    invoice.full_amount = invoice_data.full_amount
    invoice.service_fee = invoice_data.service_fee
    invoice.order_only_price = invoice_data.order_only_price
    invoice.courier_fee = invoice_data.courier_fee
    invoice.description = invoice_data.description
    invoice.comment = invoice_data.comment
    invoice.due_date = invoice_data.due_date
    invoice.tax_amount = invoice_data.tax_amount
    invoice.discount_amount = invoice_data.discount_amount
    invoice.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(invoice)

    # Send chat message about invoice update
    from utils.websocket.websocket_events import emit_chat_message

    await emit_chat_message(
        conversation_id=None,  # Will be found by order
        sender_id=current_user.id,
        content=f"تم تحديث الفاتورة - المبلغ الجديد: {invoice.full_amount:.2f} ريال",
        message_type="invoice_updated",
        order_id=invoice.order_id,
        invoice_data={
            "id": invoice.id,
            "invoice_id": invoice.invoice_id,
            "full_amount": invoice.full_amount,
            "description": invoice.description,
        },
    )

    return invoice


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get invoice by invoice_id. Public endpoint for viewing invoices.
    """
    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

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

    # Check if the invoice belongs to the current user (through the order)
    result = await db.execute(
        select(Order).where(
            Order.id == invoice.order_id, Order.created_by_user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")

    return invoice


def delete_file_after_delay(
    file_path: str, delay_seconds: int = 600
):  # 10 minutes = 600 seconds
    """Delete a file after a specified delay"""

    def delete_file():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    timer = Timer(delay_seconds, delete_file)
    timer.start()


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

    # Items table
    items_data = [
        ["Item", "Qty", "Price"],
        ["Order Value", "1", f"{invoice.order_only_price:.2f} SAR"],
        ["Service Fee", "1", f"{invoice.service_fee:.2f} SAR"],
        ["Tax (15%)", "1", f"{(invoice.order_only_price * 0.15):.2f} SAR"],
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
        ["Total Amount:", f"{invoice.full_amount:.2f} SAR"],
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
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download PDF invoice for an order.
    Creates a temporary file that auto-deletes after 10 minutes.
    """
    # Check if order exists and belongs to current user
    result = await db.execute(
        select(Order).where(
            Order.id == order_id, Order.created_by_user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or access denied")

    result = await db.execute(select(Invoice).where(Invoice.order_id == order_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found for this order")

    # Generate PDF
    pdf_buffer = generate_invoice_pdf(invoice, order)

    # Create temporary file
    temp_dir = tempfile.gettempdir()
    temp_filename = f"invoice_{invoice.invoice_id}_{int(time.time())}.pdf"
    temp_filepath = os.path.join(temp_dir, temp_filename)

    # Write PDF to temporary file
    with open(temp_filepath, "wb") as f:
        f.write(pdf_buffer.getvalue())

    # Schedule file deletion after 10 minutes
    background_tasks.add_task(delete_file_after_delay, temp_filepath, 600)

    # Return file response
    return FileResponse(
        path=temp_filepath,
        media_type="application/pdf",
        filename=f"{invoice.invoice_id}.pdf",
    )


@router.get("/id/{invoice_db_id}/pdf")
async def download_invoice_pdf_by_id(
    invoice_db_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download PDF invoice by database ID.
    Creates a temporary file that auto-deletes after 10 minutes.
    """
    # Get invoice and check ownership
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_db_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Check if the invoice belongs to the current user (through the order)
    result = await db.execute(
        select(Order).where(
            Order.id == invoice.order_id, Order.created_by_user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")

    # Generate PDF
    pdf_buffer = generate_invoice_pdf(invoice, order)

    # Create temporary file
    temp_dir = tempfile.gettempdir()
    temp_filename = f"invoice_{invoice.invoice_id}_{int(time.time())}.pdf"
    temp_filepath = os.path.join(temp_dir, temp_filename)

    # Write PDF to temporary file
    with open(temp_filepath, "wb") as f:
        f.write(pdf_buffer.getvalue())

    # Schedule file deletion after 10 minutes
    background_tasks.add_task(delete_file_after_delay, temp_filepath, 600)

    # Return file response
    return FileResponse(
        path=temp_filepath,
        media_type="application/pdf",
        filename=f"{invoice.invoice_id}.pdf",
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
    # Check if order exists and belongs to current user
    result = await db.execute(
        select(Order).where(
            Order.id == order_id, Order.created_by_user_id == current_user.id
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
    coupon_code: str = Form(...),
    invoice_id: int = Form(...),
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

    # Check if coupon is active and not expired
    if not coupon.active or coupon.valid_until < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Coupon is expired or inactive")

    # Check usage limit
    if coupon.usage_count >= coupon.usage_limit and coupon.usage_limit > 0:
        raise HTTPException(status_code=400, detail="Coupon usage limit exceeded")

    # Check minimum order value
    if invoice.full_amount < coupon.minimum_order_value:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order value for this coupon is {coupon.minimum_order_value}",
        )

    # Calculate discount
    discount_amount = 0
    if coupon.applicable_to == "order_total":
        if coupon.percentage > 0:
            discount_amount = invoice.full_amount * (coupon.percentage / 100)
        if coupon.max_value > 0 and discount_amount > coupon.max_value:
            discount_amount = coupon.max_value
    elif coupon.applicable_to == "service_fee":
        if coupon.percentage > 0:
            discount_amount = invoice.service_fee * (coupon.percentage / 100)
        if coupon.max_value > 0 and discount_amount > coupon.max_value:
            discount_amount = coupon.max_value
    elif coupon.applicable_to == "delivery_fee":
        if coupon.percentage > 0:
            discount_amount = invoice.courier_fee * (coupon.percentage / 100)
        if coupon.max_value > 0 and discount_amount > coupon.max_value:
            discount_amount = coupon.max_value

    final_amount = invoice.full_amount - discount_amount
    if final_amount < 0:
        final_amount = 0

    return {
        "coupon_id": coupon.id,
        "discount_amount": discount_amount,
        "final_amount": final_amount,
        "description": coupon.description or f"{coupon.percentage}% discount",
    }
