import React, { useState } from 'react';
import {
  View,
  Text,
  Pressable,
  ScrollView,
  TextInput,
  StyleSheet,
  Platform,
  Modal,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import DateTimePicker from '@react-native-community/datetimepicker';
import { completeProfile } from '../api';

interface Props {
  phone: string;
  otp: string;
  onNext: (token: string) => void;
}

export const CompleteProfileScreen: React.FC<Props> = ({ phone, otp, onNext }) => {
  const insets = useSafeAreaInsets();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [birthDate, setBirthDate] = useState<Date | null>(null);
  const [role, setRole] = useState<'Customer' | 'Courier'>('Customer');


  const [showPicker, setShowPicker] = useState(false);
  const [loading, setLoading] = useState(false);
const [tempDate, setTempDate] = useState<Date>(birthDate || new Date());
  const [errors, setErrors] = useState<{
    name?: string;
    email?: string;
    birthDate?: string;
    api?: string;
  }>({});

  /* ---------------- Validation ---------------- */
  const validateForm = () => {
    const newErrors: typeof errors = {};

    if (!name.trim()) {
      newErrors.name = 'الاسم مطلوب';
    } else if (name.trim().length < 5) {
      newErrors.name = 'الاسم يجب أن يكون 5 أحرف على الأقل';
    }

    if (!email.trim()) {
      newErrors.email = 'البريد الإلكتروني مطلوب';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'صيغة البريد الإلكتروني غير صحيحة';
    }

    if (!birthDate) {
      newErrors.birthDate = 'تاريخ الميلاد مطلوب';
    }
    if (birthDate && birthDate > new Date()) {
      newErrors.birthDate = 'تاريخ الميلاد غير صالح';
    }
    if (birthDate && new Date().getFullYear() - birthDate.getFullYear() < 16) {
      newErrors.birthDate = 'يجب أن يكون عمرك 16 سنة على الأقل';
    }



    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /* ---------------- Submit ---------------- */
  const handleSubmit = async () => {
    if (!validateForm()) return;

    try {
      setLoading(true);
      setErrors({});

      const response = await completeProfile({
        phone_number: phone,
        name: name.trim(),
        email: email.trim(),
        date_of_birth: birthDate!.toISOString().split('T')[0],
        role: role,
      });

      onNext(response.access_token);
    } catch (error: any) {
      if (error.message === 'Email is already registered') {
        setErrors({ email: 'البريد الإلكتروني مستخدم بالفعل' });
      } else {
        setErrors({ api: 'حدث خطأ أثناء حفظ البيانات' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 32 }]}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconContainer}>
          <Feather name="star" size={32} color="#E0AAFF" />
        </View>
        <Text style={styles.title}>أكمل بياناتك</Text>
        <Text style={styles.subtitle}>خطوة بسيطة لبدء رحلة الهدايا</Text>
      </View>

      {/* Name */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>الاسم بالكامل</Text>
        <View style={styles.inputContainer}>
          <TextInput
            style={[styles.input, errors.name && styles.inputError]}
            value={name}
            onChangeText={(text) => {
              setName(text);
              setErrors((e) => ({ ...e, name: undefined }));
            }}
            placeholder="مثال: محمد علي"
            placeholderTextColor="#9CA3AF"
          />
          <Feather name="user" size={18} color="#D1D5DB" style={styles.icon} />
        </View>
        {errors.name && <Text style={styles.error}>{errors.name}</Text>}
      </View>

      {/* Email */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>البريد الإلكتروني</Text>
        <View style={styles.inputContainer}>
          <TextInput
            style={[styles.input, errors.email && styles.inputError]}
            value={email}
            onChangeText={(text) => {
              setEmail(text);
              setErrors((e) => ({ ...e, email: undefined }));
            }}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholder="example@mail.com"
            placeholderTextColor="#9CA3AF"
          />
          <Feather name="mail" size={18} color="#D1D5DB" style={styles.icon} />
        </View>
        {errors.email && <Text style={styles.error}>{errors.email}</Text>}
      </View>
{/* Birthdate */}
<Pressable style={styles.inputGroup} onPress={() => setShowPicker(true)}>
  <Text style={styles.label}>تاريخ الميلاد</Text>
  <View
    style={[
      styles.inputContainer,
      styles.input,
      errors.birthDate && styles.inputError,
    ]}
  >
    <Text style={{ color: birthDate ? '#1F2937' : '#9CA3AF' }}>
      {birthDate
        ? birthDate.toLocaleDateString('en-US')
        : 'اختر تاريخ الميلاد'}
    </Text>
    <Feather name="calendar" size={18} color="#D1D5DB" style={styles.icon} />
  </View>
  {errors.birthDate && (
    <Text style={styles.error}>{errors.birthDate}</Text>
  )}
</Pressable>
{/* Date Picker */}
{/* Date Picker */}
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

      {/* Role Selection */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>نوع الحساب</Text>
        <View style={styles.roleContainer}>
          <Pressable
            style={[styles.roleButton, role === 'Customer' && styles.roleButtonActive]}
            onPress={() => setRole('Customer')}
          >
            <Feather name="user" size={20} color={role === 'Customer' ? '#FFF' : '#6B7280'} />
            <Text style={[styles.roleText, role === 'Customer' && styles.roleTextActive]}>عميل</Text>
          </Pressable>
          <Pressable
            style={[styles.roleButton, role === 'Courier' && styles.roleButtonActive]}
            onPress={() => setRole('Courier')}
          >
            <Feather name="truck" size={20} color={role === 'Courier' ? '#FFF' : '#6B7280'} />
            <Text style={[styles.roleText, role === 'Courier' && styles.roleTextActive]}>مندوب</Text>
          </Pressable>
        </View>
      </View>



      {/* API global error */}
      {errors.api && <Text style={styles.apiError}>{errors.api}</Text>}

      {/* Submit button */}
      <Pressable
        style={[styles.button, loading && { opacity: 0.7 }]}
        onPress={handleSubmit}
        disabled={loading}
      >
        <Text style={styles.buttonText}>
          {loading ? 'جاري الحفظ...' : 'حفظ والمتابعة'}
        </Text>
      </Pressable>
    </ScrollView>
  );
};

/* ---------------- Styles ---------------- */
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFC' },
  content: { paddingHorizontal: 32, paddingBottom: 60 },

  header: { alignItems: 'center', marginBottom: 32 },
  iconContainer: {
    width: 64,
    height: 64,
    backgroundColor: 'rgba(224,170,255,0.2)',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },

  title: { fontSize: 24, fontWeight: '900', color: '#1F2937' },
  subtitle: { fontSize: 14, color: '#9CA3AF', marginTop: 4 },

  inputGroup: { marginBottom: 16 },
  label: { fontSize: 12, fontWeight: '900', color: '#6B7280', marginBottom: 6 },

  inputContainer: { position: 'relative' },
  input: {
    height: 52,
    backgroundColor: '#FFF',
    borderRadius: 16,
    paddingHorizontal: 48,
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  inputError: { borderColor: '#DC2626' },

  icon: { position: 'absolute', right: 16 },

  error: { marginTop: 4, color: '#DC2626', fontSize: 12, fontWeight: '600' },
  apiError: { marginTop: 12, textAlign: 'center', color: '#DC2626', fontWeight: '600' },

  button: {
    marginTop: 24,
    height: 60,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonText: { color: '#FFF', fontSize: 18, fontWeight: '900' },

  roleContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  roleButton: {
    flex: 1,
    height: 52,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  roleButtonActive: {
    backgroundColor: '#E0AAFF',
    borderColor: '#E0AAFF',
  },
  roleText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  roleTextActive: {
    color: '#FFF',
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
});
