
import React, { useState, useEffect } from 'react';
import { View, Text, Pressable, ScrollView, StyleSheet, ActivityIndicator, Alert, Platform, Linking, Modal } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { WebView } from 'react-native-webview';
import { useAuth } from '../App';
import { InvoiceResponse } from '../api';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://https://giftly-backend-tfjada.cranl.net';

interface Props {
  onBack: () => void;
  invoiceId: string;
}

export const InvoiceScreen: React.FC<Props> = ({ onBack, invoiceId }) => {
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [invoice, setInvoice] = useState<InvoiceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showSuccessOverlay, setShowSuccessOverlay] = useState(false);
  const [showErrorOverlay, setShowErrorOverlay] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [showPaymentConfirmation, setShowPaymentConfirmation] = useState(false);
  const [couponCode, setCouponCode] = useState('');
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [finalAmount, setFinalAmount] = useState(invoice.full_amount);
  const [verifyingCoupon, setVerifyingCoupon] = useState(false);

  useEffect(() => {
    fetchInvoice();
  }, [invoiceId, token]);

  const fetchInvoice = async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const { getInvoice } = await import('../api');
      const invoiceData = await getInvoice(token, invoiceId);
      console.log('Invoice status received:', invoiceData.status); // Debug log
      setInvoice(invoiceData);
    } catch (err) {
      console.error('Failed to fetch invoice:', err);
      setError('فشل في تحميل الفاتورة');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
          <Pressable onPress={onBack} style={styles.backButton}>
            <Feather name="chevron-right" size={24} color="#9CA3AF" />
          </Pressable>
          <Text style={styles.headerTitle}>تفاصيل الفاتورة</Text>
          <View style={styles.headerSpacer} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#E0AAFF" />
          <Text style={styles.loadingText}>جاري تحميل الفاتورة...</Text>
        </View>
      </View>
    );
  }

  if (error || !invoice) {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
          <Pressable onPress={onBack} style={styles.backButton}>
            <Feather name="chevron-right" size={24} color="#9CA3AF" />
          </Pressable>
          <Text style={styles.headerTitle}>تفاصيل الفاتورة</Text>
          <View style={styles.headerSpacer} />
        </View>
        <View style={styles.errorContainer}>
          <Feather name="alert-circle" size={48} color="#EF4444" />
          <Text style={styles.errorText}>{error || 'فاتورة غير متوفرة'}</Text>
          <Pressable onPress={fetchInvoice} style={styles.retryButton}>
            <Text style={styles.retryButtonText}>إعادة المحاولة</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  // Calculate tax as 15% of order_only_price
  const tax = invoice.order_only_price * 0.15;

  // Status configuration
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'new':
        return {
          text: 'جديدة',
          color: '#F59E0B', // Amber
          bgColor: 'rgba(245, 158, 11, 0.1)',
          borderColor: 'rgba(245, 158, 11, 0.2)',
        };
      case 'paid':
        return {
          text: 'مدفوعة بالكامل',
          color: '#10B981', // Green
          bgColor: 'rgba(16, 185, 129, 0.1)',
          borderColor: 'rgba(16, 185, 129, 0.2)',
        };
      case 'cancelled':
        return {
          text: 'ملغية',
          color: '#EF4444', // Red
          bgColor: 'rgba(239, 68, 68, 0.1)',
          borderColor: 'rgba(239, 68, 68, 0.2)',
        };
      case 'refunded':
        return {
          text: 'مستردة',
          color: '#8B5CF6', // Purple
          bgColor: 'rgba(139, 92, 246, 0.1)',
          borderColor: 'rgba(139, 92, 246, 0.2)',
        };
      default:
        return {
          text: 'غير محدد',
          color: '#6B7280', // Gray
          bgColor: 'rgba(107, 114, 128, 0.1)',
          borderColor: 'rgba(107, 114, 128, 0.2)',
        };
    }
  };

  const statusConfig = getStatusConfig(invoice.status);

  const handleDownloadPDF = async () => {
    if (!token || !invoice) return;

    try {
      console.log('Starting PDF download...');

      // Download the PDF with proper authentication using the database ID
      const { downloadInvoicePDF } = await import('../api');
      const blob = await downloadInvoicePDF(token, invoice.id);
      console.log('Blob received, size:', blob.size);

      if (blob.size === 0) {
        throw new Error('Empty PDF file received');
      }

      // Convert blob to base64
      const base64 = await blobToBase64(blob);

      // Create file path in app's document directory
      const fileUri = FileSystem.documentDirectory + `${invoice.invoice_id}.pdf`;

      // Write file to device
      await FileSystem.writeAsStringAsync(fileUri, base64, {
        encoding: 'base64',
      });

      console.log('PDF saved to:', fileUri);

      // Share the PDF file
      const isAvailable = await Sharing.isAvailableAsync();
      if (isAvailable) {
        await Sharing.shareAsync(fileUri, {
          mimeType: 'application/pdf',
          dialogTitle: 'حفظ الفاتورة',
        });
        console.log('Share dialog opened');
      } else {
        Alert.alert('نجح', 'تم تحميل الفاتورة بنجاح إلى الجهاز');
      }
    } catch (error) {
      console.error('PDF download failed:', error);
      Alert.alert('خطأ', `فشل في تحميل الفاتورة: ${error.message}`);
    }
  };

  const handlePayment = async (paymentMethod: string) => {
    // Mock payment processing
    Alert.alert(
      'معالجة الدفع',
      `جاري معالجة الدفع باستخدام ${paymentMethod === 'apple_pay' ? 'Apple Pay' : paymentMethod === 'credit_card' ? 'بطاقة الائتمان' : 'Samsung Pay'}...`,
      [
        { text: 'إلغاء', style: 'cancel' },
        {
          text: 'تأكيد',
          onPress: () => {
            // Simulate payment success
            setTimeout(() => {
              Alert.alert(
                'تم الدفع بنجاح!',
                'تم دفع الفاتورة بنجاح. شكراً لاستخدام خدماتنا.',
                [
                  {
                    text: 'موافق',
                    onPress: () => {
                      // Refresh invoice to show paid status
                      fetchInvoice();
                    }
                  }
                ]
              );
            }, 2000);
          }
        }
      ]
    );
  };

  // Helper function to convert blob to base64
  const blobToBase64 = (blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  return (
    <View style={styles.container}>
      {/* Header Navigation */}
      <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
        <Pressable onPress={onBack} style={styles.backButton}>
          <Feather name="chevron-right" size={24} color="#9CA3AF" />
        </Pressable>
        <Text style={styles.headerTitle}>تفاصيل الفاتورة</Text>
        <View style={styles.headerSpacer} />
      </View>

      {/* Scrollable Content Container */}
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>

        {/* Main Receipt Card */}
        <View style={styles.receiptCard}>

          {/* Status Badge */}
          <View style={[styles.statusBadge, {
            backgroundColor: statusConfig.bgColor,
            borderColor: statusConfig.borderColor,
          }]}>
            <Feather
              name={
                invoice.status === 'paid' ? 'check-circle' :
                invoice.status === 'cancelled' ? 'x-circle' :
                invoice.status === 'refunded' ? 'refresh-cw' :
                'clock'
              }
              size={14}
              color={statusConfig.color}
            />
            <Text style={[styles.statusText, { color: statusConfig.color }]}>
              {statusConfig.text}
            </Text>
          </View>

          {/* Brand Info */}
          <View style={styles.brandInfo}>
            <View style={styles.brandIcon}>
              <Feather name="star" size={28} color="#E0AAFF" />
            </View>
            <Text style={styles.brandName}>هديتي للخدمات</Text>
            <View style={styles.invoiceDetails}>
              <Text style={styles.invoiceNumber}>رقم الفاتورة: {invoice.invoice_id}</Text>
              <Text style={styles.invoiceDate}>التاريخ: {new Date(invoice.created_at).toLocaleDateString('en-US')}</Text>
            </View>
            {/* Pay Now Button - Only show if invoice is new */}
            {invoice.status === 'new' && (
              <Pressable onPress={() => setShowPaymentModal(true)} style={styles.payNowButton}>
                <Text style={styles.payNowButtonText}>ادفع الآن</Text>
              </Pressable>
            )}
          </View>

          {/* Invoice Details */}
          <View style={styles.priceList}>
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>قيمة الطلب</Text>
              <Text style={styles.priceValue}>{invoice.order_only_price.toFixed(2)} ر.س</Text>
            </View>
            <View style={[styles.priceRow, styles.priceRowBorder]}>
              <Text style={styles.priceLabel}>رسوم الخدمة</Text>
              <Text style={styles.priceValue}>{invoice.service_fee.toFixed(2)} ر.س</Text>
            </View>
            <View style={[styles.priceRow, styles.priceRowBorder]}>
              <Text style={styles.priceLabel}>الضريبة (15%)</Text>
              <Text style={styles.priceValue}>{tax.toFixed(2)} ر.س</Text>
            </View>
            {invoice.description && (
              <View style={[styles.priceRow, styles.priceRowBorder]}>
                <Text style={styles.priceLabel}>الوصف</Text>
                <Text style={styles.priceValue}>{invoice.description}</Text>
              </View>
            )}
          </View>

          {/* Totals Section */}
          <View style={styles.totalsSection}>
            <View style={styles.totalAmount}>
              <View style={styles.totalAmountLeft}>
                <Text style={styles.totalAmountLabel}>المبلغ الإجمالي</Text>
                <Text style={styles.totalAmountSubLabel}>صافي المدفوع</Text>
              </View>
              <View style={styles.totalAmountRight}>
                <Text style={styles.totalAmountValue}>{(invoice.full_amount || 0).toFixed(2)}</Text>
                <Text style={styles.totalAmountCurrency}>ر.س</Text>
              </View>
            </View>
          </View>

          {/* Footer Note */}
          <View style={styles.footerNote}>
            <Feather name="file-text" size={12} color="#9CA3AF" />
            <Text style={styles.footerText}>Digital Invoice</Text>
          </View>
        </View>



        {/* Action Buttons - Always show */}
        <View style={styles.buttonContainer}>
          <Pressable onPress={() => setShowPdfViewer(true)} style={styles.viewButton}>
            <Feather name="eye" size={18} color="#E0AAFF" />
            <Text style={styles.viewButtonText}>عرض الفاتورة</Text>
          </Pressable>
          <Pressable onPress={handleDownloadPDF} style={styles.saveButton}>
            <Feather name="download" size={18} color="white" />
            <Text style={styles.saveButtonText}>حفظ PDF</Text>
          </Pressable>
        </View>

        {/* PDF Viewer Modal */}
        <Modal
          visible={showPdfViewer}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setShowPdfViewer(false)}
        >
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <Pressable onPress={() => setShowPdfViewer(false)} style={styles.closeButton}>
                <Feather name="x" size={24} color="#6B7280" />
              </Pressable>
              <Text style={styles.modalTitle}>عرض الفاتورة</Text>
              <View style={styles.modalSpacer} />
            </View>
            <WebView
              source={{
                uri: `${API_BASE_URL}/invoices/id/${invoice.id}/pdf`,
                headers: {
                  Authorization: `Bearer ${token}`,
                },
              }}
              style={styles.webView}
              javaScriptEnabled={true}
              domStorageEnabled={true}
              startInLoadingState={true}
              scalesPageToFit={true}
              onError={(syntheticEvent) => {
                const { nativeEvent } = syntheticEvent;
                console.warn('WebView error: ', nativeEvent);
                Alert.alert('خطأ', 'فشل في تحميل الفاتورة');
                setShowPdfViewer(false);
              }}
            />
          </View>
        </Modal>

        {/* Payment Method Modal */}
        <Modal
          visible={showPaymentModal}
          animationType="slide"
          transparent={true}
          onRequestClose={() => setShowPaymentModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>اختيار طريقة الدفع</Text>
                <Pressable onPress={() => setShowPaymentModal(false)} style={styles.closeButton}>
                  <Feather name="x" size={20} color="#9CA3AF" />
                </Pressable>
              </View>

              <View style={styles.modalBody}>
                <Pressable
                  onPress={() => {
                    Alert.alert('Apple Pay', 'Apple Pay placeholder - implement payment logic here');
                    setShowPaymentModal(false);
                  }}
                  style={styles.applePayButton}
                >
                  <Text style={styles.applePayButtonText}> Pay</Text>
                </Pressable>

                <Pressable
                  onPress={() => {
                    Alert.alert('Mada/Credit', 'Mada/Credit placeholder - implement payment logic here');
                    setShowPaymentModal(false);
                  }}
                  style={styles.paymentMethodButton}
                >
                  <View style={styles.paymentMethodContent}>
                    <View style={styles.paymentIcon}>
                      <Feather name="credit-card" size={20} color="#9CA3AF" />
                    </View>
                    <Text style={styles.paymentMethodText}>Mada/Credit</Text>
                  </View>
                  <Feather name="chevron-left" size={18} color="#9CA3AF" />
                </Pressable>

                <Pressable
                  onPress={() => {
                    setShowPaymentModal(false);
                    setShowPaymentConfirmation(true);
                  }}
                  style={styles.paymentMethodButton}
                >
                  <View style={styles.paymentMethodContent}>
                    <View style={styles.paymentIcon}>
                      <Feather name="wallet" size={20} color="#9CA3AF" />
                    </View>
                    <Text style={styles.paymentMethodText}>المحفظة</Text>
                  </View>
                  <Feather name="chevron-left" size={18} color="#9CA3AF" />
                </Pressable>
              </View>
            </View>
          </View>
        </Modal>

        {/* Payment Confirmation Modal */}
        <Modal
          visible={showPaymentConfirmation}
          animationType="fade"
          transparent={true}
          onRequestClose={() => setShowPaymentConfirmation(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.confirmationModalContent}>
              <View style={styles.confirmationModalBody}>
                <Feather name="credit-card" size={48} color="#E0AAFF" />
                <Text style={styles.confirmationTitle}>تأكيد الدفع</Text>

                {/* Coupon Input */}
                <View style={styles.couponSection}>
                  <Text style={styles.couponLabel}>كوبون الخصم (اختياري)</Text>
                  <View style={styles.couponInputContainer}>
                    <TextInput
                      style={styles.couponInput}
                      value={couponCode}
                      onChangeText={setCouponCode}
                      placeholder="أدخل رمز الكوبون"
                      placeholderTextColor="#9CA3AF"
                      autoCapitalize="characters"
                    />
                    <Pressable
                      onPress={async () => {
                        if (!couponCode.trim()) {
                          Alert.alert('خطأ', 'يرجى إدخال رمز الكوبون');
                          return;
                        }

                        setVerifyingCoupon(true);
                        try {
                          const formData = new FormData();
                          formData.append('coupon_code', couponCode.trim());
                          formData.append('invoice_id', invoice.id.toString());

                          const response = await fetch(`${API_BASE_URL}/invoices/verify-coupon`, {
                            method: 'POST',
                            headers: {
                              'Authorization': `Bearer ${token}`,
                            },
                            body: formData,
                          });

                          const result = await response.json();

                          if (!response.ok) {
                            throw new Error(result.detail || 'فشل في التحقق من الكوبون');
                          }

                          setCouponDiscount(result.discount_amount);
                          setFinalAmount(result.final_amount);
                          Alert.alert('نجح', `تم تطبيق الخصم: ${result.discount_amount.toFixed(2)} ريال\nالمبلغ النهائي: ${result.final_amount.toFixed(2)} ريال`);
                        } catch (error: any) {
                          Alert.alert('خطأ', error.message || 'فشل في التحقق من الكوبون');
                          setCouponCode('');
                          setCouponDiscount(0);
                          setFinalAmount(invoice.full_amount);
                        } finally {
                          setVerifyingCoupon(false);
                        }
                      }}
                      disabled={verifyingCoupon}
                      style={[styles.verifyCouponButton, verifyingCoupon && { opacity: 0.6 }]}
                    >
                      {verifyingCoupon ? (
                        <ActivityIndicator size="small" color="white" />
                      ) : (
                        <Text style={styles.verifyCouponText}>تحقق</Text>
                      )}
                    </Pressable>
                  </View>
                  {couponDiscount > 0 && (
                    <Text style={styles.discountText}>
                      الخصم المطبق: {couponDiscount.toFixed(2)} ريال
                    </Text>
                  )}
                </View>

                <Text style={styles.confirmationMessage}>
                  هل أنت متأكد من رغبتك في دفع {finalAmount.toFixed(2)} ريال من المحفظة؟
                  {couponDiscount > 0 && `\n(المبلغ الأصلي: ${invoice.full_amount.toFixed(2)} ريال)`}
                </Text>
                <View style={styles.confirmationButtons}>
                  <Pressable
                    onPress={() => {
                      setShowPaymentConfirmation(false);
                      setCouponCode('');
                      setCouponDiscount(0);
                      setFinalAmount(invoice.full_amount);
                    }}
                    style={styles.cancelButton}
                  >
                    <Text style={styles.cancelButtonText}>لا</Text>
                  </Pressable>
                  <Pressable
                    onPress={async () => {
                      setShowPaymentConfirmation(false);
                      try {
                        const { payWithWallet } = await import('../api');
                        const result = await payWithWallet(token, invoice.id, couponCode.trim() || undefined);

                        setShowSuccessOverlay(true);
                        setTimeout(() => {
                          setShowSuccessOverlay(false);
                          // Refresh invoice to show paid status
                          fetchInvoice();
                          // Reset coupon state
                          setCouponCode('');
                          setCouponDiscount(0);
                          setFinalAmount(invoice.full_amount);
                        }, 3000);
                      } catch (error: any) {
                        setErrorMessage(error.message || 'حدث خطأ أثناء الدفع');
                        setShowErrorOverlay(true);
                        setTimeout(() => {
                          setShowErrorOverlay(false);
                          setErrorMessage('');
                        }, 3000);
                      }
                    }}
                    style={styles.confirmButton}
                  >
                    <Text style={styles.confirmButtonText}>نعم</Text>
                  </Pressable>
                </View>
              </View>
            </View>
          </View>
        </Modal>

        {/* Success Overlay */}
        {showSuccessOverlay && (
          <View style={styles.successOverlay}>
            <View style={styles.successMessage}>
              <Feather name="check-circle" size={48} color="#10B981" />
              <Text style={styles.successTitle}>تم الدفع بنجاح</Text>
            </View>
          </View>
        )}

        {/* Error Overlay */}
        {showErrorOverlay && (
          <View style={styles.errorOverlay}>
            <View style={styles.errorMessage}>
              <Feather name="x-circle" size={48} color="#EF4444" />
              <Text style={styles.errorTitle}>فشل في الدفع</Text>
              <Text style={styles.errorSubtitle}>{errorMessage}</Text>
            </View>
          </View>
        )}

      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFC',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingBottom: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  backButton: {
    padding: 8,
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  headerSpacer: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 12,
    gap: 12,
  },
  receiptCard: {
    backgroundColor: 'white',
    borderRadius: 32,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.2)',
    alignSelf: 'center',
    marginBottom: 16,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '900',
    color: '#10B981',
    textTransform: 'uppercase',
  },
  brandInfo: {
    alignItems: 'center',
    marginBottom: 16,
  },
  brandIcon: {
    width: 48,
    height: 48,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  brandName: {
    fontSize: 18,
    fontWeight: '900',
    color: '#1F2937',
    marginBottom: 6,
  },
  invoiceDetails: {
    flexDirection: 'row',
    gap: 12,
  },
  invoiceNumber: {
    fontSize: 9,
    fontWeight: '900',
    color: '#9CA3AF',
  },
  invoiceDate: {
    fontSize: 9,
    fontWeight: '900',
    color: '#9CA3AF',
  },
  priceList: {
    backgroundColor: '#F9FAFB',
    borderRadius: 28,
    borderWidth: 1,
    borderColor: '#F3F4F6',
    alignSelf: 'center',
    width: '90%',
    overflow: 'hidden',
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 10,
  },
  priceRowBorder: {
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  priceLabel: {
    fontSize: 12,
    fontWeight: '900',
    color: '#374151',
  },
  priceValue: {
    fontSize: 14,
    fontWeight: '900',
    color: '#1F2937',
  },
  totalsSection: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 2,
    borderTopColor: '#F3F4F6',
    borderStyle: 'dashed',
    gap: 6,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  totalLabel: {
    fontSize: 10,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
  },
  totalValue: {
    fontSize: 12,
    fontWeight: '900',
    color: '#6B7280',
  },
  totalAmount: {
    backgroundColor: '#E0AAFF',
    borderRadius: 24,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  totalAmountLeft: {
    gap: 4,
  },
  totalAmountLabel: {
    fontSize: 10,
    fontWeight: '900',
    color: 'rgba(255, 255, 255, 0.8)',
    textTransform: 'uppercase',
  },
  totalAmountSubLabel: {
    fontSize: 10,
    fontWeight: 'bold',
    color: 'white',
  },
  totalAmountRight: {
    alignItems: 'flex-end',
  },
  totalAmountValue: {
    fontSize: 24,
    fontWeight: '900',
    color: 'white',
  },
  totalAmountCurrency: {
    fontSize: 10,
    fontWeight: 'bold',
    color: 'white',
  },
  footerNote: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
  },
  footerText: {
    fontSize: 8,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  singleButtonContainer: {
    alignItems: 'center',
  },
  saveButton: {
    flex: 1,
    height: 56,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  saveButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorText: {
    marginTop: 16,
    fontSize: 16,
    color: '#EF4444',
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 24,
    backgroundColor: '#E0AAFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 16,
  },
  retryButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  paymentSection: {
    backgroundColor: 'white',
    borderRadius: 24,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  paymentTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'center',
    marginBottom: 8,
  },
  paymentSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
  },
  paymentOptions: {
    gap: 12,
  },
  paymentButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  paymentIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#E0AAFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  applePayIcon: {
    fontSize: 24,
    color: 'white',
    fontWeight: 'bold',
  },
  samsungPayIcon: {
    fontSize: 20,
    color: 'white',
    fontWeight: 'bold',
  },
  paymentText: {
    flex: 1,
  },
  paymentButtonTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 4,
  },
  paymentButtonSubtitle: {
    fontSize: 12,
    color: '#6B7280',
  },
  applePayButton: {
    backgroundColor: '#000000',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  applePayText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  madaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  madaIcon: {
    width: 48,
    height: 32,
    backgroundColor: '#0066CC',
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  madaText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  brandApplePayButton: {
    marginTop: 16,
    backgroundColor: '#000000',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  brandApplePayText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  buttonContainer: {
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'center',
  },
  viewButton: {
    flex: 1,
    height: 56,
    backgroundColor: 'white',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E0AAFF',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  viewButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#E0AAFF',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: 'white',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
    backgroundColor: 'white',
  },
  closeButton: {
    padding: 8,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  modalSpacer: {
    width: 40,
  },
  webView: {
    flex: 1,
  },
  payNowButton: {
    marginTop: 16,
    backgroundColor: '#E0AAFF',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  payNowButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  paymentMethodButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
    marginBottom: 12,
  },
  paymentMethodContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  paymentMethodText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#374151',
  },
  applePayButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: 'white',
    borderRadius: 24,
    padding: 32,
    width: '90%',
    maxWidth: 400,
    maxHeight: '80%',
  },
  modalBody: {
    gap: 16,
  },
  successOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  successMessage: {
    backgroundColor: 'white',
    borderRadius: 24,
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  successTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1F2937',
    marginTop: 16,
    marginBottom: 8,
    textAlign: 'center',
  },
  successSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
  },
  errorOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  errorMessage: {
    backgroundColor: 'white',
    borderRadius: 24,
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1F2937',
    marginTop: 16,
    marginBottom: 8,
    textAlign: 'center',
  },
  errorSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
  },
  confirmationModalContent: {
    backgroundColor: 'white',
    borderRadius: 24,
    width: '90%',
    maxWidth: 350,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  confirmationModalBody: {
    padding: 32,
    alignItems: 'center',
  },
  confirmationTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1F2937',
    marginTop: 16,
    marginBottom: 12,
    textAlign: 'center',
  },
  confirmationMessage: {
    fontSize: 16,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 24,
  },
  confirmationButtons: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
  cancelButton: {
    flex: 1,
    backgroundColor: 'white',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#6B7280',
  },
  confirmButton: {
    flex: 1,
    backgroundColor: '#E0AAFF',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  confirmButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
  },
  couponSection: {
    width: '100%',
    marginBottom: 24,
  },
  couponLabel: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#374151',
    textAlign: 'right',
    marginBottom: 8,
  },
  couponInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  couponInput: {
    flex: 1,
    height: 48,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 16,
    color: '#1F2937',
    textAlign: 'right',
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  verifyCouponButton: {
    backgroundColor: '#E0AAFF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  verifyCouponText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  discountText: {
    fontSize: 14,
    color: '#10B981',
    fontWeight: 'bold',
    textAlign: 'center',
    marginTop: 8,
  },
});
