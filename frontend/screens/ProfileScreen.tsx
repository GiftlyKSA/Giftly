
import React, { useState, useEffect } from 'react';
import { View, Text, Pressable, ScrollView, Modal, TextInput, StyleSheet, Dimensions, Alert, Platform } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useAuth } from '../App';

interface Props {
  onBack: () => void;
  onLogout: () => void;
  onNavigateHome: () => void;
  onNavigateOrders: () => void;
  onNavigateCourier: () => void;
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

export const ProfileScreen: React.FC<Props> = ({ onBack, onLogout, onNavigateHome, onNavigateOrders, onNavigateCourier, isDarkMode, toggleDarkMode, theme }) => {
  const insets = useSafeAreaInsets();
  const { userData, token, fetchUserData } = useAuth();
  const [showEditModal, setShowEditModal] = useState(false);
  const [name, setName] = useState(userData?.name || '');
  const [email, setEmail] = useState(userData?.email || '');
  const [birthDate, setBirthDate] = useState(userData?.date_of_birth ? new Date(userData.date_of_birth) : new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);

  const [tempDate, setTempDate] = useState<Date>(birthDate || new Date());
  const [showPicker, setShowPicker] = useState(false);
  const [showSuccessOverlay, setShowSuccessOverlay] = useState(false);
  const [showErrorOverlay, setShowErrorOverlay] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [walletBalance, setWalletBalance] = useState<number>(0);
  const [chargeAmount, setChargeAmount] = useState<string>('');
  const [errors, setErrors] = useState<{
    name?: string;
    email?: string;
    date_of_birth?: string;
    chargeAmount?: string;
  }>({});

  useEffect(() => {
    if (userData) {
      setName(userData.name);
      setEmail(userData.email);
      if (userData.date_of_birth) {
        setBirthDate(new Date(userData.date_of_birth));
      }
    }
  }, [userData]);

  useEffect(() => {
    const fetchWalletBalance = async () => {
      if (!token) return;
      try {
        const { getWallet } = await import('../api');
        const walletData = await getWallet(token);
        setWalletBalance(walletData.balance);
      } catch (error) {
        console.error('Failed to fetch wallet balance:', error);
        // Keep the default balance of 0 if fetch fails
      }
    };

    fetchWalletBalance();
  }, [token]);

  /* ---------------- Validation ---------------- */
  const validateForm = () => {
    const newErrors: typeof errors = {};

    if (!name.trim()) {
      newErrors.name = 'الاسم مطلوب';
    } else if (name.trim().length < 5) {
      newErrors.name = 'الاسم يجب أن يكون 5 أحرف على الأقل';
    } else if (!/^[a-zA-Z\u0600-\u06FF][a-zA-Z\u0600-\u06FF0-9\s]*$/.test(name.trim())) {
      newErrors.name = 'الاسم يجب أن يبدأ بحرف ويمكن أن يحتوي على أرقام ومسافات';
    }

    if (!email.trim()) {
      newErrors.email = 'البريد الإلكتروني مطلوب';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'صيغة البريد الإلكتروني غير صحيحة';
    }

    if (!birthDate) {
      newErrors.date_of_birth = 'تاريخ الميلاد مطلوب';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateChargeAmount = () => {
    const newErrors: typeof errors = {};

    const amount = parseInt(chargeAmount);
    if (!chargeAmount.trim()) {
      newErrors.chargeAmount = 'مبلغ الشحن مطلوب';
    } else if (isNaN(amount) || !Number.isInteger(amount)) {
      newErrors.chargeAmount = 'يجب أن يكون المبلغ رقماً صحيحاً';
    } else if (amount < 10) {
      newErrors.chargeAmount = 'الحد الأدنى للشحن 10 ريالات';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const menuItems = [
    { icon: 'user', label: 'تعديل البيانات الشخصية', action: () => setShowEditModal(true) },
    { icon: 'credit-card', label: 'المحفظة وطرق الدفع' },
    { icon: 'shield', label: 'الخصوصية والأمان' },
  ];

  return (
    <View style={[styles.container, { backgroundColor: theme.backgroundColor }]}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
      <View style={[styles.header, { paddingTop: Math.max(insets.top + 16, Dimensions.get('window').height * 0.05), backgroundColor: theme.cardBackground, borderBottomColor: theme.borderColor }]}>
        <Text style={[styles.title, { color: theme.textColor }]}>ملفي</Text>
      </View>

      <View style={styles.profileSection}>
        <Text style={styles.userName}>{name}</Text>
        <Text style={styles.userEmail}>{email}</Text>
      </View>

      <View style={styles.walletSection}>
        <View style={styles.walletCard}>
          <View style={styles.walletContent}>
            <View style={styles.walletInfo}>
              <Text style={styles.walletLabel}>رصيد المحفظة</Text>
              <Text style={styles.walletAmount}>{walletBalance.toFixed(2)} <Text style={styles.currency}>ر.س</Text></Text>
            </View>
            <View style={styles.walletIcon}>
              <Feather name="credit-card" size={28} color="rgba(255, 255, 255, 0.8)" />
            </View>
          </View>
          <Pressable onPress={() => setShowPaymentModal(true)} style={styles.chargeButton}>
            <Text style={styles.chargeButtonText}>شحن الرصيد</Text>
          </Pressable>
        </View>
      </View>

      {/* Show different content based on user role */}
      {userData?.role === 'Courier' ? (
        // Courier Profile - Read-only
        <View style={styles.settingsSection}>
          <Text style={styles.sectionTitle}>معلومات المندوب</Text>

          <View style={styles.infoSection}>
            <View style={[styles.infoItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
              <View style={styles.infoItemContent}>
                <View style={[styles.infoIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                  <Feather name="user" size={20} color="#9CA3AF" />
                </View>
                <View style={styles.infoTextContainer}>
                  <Text style={[styles.infoLabel, { color: theme.secondaryTextColor }]}>الاسم</Text>
                  <Text style={[styles.infoValue, { color: theme.textColor }]}>{userData.name}</Text>
                </View>
              </View>
            </View>

            <View style={[styles.infoItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
              <View style={styles.infoItemContent}>
                <View style={[styles.infoIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                  <Feather name="credit-card" size={20} color="#9CA3AF" />
                </View>
                <View style={styles.infoTextContainer}>
                  <Text style={[styles.infoLabel, { color: theme.secondaryTextColor }]}>رقم الهوية الوطنية</Text>
                  <Text style={[styles.infoValue, { color: theme.textColor }]}>{userData.national_id || 'غير محدد'}</Text>
                </View>
              </View>
            </View>

            <View style={[styles.infoItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
              <View style={styles.infoItemContent}>
                <View style={[styles.infoIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                  <Feather name="map-pin" size={20} color="#9CA3AF" />
                </View>
                <View style={styles.infoTextContainer}>
                  <Text style={[styles.infoLabel, { color: theme.secondaryTextColor }]}>رقم جواز السفر</Text>
                  <Text style={[styles.infoValue, { color: theme.textColor }]}>{userData.passport_id || 'غير محدد'}</Text>
                </View>
              </View>
            </View>
          </View>

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
      ) : (
        // Customer Profile - Editable
        <View style={styles.settingsSection}>
          <Text style={styles.sectionTitle}>إعدادات الحساب</Text>

          <View style={styles.menuItems}>
            {menuItems.map((item, idx) => (
              <Pressable key={idx} onPress={item.action} style={[styles.menuItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
                <View style={styles.menuItemContent}>
                  <View style={[styles.menuIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                    <Feather name={item.icon as any} size={20} color="#9CA3AF" />
                  </View>
                  <Text style={[styles.menuLabel, { color: theme.textColor }]}>{item.label}</Text>
                </View>
                <Feather name="chevron-left" size={18} color={theme.secondaryTextColor} />
              </Pressable>
            ))}

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

            <Pressable style={[styles.menuItem, { backgroundColor: theme.cardBackground, borderColor: theme.borderColor }]}>
              <View style={styles.menuItemContent}>
                <View style={[styles.menuIcon, { backgroundColor: isDarkMode ? '#374151' : '#F9FAFB' }]}>
                  <Feather name="help-circle" size={20} color="#9CA3AF" />
                </View>
                <Text style={[styles.menuLabel, { color: theme.textColor }]}>مركز المساعدة والدعم</Text>
              </View>
              <Feather name="chevron-left" size={18} color={theme.secondaryTextColor} />
            </Pressable>
          </View>

          <Pressable onPress={onLogout} style={styles.logoutButton}>
            <View style={styles.menuItemContent}>
              <View style={styles.logoutIcon}>
                <Feather name="log-out" size={20} color="#EF4444" />
              </View>
              <Text style={styles.logoutText}>تسجيل الخروج</Text>
            </View>
          </Pressable>
        </View>
      )}

      <Modal
        visible={showEditModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowEditModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>تعديل البيانات الشخصية</Text>
              <Pressable onPress={() => setShowEditModal(false)} style={styles.closeButton}>
                <Feather name="x" size={20} color="#9CA3AF" />
              </Pressable>
            </View>

            <View style={styles.modalBody}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>الاسم بالكامل</Text>
                <TextInput
                  style={[styles.input, errors.name && styles.inputError]}
                  value={name}
                  onChangeText={(text) => {
                    setName(text);
                    setErrors((e) => ({ ...e, name: undefined }));
                  }}
                  placeholderTextColor="#9CA3AF"
                />
                {errors.name && <Text style={styles.errorText}>{errors.name}</Text>}
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>البريد الإلكتروني</Text>
                <TextInput
                  style={[styles.input, errors.email && styles.inputError]}
                  value={email}
                  onChangeText={(text) => {
                    setEmail(text);
                    setErrors((e) => ({ ...e, email: undefined }));
                  }}
                  placeholderTextColor="#9CA3AF"
                  textAlign="left"
                />
                {errors.email && <Text style={styles.errorText}>{errors.email}</Text>}
              </View>

              {/* Birthdate */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>تاريخ الميلاد</Text>
                <Pressable
                  style={[styles.input, styles.dateInput, errors.date_of_birth && styles.inputError]}
                  onPress={() => setShowPicker(true)}
                >
                  <Text style={[styles.dateText, { color: birthDate ? '#1F2937' : '#9CA3AF', textAlign: 'center' }]}>
                    {birthDate
                      ? birthDate.toLocaleDateString('en-US')
                      : 'اختر تاريخ الميلاد'}
                  </Text>
                  <Feather name="calendar" size={18} color="#D1D5DB" style={styles.dateIcon} />
                </Pressable>
                {errors.date_of_birth && (
                  <Text style={styles.errorText}>{errors.date_of_birth}</Text>
                )}
              </View>
<Modal
  visible={showPicker}
  transparent
  animationType="fade"
  onRequestClose={() => setShowPicker(false)}
>
  <View
    style={{
      flex: 1,
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}
  >
    <View
      style={{
        backgroundColor: '#fff',
        marginHorizontal: 20,
        borderRadius: 12,
        paddingTop: 8,
      }}
    >
      <DateTimePicker
        value={tempDate}
        mode="date"
        display={Platform.OS === 'ios' ? 'spinner' : 'default'}
        maximumDate={new Date()}
        accentColor="#000000"
        textColor="#000000"
        onChange={(_, date) => {
          if (date) setTempDate(date); // only update temp date
        }}
      />

      {/* Buttons */}
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          paddingHorizontal: 16,
          paddingVertical: 12,
          borderTopWidth: 1,
          borderColor: '#E5E7EB',
        }}
      >
        <Pressable onPress={() => setShowPicker(false)}>
          <Text style={{ color: '#6B7280', fontSize: 16 }}>
            إلغاء
          </Text>
        </Pressable>

        <Pressable
          onPress={() => {
            setBirthDate(tempDate); // just set the date
            setShowPicker(false);
          }}
        >
          <Text style={{ color: '#000000', fontSize: 16, fontWeight: '600' }}>
            تأكيد
          </Text>
        </Pressable>
      </View>
    </View>
  </View>
</Modal>



              <Pressable onPress={async () => {
                // Validate form first
                if (!validateForm()) return;

                try {
                  const { updateUserDetails } = await import('../api');
                  const updatedUser = await updateUserDetails(token!, {
                    name: name.trim(),
                    email: email.trim(),
                    date_of_birth: birthDate.toISOString().split('T')[0],
                  });

                  // Refresh user data from server
                  await fetchUserData();

                  setShowEditModal(false);
                  setShowSuccessOverlay(true);
                  setTimeout(() => {
                    setShowSuccessOverlay(false);
                  }, 3000);
                } catch (error: any) {
                  // Handle field-specific errors
                  if (typeof error === 'object' && error !== null) {
                    setErrors(error);
                  } else {
                    setErrorMessage(error.message || 'فشل في حفظ التعديلات');
                    setShowEditModal(false);
                    setShowErrorOverlay(true);
                    setTimeout(() => {
                      setShowErrorOverlay(false);
                      setErrorMessage('');
                    }, 3000);
                  }
                }
              }} style={styles.saveButton}>
                <Feather name="save" size={20} color="white" />
                <Text style={styles.saveButtonText}>حفظ التعديلات</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* Success Overlay */}
      {showSuccessOverlay && (
        <View style={styles.successOverlay}>
          <View style={styles.successMessage}>
            <Feather name="check-circle" size={48} color="#10B981" />
            <Text style={styles.successTitle}>تم حفظ التعديلات بنجاح</Text>
          </View>
        </View>
      )}

      {/* Error Overlay */}
      {showErrorOverlay && (
        <View style={styles.errorOverlay}>
          <View style={styles.errorMessage}>
            <Feather name="x-circle" size={48} color="#EF4444" />
            <Text style={styles.errorTitle}>فشل في حفظ التعديلات</Text>
            <Text style={styles.errorSubtitle}>{errorMessage}</Text>
          </View>
        </View>
      )}

      {/* Payment Method Modal */}
      <Modal
        visible={showPaymentModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => {
          setShowPaymentModal(false);
          setChargeAmount('');
          setErrors({});
        }}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>شحن الرصيد</Text>
              <Pressable onPress={() => {
                setShowPaymentModal(false);
                setChargeAmount('');
                setErrors({});
              }} style={styles.closeButton}>
                <Feather name="x" size={20} color="#9CA3AF" />
              </Pressable>
            </View>

            <View style={styles.modalBody}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>مبلغ الشحن (ريال)</Text>
                <TextInput
                  style={[styles.input, errors.chargeAmount && styles.inputError]}
                  value={chargeAmount}
                  onChangeText={(text) => {
                    setChargeAmount(text);
                    setErrors((e) => ({ ...e, chargeAmount: undefined }));
                  }}
                  placeholder="أدخل المبلغ"
                  keyboardType="numeric"
                  textAlign="right"
                />
                {errors.chargeAmount && <Text style={styles.errorText}>{errors.chargeAmount}</Text>}
              </View>

              <Pressable
                onPress={async () => {
                  if (!validateChargeAmount()) return;

                  try {
                    const { chargeWallet } = await import('../api');
                    const result = await chargeWallet(token!, parseInt(chargeAmount));
                    setWalletBalance(result.new_balance);
                    Alert.alert('نجح', result.message);
                    setShowPaymentModal(false);
                    setChargeAmount('');
                    setErrors({});
                  } catch (error: any) {
                    Alert.alert('خطأ', error.message || 'فشل في شحن الرصيد');
                  }
                }}
                style={styles.applePayButton}
              >
                <Text style={styles.applePayButtonText}> Pay</Text>
              </Pressable>

              <Pressable
                onPress={async () => {
                  if (!validateChargeAmount()) return;

                  try {
                    const { chargeWallet } = await import('../api');
                    const result = await chargeWallet(token!, parseInt(chargeAmount));
                    setWalletBalance(result.new_balance);
                    Alert.alert('نجح', result.message);
                    setShowPaymentModal(false);
                    setChargeAmount('');
                    setErrors({});
                  } catch (error: any) {
                    Alert.alert('خطأ', error.message || 'فشل في شحن الرصيد');
                  }
                }}
                style={styles.paymentMethodButton}
              >
                <View style={styles.paymentMethodContent}>
                  <View style={styles.paymentIcon}>
                    <Feather name="credit-card" size={20} color="#9CA3AF" />
                  </View>
                  <Text style={styles.paymentMethodText}>Credit/Mada</Text>
                </View>
                <Feather name="chevron-left" size={18} color="#9CA3AF" />
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
      </ScrollView>

      {/* Bottom Navigation */}
      <View style={styles.bottomNav}>
        <Pressable onPress={onNavigateHome} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="star" size={18} color="#9CA3AF" />
          </View>
          <Text style={styles.navText}>الرئيسية</Text>
        </Pressable>

        <Pressable onPress={onNavigateOrders} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="package" size={18} color="#9CA3AF" />
          </View>
          <Text style={styles.navText}>طلباتك</Text>
        </Pressable>

        <Pressable onPress={onNavigateCourier} style={styles.navItem}>
          <View style={styles.navIcon}>
            <Feather name="truck" size={18} color="#9CA3AF" />
          </View>
          <Text style={styles.navText}>المندوب</Text>
        </Pressable>

        <Pressable style={[styles.navItem, styles.activeNavItem]}>
          <View style={[styles.navIcon, styles.activeNavIcon]}>
            <Feather name="user" size={18} color="#E0AAFF" />
          </View>
          <Text style={[styles.navText, styles.activeNavText]}>ملفي</Text>
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
  content: {
    paddingBottom: 120,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingBottom: 16,
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
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  spacer: {
    width: 40,
  },
  profileSection: {
    alignItems: 'center',
    paddingHorizontal: 24,
    marginBottom: 32,
  },

  userName: {
    fontSize: 24,
    fontWeight: '900',
    color: '#1F2937',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 14,
    color: '#9CA3AF',
    fontWeight: 'bold',
  },
  walletSection: {
    paddingHorizontal: 24,
    marginBottom: 32,
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  walletInfo: {
    flex: 1,
  },
  walletLabel: {
    fontSize: 10,
    fontWeight: '900',
    color: 'rgba(255, 255, 255, 0.8)',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 4,
  },
  walletAmount: {
    fontSize: 30,
    fontWeight: '900',
    color: 'white',
  },
  currency: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  walletIcon: {
    width: 56,
    height: 56,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chargeButton: {
    backgroundColor: 'white',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  chargeButtonText: {
    fontSize: 12,
    fontWeight: '900',
    color: '#E0AAFF',
  },
  settingsSection: {
    paddingHorizontal: 24,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 16,
  },
  menuItems: {
    gap: 12,
    marginBottom: 24,
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
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 32,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1F2937',
  },
  closeButton: {
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
  },
  modalBody: {
    gap: 24,
  },
  inputGroup: {
    gap: 8,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 1,
    textAlign: 'right',
  },
  input: {
    width: '100%',
    height: 56,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: 24,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'right',
  },
  dateInput: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
  },
  dateText: {
    fontSize: 14,
    fontWeight: 'bold',
    flex: 1,
  },
  dateIcon: {
    marginLeft: 8,
  },
  inputError: {
    borderWidth: 1,
    borderColor: '#EF4444',
    backgroundColor: '#FEF2F2',
  },
  errorText: {
    fontSize: 12,
    color: '#EF4444',
    fontWeight: '600',
    textAlign: 'right',
  },
  successMessage: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#D1FAE5',
    borderWidth: 1,
    borderColor: '#10B981',
    borderRadius: 12,
    padding: 16,
  },
  successText: {
    fontSize: 14,
    color: '#065F46',
    fontWeight: '600',
    textAlign: 'center',
  },
  saveButton: {
    width: '100%',
    height: 64,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  saveButtonText: {
    fontSize: 18,
    fontWeight: '900',
    color: 'white',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 120,
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
    gap: Dimensions.get('window').height * 0.005,
  },
  activeNavItem: {
    transform: [{ scale: 1.05 }],
  },
  navIcon: {
    padding: Dimensions.get('window').width * 0.015,
    borderRadius: Dimensions.get('window').width * 0.03,
  },
  activeNavIcon: {
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
  },
  navText: {
    fontSize: Dimensions.get('window').width * 0.022,
    fontWeight: 'bold',
    color: '#9CA3AF',
  },
  activeNavText: {
    color: '#E0AAFF',
  },

  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  datePickerContainer: {
    backgroundColor: 'white',
    borderRadius: 20,
    padding: 20,
    width: '90%',
    maxWidth: 400,
  },
  datePickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  datePickerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  closeButton: {
    padding: 8,
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
  },
  paymentMethodContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  paymentIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: '#F9FAFB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  applePayText: {
    fontSize: 24,
    color: '#000000',
  },
  paymentMethodText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#374151',
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
    marginBottom: 12,
  },
  applePayButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  infoSection: {
    gap: 12,
    marginBottom: 24,
  },
  infoItem: {
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
  infoItemContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  infoIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: '#F9FAFB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoTextContainer: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 12,
    fontWeight: '900',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  infoValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#374151',
  },
});
