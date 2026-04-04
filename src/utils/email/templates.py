# Email templates for Giftly application

# Invoice Email Template
invoice_email = {
    "subject": "فاتورة طلبك من هديتي - {{ invoice_id }}",
    "html": """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>فاتورة طلبك من هديتي</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f8fafc;
            color: #1f2937;
            direction: rtl;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #e0aaff 0%, #c084fc 100%);
            padding: 40px 30px;
            text-align: center;
            color: white;
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: bold;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 16px;
        }
        .content {
            padding: 40px 30px;
        }
        .invoice-details {
            background-color: #f8fafc;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .invoice-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .invoice-row:last-child {
            border-bottom: none;
            font-weight: bold;
            font-size: 18px;
            color: #e0aaff;
        }
        .invoice-row.total {
            background-color: #e0aaff;
            color: white;
            margin: 0 -20px -20px -20px;
            padding: 15px 20px;
            border-radius: 0 0 8px 8px;
        }
        .order-info {
            background-color: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-paid {
            background-color: #dcfce7;
            color: #166534;
        }
        .status-pending {
            background-color: #fef3c7;
            color: #92400e;
        }
        .footer {
            background-color: #1f2937;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .footer h3 {
            margin: 0 0 10px 0;
            font-size: 18px;
        }
        .footer p {
            margin: 5px 0;
            opacity: 0.8;
        }
        .button {
            display: inline-block;
            background-color: #e0aaff;
            color: white;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: bold;
            margin: 20px 0;
        }
        .highlight {
            background-color: #fef3c7;
            padding: 20px;
            border-radius: 8px;
            border-right: 4px solid #f59e0b;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>هديتي</h1>
            <p>فاتورة طلبك جاهزة</p>
        </div>

        <div class="content">
            <div class="highlight">
                <h2 style="margin: 0 0 10px 0; color: #92400e;">مرحباً {{ customer_name }}</h2>
                <p style="margin: 0; color: #92400e;">
                    تم إنشاء فاتورة لطلبك بنجاح. يرجى مراجعة التفاصيل أدناه والقيام بالدفع لتأكيد الطلب.
                </p>
            </div>

            <div class="order-info">
                <h3 style="margin: 0 0 15px 0; color: #92400e;">تفاصيل الطلب</h3>
                <p><strong>رقم الطلب:</strong> {{ order_id }}</p>
                <p><strong>رقم الفاتورة:</strong> {{ invoice_id }}</p>
                <p><strong>تاريخ التوصيل:</strong> {{ delivery_date }}</p>
                <p><strong>الحالة:</strong> <span class="status-badge status-{{ status_class }}">{{ status_text }}</span></p>
            </div>

            <div class="invoice-details">
                <h3 style="margin: 0 0 20px 0; text-align: center;">تفاصيل الفاتورة</h3>

                <div class="invoice-row">
                    <span>سعر الهدية الأساسي</span>
                    <span>{{ gift_price }} ر.س</span>
                </div>

                <div class="invoice-row">
                    <span>رسوم الخدمة</span>
                    <span>{{ service_fee }} ر.س</span>
                </div>

                <div class="invoice-row">
                    <span>رسوم التوصيل</span>
                    <span>{{ delivery_fee }} ر.س</span>
                </div>

                {% if discount_amount > 0 %}
                <div class="invoice-row">
                    <span>خصم</span>
                    <span>-{{ discount_amount }} ر.س</span>
                </div>
                {% endif %}

                {% if tax_amount > 0 %}
                <div class="invoice-row">
                    <span>ضريبة القيمة المضافة</span>
                    <span>{{ tax_amount }} ر.س</span>
                </div>
                {% endif %}

                <div class="invoice-row total">
                    <span>المجموع الكلي</span>
                    <span>{{ total_amount }} ر.س</span>
                </div>
            </div>

            {% if status == 'pending' %}
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ payment_url }}" class="button">الدفع الآن</a>
                <p style="margin: 15px 0 0 0; font-size: 14px; color: #6b7280;">
                    يرجى إتمام الدفع قبل {{ due_date }} لتأكيد طلبك
                </p>
            </div>
            {% endif %}

            {% if notes %}
            <div class="order-info">
                <h3 style="margin: 0 0 10px 0; color: #92400e;">ملاحظات</h3>
                <p style="margin: 0; white-space: pre-line;">{{ notes }}</p>
            </div>
            {% endif %}
        </div>

        <div class="footer">
            <h3>هديتي - Giftly</h3>
            <p>نحن هنا لنجعل إهداء الهدايا أمراً سهلاً وممتعاً</p>
            <p>للاستفسارات: support@giftly.com | هاتف: 800-123-4567</p>
            <p style="margin-top: 15px; font-size: 12px;">
                © 2024 هديتي. جميع الحقوق محفوظة.
            </p>
        </div>
    </div>
</body>
</html>
    """,
    "text": """
مرحباً {{ customer_name }},

تم إنشاء فاتورة لطلبك في هديتي بنجاح!

تفاصيل الطلب:
- رقم الطلب: {{ order_id }}
- رقم الفاتورة: {{ invoice_id }}
- تاريخ التوصيل: {{ delivery_date }}
- الحالة: {{ status_text }}

تفاصيل الفاتورة:
- سعر الهدية الأساسي: {{ gift_price }} ر.س
- رسوم الخدمة: {{ service_fee }} ر.س
- رسوم التوصيل: {{ delivery_fee }} ر.س
{% if discount_amount > 0 %}
- خصم: -{{ discount_amount }} ر.س
{% endif %}
{% if tax_amount > 0 %}
- ضريبة القيمة المضافة: {{ tax_amount }} ر.س
{% endif %}
- المجموع الكلي: {{ total_amount }} ر.س

{% if status == 'pending' %}
يرجى إتمام الدفع قبل {{ due_date }} لتأكيد طلبك:
{{ payment_url }}
{% endif %}

{% if notes %}
ملاحظات:
{{ notes }}
{% endif %}

شكراً لاستخدامك هديتي!
للاستفسارات: support@giftly.com | هاتف: 800-123-4567

© 2024 هديتي. جميع الحقوق محفوظة.
    """,
}

