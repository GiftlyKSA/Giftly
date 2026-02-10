
import React, { useState, useEffect } from 'react';
import { View, Text, Pressable, ScrollView, StyleSheet, Image, Dimensions, Alert, TextInput, RefreshControl } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../App';
import { getAvailableOrdersForCourier, acceptOrder, getCourierActiveOrders, getCourierAllOrders, getWallet, requestWalletDeposit, updateUserDetails, OrderResponse, WalletResponse, getCourierStats, CourierStatsResponse } from '../api';

interface Props {
  onLogout: () => void;
  onAcceptOrder: () => void;
  onNavigateToChat?: (orderId: string) => void;
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  theme: {
    backgroundColor: string;
    textColor: string;
    secondaryTextColor: string;
    cardBackground: string;
    borderColor: string;
  };
}

type OrderStatus = 'PREPARING' | 'DELIVERING' | 'DELIVERED';

interface ActiveOrder {
  id: string;
  item: string;
  customer: string;
  status: OrderStatus;
  location: string;
}

const NEW_ORDERS = [
  { id: '101', item: 'باقة ورد عملاقة', price: 25 },
  { id: '102', item: 'تغليف هدايا عيد ميلاد', price: 15 },
  { id: '103', item: 'تنسيق شوكولاتة باتشي', price: 35 },
];

const NOTIFICATIONS = [
  { id: '1', title: 'طلب جديد متاح!', body: 'هناك طلب توصيل باقة ورد بالقرب منك.', time: 'منذ دقيقتين', type: 'new_order' },
  { id: '2', title: 'تم تأكيد الدفع', body: 'قام العميل محمد بتأكيد دفع الفاتورة #8742.', time: 'منذ ساعة', type: 'payment' },
  { id: '3', title: 'تقييم جديد ⭐', body: 'حصلت على تقييم 5 نجوم من العميل سارة.', time: 'أمس', type: 'rating' },
];

const PORTFOLIO_IMAGES = [
  'https://picsum.photos/seed/gift1/400/400',
  'https://picsum.photos/seed/gift2/400/400',
  'https://picsum.photos/seed/gift3/400/400',
  'https://picsum.photos/seed/gift4/400/400',
];

