
import React, { useState, useCallback } from 'react';
import { View, Text, Pressable, ScrollView, TextInput, StyleSheet, Image, Modal } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'other';
  time: string;
  isInvoice?: boolean;
  invoiceData?: any;
}

type UserRole = 'customer' | 'courier';

interface Props {
  userRole: UserRole;
  onBack: () => void;
  onFinishOrder: () => void;
  onShowInvoice: () => void;
}

const COURIER_GALLERY = [
  'https://picsum.photos/seed/gift1/400/400',
  'https://picsum.photos/seed/gift2/400/400',
  'https://picsum.photos/seed/gift3/400/400',
  'https://picsum.photos/seed/gift4/400/400',
];

export const CourierChatScreen: React.FC<Props> = ({ userRole, onBack, onFinishOrder, onShowInvoice }) => {
  const insets = useSafeAreaInsets();
  const [showCourierProfile, setShowCourierProfile] = useState(false);
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [showGallery, setShowGallery] = useState(false);
  const [showCancelOptions, setShowCancelOptions] = useState(false);

  const [invoiceDesc, setInvoiceDesc] = useState('');
  const [giftPrice, setGiftPrice] = useState('');
  const [serviceFee, setServiceFee] = useState('');
  const [deliveryFee, setDeliveryFee] = useState('');

  const [isInvoiceSent, setIsInvoiceSent] = useState(false);

  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: 'السلام عليكم، أنا خبير الهدايا الخاص بك في هديتي. يسعدني مساعدتك في تنسيق أجمل مفاجأة لمن تحب. كيف يمكنني خدمتك؟', sender: 'other', time: '11:15 ص' },
  ]);
  const [input, setInput] = useState('');

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    setMessages(prev => [...prev, { id: Date.now().toString(), text: input, sender: 'user', time: 'الآن' }]);
    setInput('');
  }, [input]);

  const handleAttachImage = useCallback(() => {
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      text: "تم إرفاق صورة للهدية المطلوبة 📸",
      sender: 'user',
      time: 'الآن'
    }]);
  }, []);

  const handleIssueInvoice = useCallback(() => {
    const gp = parseFloat(giftPrice) || 0;
    const sf = parseFloat(serviceFee) || 0;
    const df = parseFloat(deliveryFee) || 0;
    const total = gp + sf + df;

    if (!invoiceDesc) return;

    const invoiceMsg: Message = {
      id: Date.now().toString(),
      text: `فاتورة طلب: ${invoiceDesc}`,
      sender: 'user',
      time: 'الآن',
      isInvoice: true,
      invoiceData: {
        description: invoiceDesc,
        giftPrice: gp,
        serviceFee: sf,
        deliveryFee: df,
        total: total
      }
    };
    setMessages(prev => [...prev, invoiceMsg]);
    setIsInvoiceSent(true);
    setShowInvoiceModal(false);

    setInvoiceDesc('');
    setGiftPrice('');
    setServiceFee('');
    setDeliveryFee('');
  }, [invoiceDesc, giftPrice, serviceFee, deliveryFee]);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: Math.max(insets.top + 16, 24) }]}>
        <View style={styles.headerContent}>
          <Pressable onPress={onBack} style={styles.backButton}>
            <Feather name="chevron-right" size={24} color="#9CA3AF" />
          </Pressable>
          <Pressable onPress={() => setShowCourierProfile(true)} style={styles.userInfo}>
            <View style={styles.avatar}>
              <Image
                source={{ uri: userRole === 'customer' ? "https://picsum.photos/seed/courier1/100/100" : "https://picsum.photos/seed/user1/100/100" }}
                style={styles.avatarImage}
              />
            </View>
            <View>
              <Text style={styles.userName}>
                {userRole === 'customer' ? 'أحمد (المندوب)' : 'محمد (العميل)'}
              </Text>
              <Text style={styles.userStatus}>متصل الآن</Text>
            </View>
          </Pressable>
        </View>
        <Pressable onPress={() => setShowCancelOptions(true)} style={styles.cancelButton}>
          <Text style={styles.cancelText}>إلغاء الطلب</Text>
        </Pressable>
      </View>

      {/* Chat Area */}
      <ScrollView style={styles.chatContainer} contentContainerStyle={styles.chatContent}>
        {messages.map((msg) => (
          <View key={msg.id} style={[styles.messageContainer, msg.sender === 'user' ? styles.userMessage : styles.otherMessage]}>
            <Pressable
              onPress={msg.isInvoice ? onShowInvoice : undefined}
              style={[styles.messageBubble, msg.sender === 'user' ? styles.userBubble : styles.otherBubble]}
            >
              {msg.isInvoice ? (
                <View style={styles.invoiceContainer}>
                  <View style={styles.invoiceHeader}>
                    <Feather name="file-text" size={18} color="white" />
                    <Text style={styles.invoiceTitle}>فاتورة جديدة</Text>
                  </View>

                  <View style={styles.invoiceDetails}>
                    <View style={styles.invoiceRow}>
                      <Text style={styles.invoiceLabel}>قيمة الهدية</Text>
                      <Text style={styles.invoiceValue}>{msg.invoiceData?.giftPrice} ر.س</Text>
                    </View>
                    <View style={styles.invoiceRow}>
                      <Text style={styles.invoiceLabel}>رسوم الخدمة</Text>
                      <Text style={styles.invoiceValue}>{msg.invoiceData?.serviceFee} ر.س</Text>
                    </View>
                    <View style={styles.invoiceRow}>
                      <Text style={styles.invoiceLabel}>رسوم التوصيل</Text>
                      <Text style={styles.invoiceValue}>{msg.invoiceData?.deliveryFee} ر.س</Text>
                    </View>
                  </View>

                  <View style={styles.invoiceTotal}>
                    <Text style={styles.totalLabel}>الإجمالي النهائي</Text>
                    <Text style={styles.totalValue}>{msg.invoiceData?.total} ر.س</Text>
                  </View>
                </View>
              ) : (
                <Text style={[styles.messageText, msg.sender === 'user' ? styles.userText : styles.otherText]}>
                  {msg.text}
                </Text>
              )}
            </Pressable>
            <Text style={styles.messageTime}>{msg.time}</Text>
          </View>
        ))}
      </ScrollView>

      {/* Action Area */}
      <View style={styles.actionArea}>
        <View style={styles.actionButtons}>
          {userRole === 'customer' ? (
            <>
              <Pressable onPress={() => setShowGallery(true)} style={styles.galleryButton}>
                <Feather name="star" size={24} color="#E0AAFF" />
              </Pressable>
              <Pressable
                disabled={!isInvoiceSent}
                style={[styles.finishButton, !isInvoiceSent && styles.disabledButton]}
              >
                <Feather name="check-circle" size={18} color="white" />
                <Text style={styles.finishText}>إتمام الطلب والدفع</Text>
              </Pressable>
            </>
          ) : (
            <Pressable onPress={() => setShowInvoiceModal(true)} style={styles.invoiceButton}>
              <Feather name="plus" size={18} color="white" />
              <Text style={styles.invoiceButtonText}>إصدار فاتورة للعميل</Text>
            </Pressable>
          )}
        </View>

        <View style={styles.inputArea}>
          {userRole === 'customer' && (
            <Pressable onPress={handleAttachImage} style={styles.attachButton}>
              <Feather name="image" size={22} color="#9CA3AF" />
            </Pressable>
          )}
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="اكتب هنا..."
            placeholderTextColor="#9CA3AF"
          />
          <Pressable onPress={handleSend} style={styles.sendButton}>
            <Feather name="send" size={18} color="white" />
          </Pressable>
        </View>
      </View>

      {/* Profile Modal */}
      <Modal
        visible={showCourierProfile}
        animationType="fade"
        transparent={true}
        onRequestClose={() => setShowCourierProfile(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.profileModal}>
            <Pressable onPress={() => setShowCourierProfile(false)} style={styles.closeButton}>
              <Feather name="x" size={20} color="#9CA3AF" />
            </Pressable>

            <View style={styles.profileContent}>
              <View style={styles.profileAvatar}>
                <Image
                  source={{ uri: userRole === 'customer' ? "https://picsum.photos/seed/courier1/200/200" : "https://picsum.photos/seed/user1/200/200" }}
                  style={styles.profileImage}
                />
              </View>
              <Text style={styles.profileName}>
                {userRole === 'customer' ? 'أحمد بن فهد' : 'محمد العتيبي'}
              </Text>
              <View style={styles.rating}>
                <Feather name="star" size={20} color="#F59E0B" />
                <Text style={styles.ratingText}>4.8</Text>
              </View>

              {userRole === 'customer' && (
                <View style={styles.gallerySection}>
                  <View style={styles.galleryHeader}>
                    <Text style={styles.galleryTitle}>أطلع على هدايا العملاء</Text>
                    <Pressable onPress={() => { setShowCourierProfile(false); setShowGallery(true); }}>
                      <Text style={styles.viewAllText}>عرض الكل</Text>
                    </Pressable>
                  </View>
                  <View style={styles.galleryGrid}>
                    {COURIER_GALLERY.slice(0, 2).map((img, i) => (
                      <Image key={i} source={{ uri: img }} style={styles.galleryImage} />
                    ))}
                  </View>
                </View>
              )}

              <Pressable onPress={() => setShowCourierProfile(false)} style={styles.closeModalButton}>
                <Text style={styles.closeModalText}>إغلاق</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* Gallery Modal */}
      <Modal
        visible={showGallery}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowGallery(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.galleryModal}>
            <View style={styles.galleryModalHeader}>
              <Text style={styles.galleryModalTitle}>أطلع على هدايا العملاء</Text>
              <Pressable onPress={() => setShowGallery(false)} style={styles.closeButton}>
                <Feather name="x" size={20} color="#9CA3AF" />
              </Pressable>
            </View>
            <ScrollView style={styles.galleryScroll}>
              <View style={styles.galleryGridFull}>
                {COURIER_GALLERY.map((img, idx) => (
                  <Pressable
                    key={idx}
                    onPress={() => {
                      setInput(`أعجبني هذا التنسيق:`);
                      setShowGallery(false);
                    }}
                    style={styles.galleryItem}
                  >
                    <Image source={{ uri: img }} style={styles.galleryItemImage} />
                  </Pressable>
                ))}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Invoice Modal */}
      <Modal
        visible={showInvoiceModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowInvoiceModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.invoiceModal}>
            <View style={styles.invoiceModalHeader}>
              <Text style={styles.invoiceModalTitle}>إصدار فاتورة</Text>
              <Pressable onPress={() => setShowInvoiceModal(false)} style={styles.closeButton}>
                <Feather name="x" size={20} color="#9CA3AF" />
              </Pressable>
            </View>

            <ScrollView style={styles.invoiceForm}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>وصف الطلب</Text>
                <TextInput
                  style={styles.invoiceInput}
                  placeholder="مثال: باقة ورد + تغليف"
                  value={invoiceDesc}
                  onChangeText={setInvoiceDesc}
                  placeholderTextColor="#9CA3AF"
                />
              </View>

              <View style={styles.priceInputs}>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>قيمة الهدية</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder="0.00"
                    value={giftPrice}
                    onChangeText={setGiftPrice}
                    keyboardType="numeric"
                    placeholderTextColor="#9CA3AF"
                  />
                </View>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>رسوم الخدمة</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder="0.00"
                    value={serviceFee}
                    onChangeText={setServiceFee}
                    keyboardType="numeric"
                    placeholderTextColor="#9CA3AF"
                  />
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>رسوم التوصيل</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder="0.00"
                  value={deliveryFee}
                  onChangeText={setDeliveryFee}
                  keyboardType="numeric"
                  placeholderTextColor="#9CA3AF"
                />
              </View>

              <View style={styles.totalBox}>
                <Text style={styles.totalLabel}>الإجمالي النهائي</Text>
                <Text style={styles.totalAmount}>
                  {(parseFloat(giftPrice) || 0) + (parseFloat(serviceFee) || 0) + (parseFloat(deliveryFee) || 0)} ر.س
                </Text>
              </View>

              <Pressable onPress={handleIssueInvoice} style={styles.sendInvoiceButton}>
                <Text style={styles.sendInvoiceText}>إرسال الفاتورة للعميل</Text>
              </Pressable>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Cancel Options Modal */}
      <Modal
        visible={showCancelOptions}
        animationType="fade"
        transparent={true}
        onRequestClose={() => setShowCancelOptions(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.cancelModal}>
            <View style={styles.cancelModalHeader}>
              <Text style={styles.cancelModalTitle}>إلغاء الطلب</Text>
              <Pressable onPress={() => setShowCancelOptions(false)} style={styles.closeButton}>
                <Feather name="x" size={20} color="#9CA3AF" />
              </Pressable>
            </View>

            <View style={styles.cancelOptions}>
              <Pressable style={styles.cancelOption}>
                <View style={styles.cancelOptionIcon}>
                  <Feather name="message-circle" size={20} color="#EF4444" />
                </View>
                <View style={styles.cancelOptionContent}>
                  <Text style={styles.cancelOptionTitle}>تواصل مع المندوب</Text>
                  <Text style={styles.cancelOptionSubtitle}>تحدث مع المندوب لحل المشكلة</Text>
                </View>
              </Pressable>

              <Pressable style={styles.cancelOption}>
                <View style={styles.cancelOptionIcon}>
                  <Feather name="headphones" size={20} color="#F59E0B" />
                </View>
                <View style={styles.cancelOptionContent}>
                  <Text style={styles.cancelOptionTitle}>الدعم الفني</Text>
                  <Text style={styles.cancelOptionSubtitle}>تواصل مع فريق الدعم</Text>
                </View>
              </Pressable>

              <Pressable style={styles.cancelOption}>
                <View style={styles.cancelOptionIcon}>
                  <Feather name="refresh-ccw" size={20} color="#10B981" />
                </View>
                <View style={styles.cancelOptionContent}>
                  <Text style={styles.cancelOptionTitle}>إعادة جدولة</Text>
                  <Text style={styles.cancelOptionSubtitle}>غير موعد التوصيل</Text>
                </View>
              </Pressable>

              <Pressable style={[styles.cancelOption, styles.cancelFinal]}>
                <View style={styles.cancelOptionIcon}>
                  <Feather name="x-circle" size={20} color="#DC2626" />
                </View>
                <View style={styles.cancelOptionContent}>
                  <Text style={styles.cancelOptionTitle}>إلغاء نهائي</Text>
                  <Text style={styles.cancelOptionSubtitle}>إلغاء الطلب بشكل نهائي</Text>
                </View>
              </Pressable>
            </View>

            <Pressable onPress={() => setShowCancelOptions(false)} style={styles.cancelKeepButton}>
              <Text style={styles.cancelKeepText}>الاحتفاظ بالطلب</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
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
  headerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backButton: {
    padding: 8,
    backgroundColor: 'white',
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  userInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(224, 170, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
    borderRadius: 20,
  },
  userName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  userStatus: {
    fontSize: 10,
    color: '#E0AAFF',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  cancelButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  cancelText: {
    fontSize: 10,
    color: '#EF4444',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  chatContainer: {
    flex: 1,
  },
  chatContent: {
    padding: 24,
    gap: 24,
  },
  messageContainer: {
    maxWidth: '85%',
  },
  userMessage: {
    alignSelf: 'flex-end',
    alignItems: 'flex-end',
  },
  otherMessage: {
    alignSelf: 'flex-start',
    alignItems: 'flex-start',
  },
  messageBubble: {
    borderRadius: 28,
    paddingHorizontal: 20,
    paddingVertical: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  userBubble: {
    backgroundColor: '#E0AAFF',
    borderBottomRightRadius: 0,
  },
  otherBubble: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#F9FAFB',
    borderBottomLeftRadius: 0,
  },
  messageText: {
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 20,
  },
  userText: {
    color: 'white',
  },
  otherText: {
    color: '#374151',
  },
  messageTime: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: 'bold',
    marginTop: 6,
    marginHorizontal: 8,
  },
  invoiceContainer: {
    minWidth: 220,
  },
  invoiceHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingBottom: 12,
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.2)',
  },
  invoiceTitle: {
    fontSize: 16,
    fontWeight: '900',
    color: 'white',
  },
  invoiceDetails: {
    gap: 8,
  },
  invoiceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  invoiceLabel: {
    fontSize: 10,
    fontWeight: 'bold',
    color: 'white',
  },
  invoiceValue: {
    fontSize: 12,
    fontWeight: '900',
    color: 'white',
  },
  invoiceTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    marginTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.2)',
  },
  totalLabel: {
    fontSize: 10,
    fontWeight: '900',
    color: 'rgba(255, 255, 255, 0.8)',
    textTransform: 'uppercase',
  },
  totalValue: {
    fontSize: 24,
    fontWeight: '900',
    color: 'white',
  },
  actionArea: {
    padding: 16,
    backgroundColor: 'white',
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    gap: 16,
    paddingBottom: 32,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  galleryButton: {
    width: 56,
    height: 56,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  finishButton: {
    flex: 1,
    height: 56,
    backgroundColor: '#E0AAFF',
    borderRadius: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  disabledButton: {
    backgroundColor: '#E5E7EB',
  },
  finishText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  invoiceButton: {
    flex: 1,
    height: 56,
    backgroundColor: '#E0AAFF',
    borderRadius: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  invoiceButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  inputArea: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(249, 250, 251, 0.5)',
    borderRadius: 24,
    paddingHorizontal: 6,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  attachButton: {
    padding: 10,
  },
  input: {
    flex: 1,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#374151',
    paddingHorizontal: 16,
    textAlign: 'right',
  },
  sendButton: {
    width: 48,
    height: 48,
    backgroundColor: '#E0AAFF',
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  profileModal: {
    backgroundColor: 'white',
    borderRadius: 48,
    padding: 32,
    width: '90%',
    maxHeight: '85%',
  },
  closeButton: {
    position: 'absolute',
    top: 24,
    left: 24,
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
  },
  profileContent: {
    alignItems: 'center',
    gap: 16,
  },
  profileAvatar: {
    width: 96,
    height: 96,
    borderRadius: 48,
    overflow: 'hidden',
    borderWidth: 4,
    borderColor: 'white',
  },
  profileImage: {
    width: '100%',
    height: '100%',
  },
  profileName: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
  },
  rating: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.2)',
  },
  ratingText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#F59E0B',
  },
  gallerySection: {
    width: '100%',
    marginTop: 24,
  },
  galleryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  galleryTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  viewAllText: {
    fontSize: 10,
    fontWeight: '900',
    color: '#E0AAFF',
    textTransform: 'uppercase',
  },
  galleryGrid: {
    flexDirection: 'row',
    gap: 8,
  },
  galleryImage: {
    width: 80,
    height: 80,
    borderRadius: 16,
  },
  closeModalButton: {
    width: '100%',
    height: 56,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
  },
  closeModalText: {
    fontSize: 18,
    fontWeight: '900',
    color: 'white',
  },
  galleryModal: {
    backgroundColor: 'white',
    borderTopLeftRadius: 48,
    borderTopRightRadius: 48,
    width: '100%',
    height: '80%',
    position: 'absolute',
    bottom: 0,
  },
  galleryModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 32,
    paddingBottom: 24,
  },
  galleryModalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1F2937',
  },
  galleryScroll: {
    flex: 1,
    paddingHorizontal: 32,
  },
  galleryGridFull: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
    paddingBottom: 32,
  },
  galleryItem: {
    width: '48%',
    aspectRatio: 1,
    borderRadius: 32,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: 'white',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  galleryItemImage: {
    width: '100%',
    height: '100%',
  },
  invoiceModal: {
    backgroundColor: 'white',
    borderTopLeftRadius: 48,
    borderTopRightRadius: 48,
    width: '100%',
    height: '90%',
    position: 'absolute',
    bottom: 0,
  },
  invoiceModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 32,
    paddingBottom: 24,
  },
  invoiceModalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1F2937',
  },
  invoiceForm: {
    paddingHorizontal: 32,
  },
  inputGroup: {
    marginBottom: 24,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 8,
  },
  invoiceInput: {
    width: '100%',
    height: 56,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: 24,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  priceInputs: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 24,
  },
  priceInput: {
    flex: 1,
    height: 56,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: 24,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'left',
  },
  totalBox: {
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(224, 170, 255, 0.2)',
    marginBottom: 24,
  },
  totalAmount: {
    fontSize: 20,
    fontWeight: '900',
    color: '#E0AAFF',
  },
  sendInvoiceButton: {
    width: '100%',
    height: 64,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  sendInvoiceText: {
    fontSize: 18,
    fontWeight: '900',
    color: 'white',
  },
  cancelModal: {
    backgroundColor: 'white',
    borderRadius: 32,
    padding: 24,
    width: '90%',
    maxWidth: 400,
  },
  cancelModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  cancelModalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1F2937',
  },
  cancelOptions: {
    gap: 12,
    marginBottom: 24,
  },
  cancelOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  cancelFinal: {
    backgroundColor: 'rgba(220, 38, 38, 0.05)',
    borderColor: 'rgba(220, 38, 38, 0.2)',
  },
  cancelOptionIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  cancelOptionContent: {
    flex: 1,
  },
  cancelOptionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: 2,
  },
  cancelOptionSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  cancelKeepButton: {
    width: '100%',
    height: 48,
    backgroundColor: '#E0AAFF',
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelKeepText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
  },
});