# Welcome Email Template
welcome_email = {
    "subject": "مرحباً بك في هديتي - {{ user_name }}!",
    "html": """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مرحباً بك في هديتي</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f8fafc;
            color: #1f2937;
            direction: rtl;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #e0aaff 0%, #c084fc 100%);
            padding: 40px 30px;
            text-align: center;
            color: white;
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: bold;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 16px;
        }
        .content {
            padding: 40px 30px;
        }
        .welcome-message {
            background-color: #f0f9ff;
            border: 1px solid #0ea5e9;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            border-right: 4px solid #0ea5e9;
        }
        .features {
            margin: 30px 0;
        }
        .feature {
            display: flex;
            align-items: center;
            margin: 15px 0;
            padding: 15px;
            background-color: #f8fafc;
            border-radius: 8px;
        }
        .feature-icon {
            width: 40px;
            height: 40px;
            background-color: #e0aaff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 15px;
            color: white;
            font-size: 18px;
        }
        .feature-content h3 {
            margin: 0 0 5px 0;
            color: #1f2937;
            font-size: 16px;
        }
        .feature-content p {
            margin: 0;
            color: #6b7280;
            font-size: 14px;
        }
        .cta-button {
            display: inline-block;
            background-color: #e0aaff;
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin: 30px 0;
            text-align: center;
        }
        .footer {
            background-color: #1f2937;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .footer h3 {
            margin: 0 0 10px 0;
            font-size: 18px;
        }
        .footer p {
            margin: 5px 0;
            opacity: 0.8;
        }
        .social-links {
            margin: 20px 0;
        }
        .social-links a {
            color: #e0aaff;
            text-decoration: none;
            margin: 0 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>هديتي</h1>
            <p>أهلاً وسهلاً بك في عائلتنا</p>
        </div>

        <div class="content">
            <div class="welcome-message">
                <h2 style="margin: 0 0 10px 0; color: #0ea5e9;">مرحباً {{ user_name }}! 🎉</h2>
                <p style="margin: 0; color: #0ea5e9;">
                    شكراً لتسجيلك في هديتي! نحن متحمسون لمساعدتك في إيجاد الهدايا المثالية لأحبائك.
                </p>
            </div>

            <p style="font-size: 16px; line-height: 1.6; margin: 20px 0;">
                لقد تم تأكيد حسابك بنجاح ويمكنك الآن البدء في استكشاف خدماتنا. إليك بعض المميزات التي تنتظرك:
            </p>

            <div class="features">
                <div class="feature">
                    <div class="feature-icon">🎁</div>
                    <div class="feature-content">
                        <h3>تنويع هائل من الهدايا</h3>
                        <p>اكتشف آلاف الخيارات من الهدايا لكل المناسبات والأذواق</p>
                    </div>
                </div>

                <div class="feature">
                    <div class="feature-icon">🚚</div>
                    <div class="feature-content">
                        <h3>توصيل سريع وآمن</h3>
                        <p>مندوبينا المدربين سيصلون إلى بابك في نفس اليوم</p>
                    </div>
                </div>

                <div class="feature">
                    <div class="feature-icon">💝</div>
                    <div class="feature-content">
                        <h3>تخصيص كامل</h3>
                        <p>اطلب أي هدية تتخيلها وسنقوم بتنسيقها خصيصاً لك</p>
                    </div>
                </div>

                <div class="feature">
                    <div class="feature-icon">⭐</div>
                    <div class="feature-content">
                        <h3>خدمة عملاء على مدار 24 ساعة</h3>
                        <p>فريقنا جاهز لمساعدتك في أي وقت تحتاجه</p>
                    </div>
                </div>
            </div>

            <div style="text-align: center;">
                <a href="{{ app_url }}" class="cta-button">ابدأ رحلتك الآن</a>
                <p style="margin: 15px 0 0 0; font-size: 14px; color: #6b7280;">
                    احتفظ بهذا البريد الإلكتروني للمراجعة لاحقاً
                </p>
            </div>

            <div style="background-color: #fef3c7; padding: 20px; border-radius: 8px; margin: 30px 0; border-right: 4px solid #f59e0b;">
                <h3 style="margin: 0 0 10px 0; color: #92400e;">نصائح للبدء:</h3>
                <ul style="margin: 0; padding-right: 20px; color: #92400e;">
                    <li>أضف عنوان التوصيل في ملفك الشخصي</li>
                    <li>استكشف الأقسام المختلفة للهدايا</li>
                    <li>اتصل بنا إذا كان لديك أي أسئلة</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            <h3>هديتي - Giftly</h3>
            <p>نحن هنا لنجعل إهداء الهدايا أمراً سهلاً وممتعاً</p>
            <div class="social-links">
                <a href="#">فيسبوك</a> |
                <a href="#">إنستغرام</a> |
                <a href="#">تويتر</a>
            </div>
            <p>للاستفسارات: support@giftly.com | هاتف: 800-123-4567</p>
            <p style="margin-top: 15px; font-size: 12px;">
                © 2024 هديتي. جميع الحقوق محفوظة.
            </p>
        </div>
    </div>
</body>
</html>
    """,
    "text": """
مرحباً {{ user_name }}! 🎉

شكراً لتسجيلك في هديتي!

لقد تم تأكيد حسابك بنجاح ويمكنك الآن البدء في استكشاف خدماتنا.

المميزات التي تنتظرك:
• تنويع هائل من الهدايا لكل المناسبات والأذواق
• توصيل سريع وآمن في نفس اليوم
• تخصيص كامل للهدايا حسب رغبتك
• خدمة عملاء على مدار 24 ساعة

ابدأ رحلتك الآن: {{ app_url }}

نصائح للبدء:
• أضف عنوان التوصيل في ملفك الشخصي
• استكشف الأقسام المختلفة للهدايا
• اتصل بنا إذا كان لديك أي أسئلة

شكراً لانضمامك إلينا!
نحن متحمسون لمساعدتك في إيجاد الهدايا المثالية.

للاستفسارات: support@giftly.com | هاتف: 800-123-4567

© 2024 هديتي. جميع الحقوق محفوظة.
    """,
}
