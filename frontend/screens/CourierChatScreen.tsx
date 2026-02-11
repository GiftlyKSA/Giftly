
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, Pressable, ScrollView, TextInput, StyleSheet, Image, Modal, Alert, Keyboard, ActivityIndicator } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Message, ChatMessage } from '../types';
import { useAuth } from '../App';
import { getOrder, OrderResponse, getConversationMessages, sendMessage, createOrGetConversation, getConversationByOrder, Conversation, createInvoice, updateInvoice } from '../api';
import { webSocketService } from '../WebSocketService';

interface Props {
  orderId?: string | null;
  onBack: () => void;
  onShowInvoice?: (invoiceId: string) => void;
  chatState?: {
    messages: Message[];
    input: string;
    order: OrderResponse | null;
    conversation: Conversation | null;
  };
  onChatStateChange?: (state: {
    messages: Message[];
    input: string;
    order: OrderResponse | null;
    conversation: Conversation | null;
  }) => void;
}

export const CourierChatScreen: React.FC<Props> = ({ orderId, onBack, onShowInvoice, chatState, onChatStateChange }) => {
  const insets = useSafeAreaInsets();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(chatState?.input || '');

  const [order, setOrder] = useState<OrderResponse | null>(chatState?.order || null);
  const [loadingOrder, setLoadingOrder] = useState(false);

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [invoiceDescription, setInvoiceDescription] = useState('');
  const [giftPrice, setGiftPrice] = useState('');
  const [serviceFee, setServiceFee] = useState('');
  const [deliveryFee, setDeliveryFee] = useState('');
  const [creatingInvoice, setCreatingInvoice] = useState(false);

  const { token, userData } = useAuth();
  const onChatStateChangeRef = useRef(onChatStateChange);
  const scrollViewRef = useRef<ScrollView>(null);

  // Update the ref whenever onChatStateChange changes
  useEffect(() => {
    onChatStateChangeRef.current = onChatStateChange;
  }, [onChatStateChange]);

  // Initialize state when orderId or chatState changes
  useEffect(() => {
    if (chatState) {
      setMessages(chatState.messages || []);
      setInput(chatState.input || '');
      setOrder(chatState.order || null);
      setConversation(chatState.conversation || null);
      setInitialLoading(false); // Data is already available from chatState
    } else {
      // Reset to initial state for new orders
      setMessages([]);
      setInput('');
      setOrder(null);
      setConversation(null);
      setInitialLoading(true); // Start loading
    }

    // Fetch order details if we have orderId and token
    if (orderId && token && (!chatState?.order || chatState.order.order_id !== orderId)) {
      fetchOrderDetails();
    }
  }, [orderId, chatState, token]);

  // Load conversation when order is available (conversation is created with order)
  useEffect(() => {
    const loadConversation = async () => {
      if (!order || !token) {
        return;
      }

      try {
        const conv = await getConversationByOrder(token, order.id);
        setConversation(conv);
      } catch (error) {
        console.error('Failed to load conversation:', error);
      }
    };

    loadConversation();
  }, [order, token]);

  // Load messages when conversation changes
  useEffect(() => {
    const loadMessages = async () => {
      if (!conversation || !token) {
        setMessages([]);
        return;
      }

      setLoadingMessages(true);
      try {
        const chatMessages = await getConversationMessages(token, conversation.id);
        const customerId = order?.created_by_user_id;
        const uiMessages = chatMessages.map(chatMsg => convertChatMessageToMessage(chatMsg, customerId));
        setMessages(uiMessages);
        scrollToBottom();
      } catch (error) {
        console.error('Failed to load messages:', error);
        Alert.alert('خطأ', 'فشل في تحميل الرسائل');
      } finally {
        setLoadingMessages(false);
      }
    };

    loadMessages();
  }, [conversation, token, convertChatMessageToMessage, scrollToBottom, order?.created_by_user_id]);

  // Set initial loading to false when data is ready
  useEffect(() => {
    if (initialLoading) {
      const hasOrder = !!order;
      const hasConversation = !!conversation;
      const messagesLoaded = !loadingMessages;

      // Wait for order, conversation, and messages to be loaded
      if (hasOrder && hasConversation && messagesLoaded) {
        setInitialLoading(false);
      }
    }
  }, [order, conversation, loadingMessages, initialLoading]);

  // Keyboard handling
  useEffect(() => {
    const keyboardDidShowListener = Keyboard.addListener('keyboardDidShow', (e) => {
      setKeyboardHeight(e.endCoordinates.height);
    });

    const keyboardDidHideListener = Keyboard.addListener('keyboardDidHide', () => {
      setKeyboardHeight(0);
    });

    return () => {
      keyboardDidShowListener.remove();
      keyboardDidHideListener.remove();
    };
  }, []);

  // Convert ChatMessage to Message for UI display
  const convertChatMessageToMessage = useCallback((chatMsg: ChatMessage, customerId?: number): Message => {
    const isCustomer = customerId && chatMsg.sender_id === customerId;
    const date = new Date(chatMsg.sent_at);
    const timeString = date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });

    let text = chatMsg.content;
    if (chatMsg.message_type === 'invoice' && chatMsg.invoice_description) {
      text = `فاتورة: ${chatMsg.invoice_description}\nالمجموع: ${chatMsg.invoice_total} ريال`;
    }

    return {
      id: chatMsg.id.toString(),
      text,
      sender: isCustomer ? 'customer' : 'courier',
      time: timeString,
      isInvoice: chatMsg.message_type === 'invoice',
      invoiceData: chatMsg.message_type === 'invoice' ? {
        description: chatMsg.invoice_description || '',
        giftPrice: chatMsg.invoice_gift_price || 0,
        serviceFee: chatMsg.invoice_service_fee || 0,
        deliveryFee: chatMsg.invoice_delivery_fee || 0,
        total: chatMsg.invoice_total || 0,
      } : undefined,
    };
  }, []); // No dependencies needed now

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);
  }, []);

  // WebSocket setup
  useEffect(() => {
    if (!conversation) return;

    const room = `chat_${conversation.id}`;

    // Join the chat room
    webSocketService.joinRoom(room);

    // Listen for chat messages
    const handleChatMessage = (message: any) => {
      if (message.room === room) {
        const newMessage = convertChatMessageToMessage(message.data, order?.created_by_user_id);
        setMessages(prev => {
          if (prev.some(m => m.id === newMessage.id)) return prev;
          return [...prev, newMessage];
        });
        scrollToBottom();
      }
    };

    webSocketService.onChatMessage(handleChatMessage);

    // Cleanup function
    return () => {
      webSocketService.leaveRoom(room);
      webSocketService.off('chat_message', handleChatMessage);
    };
  }, [conversation, convertChatMessageToMessage, scrollToBottom, order?.created_by_user_id]);

  // Listen for invoice creation events
  useEffect(() => {
    const handleInvoiceCreated = (message: any) => {
      console.log('Invoice created event received in courier chat:', message);
      if (message.data.order_id === order?.order_id) {
        // Update order with invoice data
        setOrder(prev => prev ? {
          ...prev,
          invoice: message.data.invoice,
          status: message.data.status,
          updated_at: message.data.updated_at
        } : null);
      }
    };

    webSocketService.on('invoice_created', handleInvoiceCreated);

    return () => {
      webSocketService.off('invoice_created', handleInvoiceCreated);
    };
  }, [conversation, convertChatMessageToMessage, scrollToBottom, order?.created_by_user_id]);

  // Cleanup on unmount

  const fetchOrderDetails = async () => {
    if (!orderId || !token) {
      console.log('Courier fetchOrderDetails: Missing orderId or token', { orderId, token: !!token });
      return;
    }
    console.log('Courier fetchOrderDetails: Fetching order with ID:', orderId);
    setLoadingOrder(true);
    try {
      const orderDetails = await getOrder(token, orderId);
      console.log('Courier fetchOrderDetails: Successfully fetched order:', JSON.stringify(orderDetails, null, 2));
      console.log('Courier fetchOrderDetails: Order invoice data:', orderDetails.invoice ? JSON.stringify(orderDetails.invoice, null, 2) : 'No invoice data');
      setOrder(orderDetails);
    } catch (error: any) {
      console.error('Courier fetchOrderDetails: Failed to fetch order details:', error);
      Alert.alert('خطأ', error.message || 'فشل في تحميل تفاصيل الطلب');
    } finally {
      setLoadingOrder(false);
    }
  };

  const handleSend = async () => {
    console.log('🔄 Courier handleSend: Starting send process');
    console.log('📝 Input:', input.trim());
    console.log('💬 Conversation:', !!conversation);
    console.log('🔑 Token:', !!token);
    console.log('⏳ Sending:', sendingMessage);
    console.log('📦 Order status:', order?.status);

    if (!input.trim() || !token || sendingMessage) {
      console.log('❌ Courier handleSend: Early return - conditions not met');
      console.log('   - Has input:', !!input.trim());
      console.log('   - Has token:', !!token);
      console.log('   - Not sending:', !sendingMessage);
      return;
    }

    // Immediately disable sending to prevent multiple clicks
    console.log('🔒 Disabling send button');
    setSendingMessage(true);

    // If no conversation but order is assigned, try to create conversation first
    let currentConversation = conversation;
    if (!currentConversation && order?.status === 'received by courier' && order.created_by_user_id) {
      console.log('🏗️ Creating conversation for assigned order...');
      try {
        currentConversation = await createOrGetConversation(token, order.created_by_user_id);
        setConversation(currentConversation);
        console.log('✅ Conversation created:', currentConversation.id);
      } catch (error: any) {
        console.error('❌ Failed to create conversation:', error);
        setSendingMessage(false); // Re-enable on error
        Alert.alert('خطأ', 'فشل في إنشاء المحادثة');
        return;
      }
    }

    if (!currentConversation) {
      console.log('❌ No conversation available');
      setSendingMessage(false); // Re-enable on error
        Alert.alert('خطأ', 'لا توجد محادثة متاحة');
      return;
    }

    const messageContent = input.trim();
    console.log('📤 Sending message:', messageContent.substring(0, 50) + (messageContent.length > 50 ? '...' : ''));
    setInput(''); // Clear input immediately

    try {
      // Send message via WebSocket
      const room = `chat_${currentConversation.id}`;
      console.log('🌐 Sending message via WebSocket to room:', room);
      webSocketService.sendChatMessage(room, messageContent, 'text');

      // Optimistic update - add message to UI immediately
      const optimisticMessage: Message = {
        id: `temp_${Date.now()}`,
        text: messageContent,
        sender: 'courier',
        time: new Date().toLocaleTimeString('ar-SA', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true
        }),
      };

      setMessages(prev => [...prev, optimisticMessage]);
      scrollToBottom();
      console.log('✅ Message sent via WebSocket');
    } catch (error: any) {
      console.error('❌ Error sending message:', error);
      // Revert input on error
      setInput(messageContent);
      Alert.alert('خطأ', error.message || 'فشل في إرسال الرسالة');
    } finally {
      console.log('🔓 Re-enabling send button');
      setSendingMessage(false);
    }
  };

  const handleAttachImage = () => {
    // محاكاة إرسال صورة
    const newMessage: Message = {
      id: Date.now().toString(),
      text: "تم إرفاق صورة 📸",
      sender: 'courier',
      time: 'الآن',
    };
    setMessages([...messages, newMessage]);
  };

  const handleInvoicePress = () => {
    // Pre-fill form if editing existing invoice
    if (order?.invoice) {
      setInvoiceDescription(order.invoice.description || '');
      // Amounts are now stored as floats directly, no need to divide by 1000
      setGiftPrice(order.invoice.order_only_price.toString());
      setServiceFee(order.invoice.service_fee.toString());
      setDeliveryFee(order.invoice.courier_fee.toString());
    } else {
      // Reset form for new invoice
      setInvoiceDescription('');
      setGiftPrice('');
      setServiceFee('');
      setDeliveryFee('');
    }
    setShowInvoiceModal(true);
  };

  const handleCreateInvoice = async () => {
    if (!order || !token || !conversation) {
      Alert.alert('خطأ', 'معلومات غير كافية');
      return;
    }

    const giftPriceNum = parseFloat(giftPrice) || 0;
    const serviceFeeNum = parseFloat(serviceFee) || 0;
    const deliveryFeeNum = parseFloat(deliveryFee) || 0;

    // Validate non-negative amounts
    if (giftPriceNum < 0 || serviceFeeNum < 0 || deliveryFeeNum < 0) {
      Alert.alert('خطأ', 'يجب أن تكون جميع المبالغ موجبة أو صفر');
      return;
    }

    const total = giftPriceNum + serviceFeeNum + deliveryFeeNum;

    if (total <= 0) {
      Alert.alert('خطأ', 'يجب أن يكون المجموع أكبر من صفر');
      return;
    }

    setCreatingInvoice(true);
    try {
      const invoiceData = {
        order_id: order.id,
        description: invoiceDescription.trim(),
        full_amount: parseFloat(total.toFixed(3)), // Total amount as float with up to 3 decimal places
        service_fee: parseFloat(serviceFeeNum.toFixed(3)), // Service fee as float with up to 3 decimal places
        order_only_price: parseFloat(giftPriceNum.toFixed(3)), // Gift price as float with up to 3 decimal places
        courier_fee: parseFloat(deliveryFeeNum.toFixed(3)), // Delivery fee as float with up to 3 decimal places
      };

      let result;
      const isEditing = !!order.invoice;

      if (isEditing) {
        // Update existing invoice
        result = await updateInvoice(token, order.invoice.invoice_id, invoiceData);
      } else {
        // Create new invoice
        result = await createInvoice(token, invoiceData);
      }

      // Update local order state
      setOrder(prev => prev ? {
        ...prev,
        invoice: {
          id: result.id,
          invoice_id: result.invoice_id,
          description: invoiceDescription,
          order_only_price: invoiceData.order_only_price,
          service_fee: invoiceData.service_fee,
          courier_fee: invoiceData.courier_fee,
          full_amount: invoiceData.full_amount,
          status: 'unpaid',
          created_at: result.created_at,
          updated_at: result.updated_at,
        }
      } : null);

      setShowInvoiceModal(false);
      const totalPrice = parseFloat(total.toFixed(2));
      Alert.alert('نجح', isEditing ? `تم تحديث الفاتورة بنجاح\nالمبلغ الإجمالي: ${totalPrice} ريال` : `تم إنشاء الفاتورة بنجاح\nالمبلغ الإجمالي: ${totalPrice} ريال`);
    } catch (error: any) {
      console.error('Error creating/updating invoice:', error);
      Alert.alert('خطأ', error.message || 'فشل في إنشاء/تحديث الفاتورة');
    } finally {
      setCreatingInvoice(false);
    }
  };



  // No loading screen - show content immediately for better UX

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: Math.max(insets.top + 16, 24) }]}>
        <View style={styles.headerContent}>
          <Pressable onPress={onBack} style={styles.backButton}>
            <Feather name="chevron-right" size={24} color="#9CA3AF" />
          </Pressable>
          <Pressable style={styles.userInfo}>
            <View style={styles.avatar}>
              <Image
                source={{ uri: "https://picsum.photos/seed/customer/100/100" }}
                style={styles.avatarImage}
              />
              <View style={styles.onlineIndicator} />
            </View>
            <View>
              <Text style={styles.userName}>
                {order?.created_by_user?.name || 'العميل'}
              </Text>
            </View>
          </Pressable>
        </View>
        <View style={styles.headerActions}>
          {/* Cancel order functionality removed for couriers */}
        </View>
      </View>

      {/* Chat Area */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.chatContainer}
        contentContainerStyle={styles.chatContent}
      >
        {messages.length === 0 && conversation && (
          <View style={styles.emptyChatContainer}>
            <Text style={styles.emptyChatText}>ابدأ المحادثة الآن</Text>
          </View>
        )}
        {messages.map((msg) => (
          <View key={msg.id} style={[styles.messageContainer, msg.sender === 'courier' ? styles.customerMessage : styles.courierMessage]}>
            <View style={[styles.messageBubble, msg.sender === 'courier' ? styles.customerBubble : styles.courierBubble]}>
              <Text style={[styles.messageText, msg.sender === 'courier' ? styles.customerText : styles.courierText]}>
                {msg.text}
              </Text>
            </View>
            <Text style={styles.messageTime}>{msg.time}</Text>
          </View>
        ))}
      </ScrollView>

      {/* Invoice Button - Above Input Area */}
      {order && (
        <View style={styles.invoiceButtonContainer}>
          <Pressable onPress={handleInvoicePress} style={styles.invoiceButton}>
            <Feather name="file-text" size={16} color="#E0AAFF" />
            <Text style={styles.invoiceButtonText}>
              {order.invoice ? 'تعديل الفاتورة' : 'إضافة فاتورة'}
            </Text>
          </Pressable>
        </View>
      )}

      {/* Input Area */}
      <View style={[styles.inputArea, { paddingBottom: Math.max(insets.bottom, 16) + keyboardHeight }]}>
        <View style={styles.inputContainer}>
          <Pressable onPress={handleAttachImage} style={styles.attachButton}>
            <Feather name="image" size={22} color="#9CA3AF" />
          </Pressable>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder={order?.status === 'received by courier' ? "اكتب رسالتك هنا..." : "في انتظار تعيين مندوب..."}
            placeholderTextColor="#9CA3AF"
            editable={order?.status === 'received by courier'}
          />
          <Pressable onPress={handleSend} style={[styles.sendButton, { backgroundColor: sendingMessage ? '#9CA3AF' : '#E0AAFF', shadowColor: sendingMessage ? '#9CA3AF' : '#E0AAFF' }]} disabled={sendingMessage}>
            {sendingMessage ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <Feather name="send" size={18} color="white" />
            )}
          </Pressable>
        </View>
      </View>

      {/* Invoice Creation Modal */}
      <Modal
        visible={showInvoiceModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowInvoiceModal(false)}
      >
        <View style={styles.invoiceModal}>
          <View style={styles.invoiceModalHeader}>
            <Text style={styles.invoiceModalTitle}>
              {order?.invoice ? 'تعديل الفاتورة' : 'إضافة فاتورة'}
            </Text>
            <Pressable onPress={() => setShowInvoiceModal(false)} style={styles.closeButton}>
              <Feather name="x" size={20} color="#9CA3AF" />
            </Pressable>
          </View>

          <ScrollView style={styles.invoiceForm}>
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>وصف الفاتورة</Text>
              <TextInput
                style={styles.invoiceInput}
                value={invoiceDescription}
                onChangeText={setInvoiceDescription}
                placeholder="اكتب وصف الفاتورة هنا..."
                placeholderTextColor="#9CA3AF"
                multiline
                numberOfLines={3}
                textAlignVertical="top"
              />
            </View>

            <View style={styles.priceInputs}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>سعر الهدية</Text>
                <TextInput
                  style={styles.priceInput}
                  value={giftPrice}
                  onChangeText={setGiftPrice}
                  placeholder="0.00"
                  keyboardType="decimal-pad"
                  textAlign="left"
                />
              </View>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>رسوم الخدمة</Text>
                <TextInput
                  style={styles.priceInput}
                  value={serviceFee}
                  onChangeText={setServiceFee}
                  placeholder="0.00"
                  keyboardType="decimal-pad"
                  textAlign="left"
                />
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>رسوم التوصيل</Text>
              <TextInput
                style={styles.invoiceInput}
                value={deliveryFee}
                onChangeText={setDeliveryFee}
                placeholder="0.00"
                keyboardType="decimal-pad"
                textAlign="left"
              />
            </View>

            <View style={styles.totalBox}>
              <Text style={styles.totalLabel}>المجموع الكلي</Text>
              <Text style={styles.totalAmount}>
                {(parseFloat(giftPrice || '0') + parseFloat(serviceFee || '0') + parseFloat(deliveryFee || '0')).toFixed(2)} ر.س
              </Text>
            </View>

            <Pressable
              onPress={handleCreateInvoice}
              disabled={creatingInvoice}
              style={[styles.sendInvoiceButton, creatingInvoice && { opacity: 0.6 }]}
            >
              {creatingInvoice ? (
                <ActivityIndicator size="small" color="white" />
              ) : (
                <Text style={styles.sendInvoiceText}>
                  {order?.invoice ? 'تحديث الفاتورة' : 'إرسال الفاتورة'}
                </Text>
              )}
            </Pressable>
          </ScrollView>
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
    fontSize: 14,
    fontWeight: '900',
    color: '#6B7280',
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
  headerActions: {
    flexDirection: 'row',
    gap: 8,
  },
  onlineIndicator: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#10B981',
    borderWidth: 2,
    borderColor: 'white',
  },
  customerMessage: {
    alignSelf: 'flex-start',
    alignItems: 'flex-start',
  },
  courierMessage: {
    alignSelf: 'flex-end',
    alignItems: 'flex-end',
  },
  customerBubble: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#F9FAFB',
    borderBottomLeftRadius: 0,
  },
  courierBubble: {
    backgroundColor: '#E0AAFF',
    borderBottomRightRadius: 0,
  },
  customerText: {
    color: '#374151',
  },
  courierText: {
    color: 'white',
  },
  emptyChatContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyChatText: {
    fontSize: 16,
    color: '#9CA3AF',
    textAlign: 'center',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(249, 250, 251, 0.5)',
    borderRadius: 24,
    paddingHorizontal: 6,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  invoiceButtonBottom: {
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(224, 170, 255, 0.2)',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    alignSelf: 'center',
  },
  invoiceButtonTextBottom: {
    fontSize: 12,
    color: '#E0AAFF',
    fontWeight: 'bold',
  },
  invoiceButtonContainer: {
    paddingHorizontal: 24,
    paddingBottom: 12,
  },
  invoiceButton: {
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(224, 170, 255, 0.2)',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    alignSelf: 'center',
  },
  invoiceButtonText: {
    fontSize: 12,
    color: '#E0AAFF',
    fontWeight: 'bold',
  },
  initialLoadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  initialLoadingText: {
    marginTop: 16,
    fontSize: 18,
    color: '#6B7280',
    textAlign: 'center',
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
  cancelModalSubtitle: {
    fontSize: 16,
    color: '#6B7280',
    fontWeight: '500',
    marginBottom: 20,
  },
  reasonsList: {
    gap: 10,
    marginBottom: 20,
  },
  reasonOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  selectedReasonOption: {
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderColor: '#E0AAFF',
  },
  reasonText: {
    fontSize: 16,
    color: '#374151',
    fontWeight: '500',
  },
  selectedReasonText: {
    color: '#E0AAFF',
    fontWeight: 'bold',
  },
  customReasonInput: {
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#374151',
    textAlignVertical: 'top',
    marginBottom: 20,
    minHeight: 80,
  },
  cancelModalActions: {
    flexDirection: 'row',
    gap: 12,
  },
  cancelModalCancelButton: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    paddingVertical: 16,
    borderRadius: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  cancelModalCancelText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#6B7280',
  },
  cancelModalConfirmButton: {
    flex: 1,
    backgroundColor: '#EF4444',
    paddingVertical: 16,
    borderRadius: 16,
    alignItems: 'center',
  },
  cancelModalConfirmText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
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
});