export const CourierHomeScreen: React.FC<Props> = ({ onLogout, onAcceptOrder, onNavigateToChat, isDarkMode, toggleDarkMode, theme }) => {
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<'available' | 'active' | 'wallet' | 'profile' | 'notifications' | 'previous'>('available');
  const [portfolio, setPortfolio] = useState(PORTFOLIO_IMAGES);
  const { userData, token } = useAuth();

  // Real data states
  const [availableOrders, setAvailableOrders] = useState<OrderResponse[]>([]);
  const [activeOrders, setActiveOrders] = useState<OrderResponse[]>([]);
  const [previousOrders, setPreviousOrders] = useState<OrderResponse[]>([]);
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [courierStats, setCourierStats] = useState<CourierStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [depositAmount, setDepositAmount] = useState('');

  // Load data on component mount and when tab changes
  useEffect(() => {
    if (token) {
      loadData();
    }
  }, [activeTab, token]);

  const loadData = async () => {
    if (!token) {
      console.log('CourierHomeScreen: No token available');
      return;
    }

    console.log(`CourierHomeScreen: Loading data for tab: ${activeTab}`);

    try {
      // Always fetch courier stats for the stats display
      console.log('CourierHomeScreen: Fetching courier stats...');
      const stats = await getCourierStats(token);
      console.log('CourierHomeScreen: Received courier stats:', stats);
      setCourierStats(stats);

      if (activeTab === 'available') {
        // Available orders: Use dedicated API for available orders
        console.log('CourierHomeScreen: Fetching available orders...');
        const orders = await getAvailableOrdersForCourier(token);
        console.log(`CourierHomeScreen: Received ${orders.length} available orders`);
        setAvailableOrders(orders);
      } else if (activeTab === 'active') {
        // Active orders: Use dedicated API for active orders
        console.log('CourierHomeScreen: Fetching active orders...');
        const orders = await getCourierActiveOrders(token);
        console.log(`CourierHomeScreen: Received ${orders.length} active orders`);
        setActiveOrders(orders);
      } else if (activeTab === 'wallet') {
        console.log('CourierHomeScreen: Fetching wallet data...');
        const walletData = await getWallet(token);
        console.log('CourierHomeScreen: Received wallet data:', walletData);
        setWallet(walletData);
      } else if (activeTab === 'previous') {
        // Previous orders: Use dedicated API for all courier orders
        console.log('CourierHomeScreen: Fetching previous orders...');
        const orders = await getCourierAllOrders(token);
        console.log(`CourierHomeScreen: Received ${orders.length} total orders`);
        // Filter for cancelled and done orders
        const previousOrdersFiltered = orders.filter(order =>
          order.status === 'cancelled' || order.status === 'done'
        );
        console.log(`CourierHomeScreen: Filtered to ${previousOrdersFiltered.length} previous orders`);
        setPreviousOrders(previousOrdersFiltered);
      }
    } catch (error) {
      console.error('CourierHomeScreen: Error loading data:', error);
      Alert.alert('خطأ', 'فشل في تحميل البيانات');
    }
  };

  const handleAcceptOrder = async (orderId: string) => {
    try {
      setLoading(true);
      if (!token) return;

      await acceptOrder(token, orderId);
      Alert.alert('نجح', 'تم قبول الطلب بنجاح');

      // Switch to active orders tab to show the newly accepted order
      setActiveTab('active');

      // Refresh data for the active tab
      loadData();
    } catch (error) {
      console.error('Error accepting order:', error);
      Alert.alert('خطأ', 'فشل في قبول الطلب');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestDeposit = async () => {
    const amount = parseFloat(depositAmount);
    if (isNaN(amount) || amount < 10) {
      Alert.alert('خطأ', 'يجب أن يكون المبلغ 10 ريال على الأقل');
      return;
    }

    try {
      setLoading(true);
      if (!token) return;

      await requestWalletDeposit(token, amount);
      Alert.alert('نجح', 'تم إرسال طلب الشحن بنجاح');
      setDepositAmount('');
      // Refresh wallet data
      loadData();
    } catch (error) {
      console.error('Error requesting deposit:', error);
      Alert.alert('خطأ', 'فشل في طلب الشحن');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async (profileData: any) => {
    try {
      setLoading(true);
      if (!token) return;

      await updateUserDetails(token, profileData);
      Alert.alert('نجح', 'تم تحديث الملف الشخصي بنجاح');
    } catch (error) {
      console.error('Error updating profile:', error);
      Alert.alert('خطأ', 'فشل في تحديث الملف الشخصي');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await loadData();
    } catch (error) {
      console.error('Error refreshing data:', error);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.backgroundColor }]}>
      {/* Header - Fixed */}
      <View style={[styles.header, {
        paddingTop: Math.max(insets.top + 16, Dimensions.get('window').height * 0.05),
        backgroundColor: theme.cardBackground,
        borderBottomColor: theme.borderColor
      }]}>
        <View style={styles.headerContent}>
          <View style={styles.headerLeft}>
            <View style={styles.truckIcon}>
              <Feather name="truck" size={24} color="white" />
            </View>
            <View>
              <Text style={[styles.headerSubtitle, { color: theme.secondaryTextColor }]}>مندوب هديتي</Text>
              <Text style={[styles.headerTitle, { color: theme.textColor }]}>{userData?.name || 'مندوب'}</Text>
            </View>
          </View>
        </View>

      </View>

      {/* Scrollable Content Area */}
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={['#E0AAFF']}
            tintColor="#E0AAFF"
          />
        }
      >
        {(activeTab === 'available' || activeTab === 'active') && (
          <View>
            {/* Stats Summary */}
            <View style={styles.statsContainer}>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>أرباح اليوم</Text>
                <Text style={styles.statValue}>
                  {courierStats ? (courierStats.todays_earnings / 100).toFixed(2) : '0.00'} <Text style={styles.currency}>ر.س</Text>
                </Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>طلبات نشطة</Text>
                <Text style={styles.statValue}>{courierStats?.active_orders_count || 0}</Text>
              </View>
            </View>

            {/* Tabs */}
            <View style={styles.tabsContainer}>
              <View style={styles.tabsBackground}>
                <Pressable
                  onPress={() => setActiveTab('available')}
                  style={[styles.tab, activeTab === 'available' && styles.activeTab]}
                >
                  <Text style={[styles.tabText, activeTab === 'available' && styles.activeTabText]}>طلبات متاحة</Text>
                </Pressable>
                <Pressable
                  onPress={() => setActiveTab('active')}
                  style={[styles.tab, activeTab === 'active' && styles.activeTab]}
                >
                  <Text style={[styles.tabText, activeTab === 'active' && styles.activeTabText]}>طلباتي النشطة</Text>
                </Pressable>
              </View>
            </View>

            <View style={styles.ordersContainer}>
              {activeTab === 'available' ? (
                availableOrders.length > 0 ? (
                  availableOrders.map(order => (
                    <View key={order.id} style={styles.orderCard}>
                      <View style={styles.orderHeader}>
                        <View style={styles.orderLeft}>
                          <View style={styles.packageIcon}>
                            <Feather name="package" size={24} color="#E0AAFF" />
                          </View>
                          <View>
                            <Text style={styles.orderTitle}>طلب {order.order_id}</Text>
                            <Text style={styles.orderSubtitle}>{order.description || 'وصف غير محدد'}</Text>
                          </View>
                        </View>
                        <Text style={styles.orderPrice}>
                          {order.invoice ? `${(order.invoice.full_amount / 100).toFixed(2)} ر.س` : 'غير محدد'}
                        </Text>
                      </View>
                      <View style={styles.orderFooter}>
                        <Pressable
                          onPress={() => handleAcceptOrder(order.order_id)}
                          disabled={loading}
                          style={[styles.acceptButton, loading && { opacity: 0.6 }]}
                        >
                          <Text style={styles.acceptButtonText}>
                            {loading ? 'جاري المعالجة...' : 'قبول الطلب'}
                          </Text>
                        </Pressable>
                      </View>
                    </View>
                  ))
                ) : (
                  <View style={styles.emptyState}>
                    <View style={styles.emptyIcon}>
                      <Feather name="package" size={32} color="#9CA3AF" />
                    </View>
                    <Text style={styles.emptyText}>لا توجد طلبات متاحة حالياً</Text>
                  </View>
                )
              ) : (
                activeOrders.length > 0 ? (
                  activeOrders.map(order => (
                    <View key={order.id} style={styles.activeOrderCard}>
                      <View style={styles.activeOrderHeader}>
                        <View style={styles.activeOrderLeft}>
                          <View style={styles.activePackageIcon}>
                            <Feather name="package" size={20} color="#E0AAFF" />
                          </View>
                          <View>
                            <Text style={styles.activeOrderTitle}>طلب {order.order_id}</Text>
                            <Text style={styles.activeOrderSubtitle}>
                              {order.status === 'received by courier' ? 'تم الاستلام' :
                               order.status === 'in progress to do' ? 'قيد التجهيز' :
                               order.status === 'in progress to deliver' ? 'قيد التوصيل' :
                               order.status === 'done' ? 'مكتمل' : order.status}
                            </Text>
                          </View>
                        </View>
                        <View style={styles.activeBadge}>
                          <Text style={styles.activeBadgeText}>نشط الآن</Text>
                        </View>
                      </View>

                      <View style={styles.progressSection}>
                        <Text style={styles.progressTitle}>حالة الطلب</Text>
                        <View style={styles.progressContainer}>
                          <View style={styles.progressBar}>
                            <View style={[styles.progressFill, {
                              width: order.status === 'received by courier' ? '25%' :
                                     order.status === 'in progress to do' ? '50%' :
                                     order.status === 'in progress to deliver' ? '75%' : '100%'
                            }]} />
                          </View>

                          <View style={styles.progressStep}>
                            <View style={[styles.stepIcon, order.status === 'received by courier' && styles.activeStepIcon]}>
                              <Feather name="check-circle" size={18} color={order.status === 'received by courier' ? 'white' : '#9CA3AF'} />
                            </View>
                            <Text style={[styles.stepText, order.status === 'received by courier' && styles.activeStepText]}>تم الاستلام</Text>
                          </View>

                          <View style={styles.progressStep}>
                            <View style={[styles.stepIcon, order.status === 'in progress to do' && styles.activeStepIcon]}>
                              <Feather name="gift" size={18} color={order.status === 'in progress to do' ? 'white' : '#9CA3AF'} />
                            </View>
                            <Text style={[styles.stepText, order.status === 'in progress to do' && styles.activeStepText]}>تجهيز الهدية</Text>
                          </View>

                          <View style={styles.progressStep}>
                            <View style={[styles.stepIcon, order.status === 'in progress to deliver' && styles.activeStepIcon]}>
                              <Feather name="truck" size={18} color={order.status === 'in progress to deliver' ? 'white' : '#9CA3AF'} />
                            </View>
                            <Text style={[styles.stepText, order.status === 'in progress to deliver' && styles.activeStepText]}>في الطريق</Text>
                          </View>

                          <View style={styles.progressStep}>
                            <View style={[styles.stepIcon, order.status === 'done' && styles.activeStepIcon]}>
                              <Feather name="check-circle" size={18} color={order.status === 'done' ? 'white' : '#9CA3AF'} />
                            </View>
                            <Text style={[styles.stepText, order.status === 'done' && styles.activeStepText]}>تم التسليم</Text>
                          </View>
                        </View>
                      </View>

                      <View style={styles.activeOrderFooter}>
                        <Pressable onPress={onAcceptOrder} style={styles.mapButton}>
                          <Feather name="map" size={16} color="#E0AAFF" />
                          <Text style={styles.mapButtonText}>فتح الخريطة</Text>
                        </Pressable>
                        <Pressable onPress={() => onNavigateToChat?.(order.order_id)} style={styles.chatButton}>
                          <Text style={styles.chatButtonText}>الدردشة مع العميل</Text>
                        </Pressable>
                      </View>
                    </View>
                  ))
                ) : (
                  <View style={styles.emptyState}>
                    <View style={styles.emptyIcon}>
                      <Feather name="package" size={32} color="#9CA3AF" />
                    </View>
                    <Text style={styles.emptyText}>لا توجد طلبات نشطة حالياً</Text>
                  </View>
                )
              )}
            </View>
            </View>
        )}

        {activeTab === 'notifications' && (
          <View style={styles.notificationsContainer}>
            <View style={styles.notificationsHeader}>
              <Text style={styles.notificationsTitle}>التنبيهات</Text>
              <View style={styles.newBadge}>
                <Text style={styles.newBadgeText}>3 جديد</Text>
              </View>
            </View>
            <View style={styles.notificationsList}>
              {NOTIFICATIONS.map(note => (
                <Pressable key={note.id} style={styles.notificationItem}>
                  <View style={[styles.notificationIcon, {
                    backgroundColor: note.type === 'new_order' ? 'rgba(59, 130, 246, 0.1)' :
                                   note.type === 'payment' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)'
                  }]}>
                    <Feather
                      name={note.type === 'new_order' ? 'package' : note.type === 'payment' ? 'dollar-sign' : 'star'}
                      size={20}
                      color={note.type === 'new_order' ? '#3B82F6' : note.type === 'payment' ? '#10B981' : '#F59E0B'}
                    />
                  </View>
                  <View style={styles.notificationContent}>
                    <View style={styles.notificationHeader}>
                      <Text style={styles.notificationTitle}>{note.title}</Text>
                      <Text style={styles.notificationTime}>{note.time}</Text>
                    </View>
                    <Text style={styles.notificationBody}>{note.body}</Text>
                  </View>
                </Pressable>
              ))}
            </View>
          </View>
        )}

        {activeTab === 'wallet' && (
          <View style={styles.walletContainer}>
            <Text style={styles.walletTitle}>المحفظة</Text>
            <View style={styles.walletCard}>
              <View style={styles.walletContent}>
                <Text style={styles.walletLabel}>الرصيد المتاح</Text>
                <Text style={styles.walletAmount}>
                  {wallet ? (wallet.balance / 100).toFixed(2) : '0.00'} <Text style={styles.walletCurrency}>ر.س</Text>
                </Text>
              </View>
            </View>

            <View style={styles.depositSection}>
              <Text style={styles.depositTitle}>طلب شحن المحفظة</Text>
              <Text style={styles.depositSubtitle}>الحد الأدنى 10 ريال (دقة إلى منزلتين عشريتين)</Text>

              <View style={styles.depositInputContainer}>
                <TextInput
                  style={styles.depositInput}
                  placeholder="أدخل المبلغ"
                  keyboardType="decimal-pad"
                  value={depositAmount}
                  onChangeText={setDepositAmount}
                />
                <Text style={styles.depositCurrency}>ر.س</Text>
              </View>

              <Pressable
                onPress={handleRequestDeposit}
                disabled={loading}
                style={[styles.depositButton, loading && { opacity: 0.6 }]}
              >
                <Text style={styles.depositButtonText}>
                  {loading ? 'جاري الإرسال...' : 'إرسال طلب الشحن'}
                </Text>
              </Pressable>
            </View>
          </View>
        )}

        {activeTab === 'previous' && (
          <View style={styles.previousOrdersContainer}>
            <Text style={styles.previousOrdersTitle}>طلباتك السابقة</Text>
            <View style={styles.previousOrdersList}>
              {previousOrders.length > 0 ? (
                previousOrders.map(order => (
                  <View key={order.id} style={styles.previousOrderCard}>
                    <View style={styles.previousOrderHeader}>
                      <View style={styles.previousOrderLeft}>
                        <View style={[styles.previousOrderIcon, {
                          backgroundColor: order.status === 'done' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'
                        }]}>
                          <Feather
                            name={order.status === 'done' ? 'check-circle' : 'x-circle'}
                            size={20}
                            color={order.status === 'done' ? '#10B981' : '#EF4444'}
                          />
                        </View>
                        <View>
                          <Text style={styles.previousOrderTitle}>طلب {order.order_id}</Text>
                          <Text style={styles.previousOrderSubtitle}>
                            {order.status === 'done' ? 'مكتمل' : order.status === 'cancelled' ? 'ملغي' : order.status}
                          </Text>
                        </View>
                      </View>
                      <Text style={styles.previousOrderPrice}>
                        {order.invoice ? `${(order.invoice.full_amount / 100).toFixed(2)} ر.س` : 'غير محدد'}
                      </Text>
                    </View>
                    <View style={styles.previousOrderFooter}>
                      <Text style={styles.previousOrderDate}>
                        {new Date(order.created_at).toLocaleDateString('ar-SA')}
                      </Text>
                    </View>
                  </View>
                ))
              ) : (
                <View style={styles.emptyState}>
                  <View style={styles.emptyIcon}>
                    <Feather name="clock" size={32} color="#9CA3AF" />
                  </View>
                  <Text style={styles.emptyText}>لا توجد طلبات سابقة</Text>
                </View>
              )}
            </View>
          </View>
        )}

        {activeTab === 'profile' && (
          <View style={styles.profileContainer}>
            <View style={styles.profileAvatarContainer}>
              <Image
                source={{ uri: 'https://picsum.photos/seed/courier1/200/200' }}
                style={styles.profileAvatar}
              />
            </View>
            <Text style={[styles.profileName, { color: theme.textColor }]}>{userData?.name || 'مندوب'}</Text>
            <View style={styles.ratingContainer}>
              <Feather name="star" size={18} color="#F59E0B" />
              <Text style={[styles.ratingText, { color: theme.textColor }]}>4.8 (120 تقييم)</Text>
            </View>

            <View style={styles.settingsSection}>
              <Text style={[styles.sectionTitle, { color: theme.secondaryTextColor }]}>إعدادات الحساب</Text>

              <View style={styles.menuItems}>
                <Pressable onPress={toggleDarkMode} style={[styles.menuItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
                  <View style={styles.menuItemContent}>
                    <View style={[styles.menuIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                      <Feather name={isDarkMode ? "sun" : "moon"} size={20} color="#9CA3AF" />
                    </View>
                    <Text style={[styles.menuLabel, { color: theme.textColor }]}>الوضع الداكن (Dark Mode)</Text>
                  </View>
                  <View style={[styles.toggle, isDarkMode && styles.toggleActive]}>
                    <View style={[styles.toggleKnob, isDarkMode && styles.toggleKnobActive]} />
                  </View>
                </Pressable>

                <Pressable onPress={() => setActiveTab('previous')} style={[styles.menuItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
                  <View style={styles.menuItemContent}>
                    <View style={[styles.menuIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                      <Feather name="clock" size={20} color="#9CA3AF" />
                    </View>
                    <Text style={[styles.menuLabel, { color: theme.textColor }]}>طلباتك السابقة</Text>
                  </View>
                  <Feather name="chevron-left" size={18} color={theme.secondaryTextColor} />
                </Pressable>

                <Pressable style={[styles.menuItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
                  <View style={styles.menuItemContent}>
                    <View style={[styles.menuIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                      <Feather name="help-circle" size={20} color="#9CA3AF" />
                    </View>
                    <Text style={[styles.menuLabel, { color: theme.textColor }]}>مركز المساعدة والدعم</Text>
                  </View>
                  <Feather name="chevron-left" size={18} color={theme.secondaryTextColor} />
                </Pressable>

                <Pressable onPress={onLogout} style={styles.logoutButton}>
                  <View style={styles.menuItemContent}>
                    <View style={styles.logoutIcon}>
                      <Feather name="log-out" size={20} color="#EF4444" />
                    </View>
                    <Text style={styles.logoutText}>تسجيل الخروج</Text>
                  </View>
                </Pressable>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
      {/* Bottom Nav */}
      <View style={styles.bottomNav}>
        <Pressable onPress={() => setActiveTab('available')} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="truck" size={18} color={activeTab === 'available' || activeTab === 'active' ? '#E0AAFF' : '#9CA3AF'} />
          </View>
          <Text style={[styles.navText, (activeTab === 'available' || activeTab === 'active') && styles.activeNavText]}>الرئيسية</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('wallet')} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="dollar-sign" size={18} color={activeTab === 'wallet' ? '#E0AAFF' : '#9CA3AF'} />
          </View>
          <Text style={[styles.navText, activeTab === 'wallet' && styles.activeNavText]}>المحفظة</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('notifications')} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="bell" size={18} color={activeTab === 'notifications' ? '#E0AAFF' : '#9CA3AF'} />
          </View>
          <Text style={[styles.navText, activeTab === 'notifications' && styles.activeNavText]}>التنبيهات</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('profile')} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="user" size={18} color={activeTab === 'profile' ? '#E0AAFF' : '#9CA3AF'} />
          </View>
          <Text style={[styles.navText, activeTab === 'profile' && styles.activeNavText]}>ملفي</Text>
        </Pressable>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFC',
  },
  header: {
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
    minHeight: 80, // Ensure minimum header height
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  truckIcon: {
    width: 48,
    height: 48,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  headerSubtitle: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  logoutButton: {
    padding: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 12,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 120, // Adjusted for new bottom nav layout
  },
  statsContainer: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    gap: 16,
    marginTop: Math.max(24, Dimensions.get('window').height * 0.03), // Dynamic top margin
  },
  statCard: {
    flex: 1,
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  statLabel: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '900',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '900',
    color: '#E0AAFF',
  },
  currency: {
    fontSize: 12,
  },
  tabsContainer: {
    paddingHorizontal: 24,
    marginTop: Math.max(24, Dimensions.get('window').height * 0.04), // Dynamic top margin
  },
  tabsBackground: {
    flexDirection: 'row',
    backgroundColor: '#F3F4F6',
    borderRadius: 28,
    padding: 4,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 24,
    alignItems: 'center',
  },
  activeTab: {
    backgroundColor: 'white',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  tabText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#9CA3AF',
  },
  activeTabText: {
    color: '#E0AAFF',
  },
  bottomNav: {
    backgroundColor: 'white',
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  navItem: {
    alignItems: 'center',
    gap: 4,
  },
  navIcon: {
    padding: Dimensions.get('window').width * 0.015,
    borderRadius: Dimensions.get('window').width * 0.03,
  },
  navText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#9CA3AF',
  },
  activeNavText: {
    color: '#E0AAFF',
  },
  ordersContainer: {
    paddingHorizontal: 24,
    marginTop: Math.max(16, Dimensions.get('window').height * 0.02), // Dynamic top margin for orders
    gap: 16,
  },
  orderCard: {
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 40,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  orderLeft: {
    flexDirection: 'row',
    gap: 16,
  },
  packageIcon: {
    width: 48,
    height: 48,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  orderTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  orderSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '500',
    marginTop: 4,
  },
  orderPrice: {
    fontSize: 14,
    fontWeight: '900',
    color: '#E0AAFF',
  },
  orderFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#F9FAFB',
  },
  acceptButton: {
    paddingHorizontal: 32,
    paddingVertical: 8,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
  },
  acceptButtonText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: 'white',
  },
  activeOrderCard: {
    backgroundColor: 'white',
    padding: 24,
    borderRadius: 40,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: 'rgba(224, 170, 255, 0.1)',
  },
  activeOrderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  activeOrderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  activePackageIcon: {
    width: 40,
    height: 40,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  activeOrderTitle: {
    fontSize: 14,
    fontWeight: '900',
    color: '#1F2937',
  },
  activeOrderSubtitle: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  activeBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.2)',
  },
  activeBadgeText: {
    fontSize: 9,
    color: '#10B981',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  progressSection: {
    gap: 24,
  },
  progressTitle: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '900',
    textTransform: 'uppercase',
    textAlign: 'right',
  },
  progressContainer: {
    paddingHorizontal: 16,
    position: 'relative',
  },
  progressBar: {
    position: 'absolute',
    top: 20,
    left: 32,
    right: 32,
    height: 2,
    backgroundColor: '#F3F4F6',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#E0AAFF',
  },
  progressStep: {
    alignItems: 'center',
    gap: 8,
    position: 'relative',
    zIndex: 10,
  },
  stepIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  activeStepIcon: {
    backgroundColor: '#E0AAFF',
  },
  stepText: {
    fontSize: 9,
    fontWeight: '900',
    color: '#9CA3AF',
    textAlign: 'center',
  },
  activeStepText: {
    color: '#E0AAFF',
  },
  activeOrderFooter: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 24,
    paddingTop: 24,
    borderTopWidth: 1,
    borderTopColor: '#F9FAFB',
  },
  mapButton: {
    flex: 1,
    paddingVertical: 12,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  mapButtonText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#E0AAFF',
  },
  chatButton: {
    flex: 1,
    paddingVertical: 12,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chatButtonText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: 'white',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 48,
    opacity: 0.4,
  },
  emptyIcon: {
    width: 80,
    height: 80,
    backgroundColor: '#F3F4F6',
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#9CA3AF',
  },
  notificationsContainer: {
    padding: 24,
  },
  notificationsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 32,
  },
  notificationsTitle: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
  },
  newBadge: {
    backgroundColor: 'rgba(224, 170, 255, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
  },
  newBadgeText: {
    fontSize: 10,
    fontWeight: '900',
    color: '#E0AAFF',
    textTransform: 'uppercase',
  },
  notificationsList: {
    gap: 16,
  },
  notificationItem: {
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
    flexDirection: 'row',
    gap: 16,
  },
  notificationIcon: {
    width: 48,
    height: 48,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationContent: {
    flex: 1,
  },
  notificationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  notificationTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  notificationTime: {
    fontSize: 9,
    color: '#9CA3AF',
    fontWeight: 'bold',
  },
  notificationBody: {
    fontSize: 12,
    color: '#9CA3AF',
    lineHeight: 16,
  },
  walletContainer: {
    padding: 24,
  },
  walletTitle: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
    textAlign: 'right',
    marginBottom: 24,
  },
  walletCard: {
    backgroundColor: '#E0AAFF',
    borderRadius: 40,
    padding: 32,
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  walletContent: {
    alignItems: 'flex-end',
  },
  walletLabel: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'rgba(255, 255, 255, 0.8)',
    marginBottom: 4,
  },
  walletAmount: {
    fontSize: 36,
    fontWeight: '900',
    color: 'white',
  },
  walletCurrency: {
    fontSize: 18,
  },
  profileContainer: {
    padding: 24,
    alignItems: 'center',
  },
  profileAvatarContainer: {
    width: 128,
    height: 128,
    borderRadius: 64,
    backgroundColor: '#E0AAFF',
    padding: 4,
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
    marginBottom: 24,
    transform: [{ rotate: '3deg' }],
  },
  profileAvatar: {
    width: '100%',
    height: '100%',
    borderRadius: 60,
    borderWidth: 4,
    borderColor: 'white',
  },
  profileName: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
    marginBottom: 16,
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.2)',
  },
  ratingText: {
    fontSize: 14,
    fontWeight: '900',
    color: '#F59E0B',
  },
  settingsSection: {
    width: '100%',
    marginTop: 32,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 16,
    textAlign: 'right',
  },
  menuItems: {
    gap: 12,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  menuItemContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  menuIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: '#F9FAFB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuLabel: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#374151',
  },
  toggle: {
    width: 48,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#E5E7EB',
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  toggleActive: {
    backgroundColor: '#E0AAFF',
  },
  toggleKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: 'white',
    transform: [{ translateX: 0 }],
  },
  toggleKnobActive: {
    transform: [{ translateX: 20 }],
  },
  depositSection: {
    marginTop: 32,
  },
  depositTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'right',
    marginBottom: 8,
  },
  depositSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'right',
    marginBottom: 24,
  },
  depositInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'white',
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  depositInput: {
    flex: 1,
    fontSize: 16,
    textAlign: 'right',
    color: '#1F2937',
  },
  depositCurrency: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#E0AAFF',
    marginLeft: 8,
  },
  depositButton: {
    backgroundColor: '#E0AAFF',
    paddingVertical: 16,
    borderRadius: 16,
    alignItems: 'center',
  },
  depositButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
  },
  previousOrdersContainer: {
    padding: 24,
  },
  previousOrdersTitle: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
    textAlign: 'right',
    marginBottom: 24,
  },
  previousOrdersList: {
    gap: 16,
  },
  previousOrderCard: {
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  previousOrderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  previousOrderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  previousOrderIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  previousOrderTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  previousOrderSubtitle: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  previousOrderPrice: {
    fontSize: 14,
    fontWeight: '900',
    color: '#E0AAFF',
  },
  previousOrderFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F9FAFB',
  },
  previousOrderDate: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: 'bold',
  },
  logoutButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  logoutIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoutText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#EF4444',
  },
});
