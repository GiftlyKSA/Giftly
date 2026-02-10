
import React, { useState, useRef, useEffect } from 'react';
import { View, Text, Pressable, TextInput, StyleSheet, TouchableWithoutFeedback, Keyboard } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { sendOTP, verifyOTP } from '../api';

interface Props {
  onNext: (result: { phone: string, token?: string, needsProfile?: boolean, otp?: string }) => void;
}

export const LoginScreen: React.FC<Props> = ({ onNext }) => {
  const [phone, setPhone] = useState('');
  const [step, setStep] = useState<'PHONE' | 'OTP'>('PHONE');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [phoneError, setPhoneError] = useState('');
  const [error, setError] = useState('');
  const [timer, setTimer] = useState(90);
  const [canResend, setCanResend] = useState(false);
  const [sentOtp, setSentOtp] = useState('');

  const otpRefs = useRef<TextInput[]>([]);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (step === 'OTP' && timer > 0) {
      interval = setInterval(() => {
        setTimer((prev) => {
          if (prev <= 1) {
            setCanResend(true);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [step, timer]);

  const handleOtpChange = (value: string, index: number) => {
    // Only allow numeric digits
    const numericValue = value.replace(/[^0-9]/g, '');
    if (numericValue.length > 1) return; // Only allow single digit

    const newOtp = [...otp];
    newOtp[index] = numericValue;
    setOtp(newOtp);

    // Auto-focus next input if we have a value and it's not the last field
    if (numericValue && index < 5) {
      setTimeout(() => {
        otpRefs.current[index + 1]?.focus();
      }, 10);
    }

    // Clear error when user starts typing
    if (error) setError('');
  };

  const handleOtpKeyPress = (key: string, index: number) => {
    // Handle Enter key to move to next field
    if (key === 'Enter' && index < 5) {
      setTimeout(() => {
        otpRefs.current[index + 1]?.focus();
      }, 10);
    }
    // Handle backspace - if current field is empty and we're not at first field, move left
    else if (key === 'Backspace' && index > 0 && otp[index] === '') {
      setTimeout(() => {
        otpRefs.current[index - 1]?.focus();
      }, 10);
    }
  };

  const validatePhone = (ph: string): string => {
    if (!ph || ph.trim() === '') {
      return 'رقم الجوال مطلوب';
    }

    const clean = ph.replace(/[^0-9]/g, '');

    if (clean.startsWith('05')) {
      if (clean.length !== 10) {
        return 'الرقم غير صحيح';
      }
    } else if (clean.startsWith('5')) {
      if (clean.length !== 9) {
        return 'الرقم غير صحيح';
      }
    } else {
      return 'الرقم غير صحيح';
    }

    return '';
  };

  const handleResendOTP = async () => {
    try {
      const response = await sendOTP(phone);
      setSentOtp(response.otp);
      setTimer(90);
      setCanResend(false);
      setError('');
      setOtp(['', '', '', '', '', '']);
      otpRefs.current[0]?.focus();
    } catch (error) {
      setError('Failed to resend OTP');
    }
  };

  return (
    <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
      <View style={styles.container}>
      {/* Branded Logo Section */}
      <View style={styles.logoSection}>
        <View style={styles.logoContainer}>
          <View style={styles.logoBox}>
            <View style={styles.glossyOverlay} />
            <View style={styles.ribbonVertical} />
            <View style={styles.ribbonHorizontal} />
            <Feather name="star" size={40} color="white" />
            <View style={styles.sparkle} />
          </View>
        </View>
        <Text style={styles.brandName}>هديتي</Text>
        <Text style={styles.brandTagline}>أرسل الفرحة لمن تحب بكل حب</Text>
      </View>

      {step === 'PHONE' ? (
        <View style={styles.formSection}>
          <View style={styles.formHeader}>
            <Text style={styles.formTitle}>مرحباً بك</Text>
            <Text style={styles.formSubtitle}>أدخل رقم جوالك للمتابعة</Text>
          </View>

          <View style={styles.inputContainer}>
            <TextInput
              style={styles.phoneInput}
              placeholder="5xxxxxxxx"
              value={phone}
              onChangeText={(text) => {
                setPhone(text);
                if (phoneError) setPhoneError('');
              }}
              keyboardType="phone-pad"
              maxLength={9}
              placeholderTextColor="#9CA3AF"
            />
            <View style={styles.phoneIcon}>
              <Feather name="phone" size={22} color="#E0AAFF" />
            </View>
            <View style={styles.countryCode}>
              <Text style={styles.countryCodeText}>+966</Text>
            </View>
          </View>
          {phoneError ? (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{phoneError}</Text>
            </View>
          ) : null}

            <Pressable onPress={async () => {
              // Validate phone number
              const validationError = validatePhone(phone);
              if (validationError) {
                setPhoneError(validationError);
                return;
              }

              try {
                const response = await sendOTP(phone);
                setSentOtp(response.otp);
                setStep('OTP');
                setTimer(90);
                setCanResend(false);
                setError('');
                setPhoneError(''); // Clear any previous phone errors
              } catch (error: any) {
                setError(error.message || 'Failed to send OTP');
              }
            }} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>إرسال رمز التحقق</Text>
            </Pressable>
        </View>
      ) : (
        <View style={styles.formSection}>
          <View style={styles.formHeader}>
            <Text style={styles.formTitle}>رمز التحقق</Text>
            <Text style={styles.otpSubtitle}>تم إرسال الرمز إلى {phone}</Text>
            {timer > 0 ? (
              <Text style={styles.timerText}>
                {Math.floor(timer / 60)}:{(timer % 60).toString().padStart(2, '0')}
              </Text>
            ) : null}
          </View>

          {error ? (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <View style={styles.otpContainer}>
            {otp.map((digit, index) => (
              <TextInput
                key={index}
                ref={(ref) => {
                  if (ref) otpRefs.current[index] = ref;
                }}
                style={styles.otpInput}
                value={digit}
                onChangeText={(value) => handleOtpChange(value, index)}
                onKeyPress={({ nativeEvent }) => handleOtpKeyPress(nativeEvent.key, index)}
                keyboardType="numeric"
                maxLength={1}
                caretHidden={true}
                selectTextOnFocus={true}
                placeholderTextColor="#9CA3AF"
              />
            ))}
          </View>

          <Text style={styles.debugText}>Sent OTP: {sentOtp}</Text>


            <Pressable onPress={async () => {
              const otpString = otp.join('');
              if (otpString.length !== 6) {
                setError('يرجى إدخال رمز التحقق المكون من 6 أرقام');
                return;
              }

              try {
                const response = await verifyOTP({
                  phone_number: phone,
                  otp: otpString
                });

                // Success - proceed to next screen based on profile completion status
                onNext({
                  phone,
                  token: response.access_token,
                  needsProfile: response.needs_profile
                });
              } catch (error: any) {
                setError(error.message || 'فشل في التحقق من رمز التحقق');
              }
            }} style={styles.primaryButton}>
            <Text style={styles.primaryButtonText}>دخول</Text>
          </Pressable>

          {canResend && (
            <Pressable onPress={handleResendOTP} style={styles.resendButton}>
              <Text style={styles.resendButtonText}>إعادة إرسال الرمز</Text>
            </Pressable>
          )}

          <Pressable onPress={() => setStep('PHONE')} style={styles.changeNumberButton}>
            <Text style={styles.changeNumberText}>تغيير الرقم</Text>
            <Feather name="arrow-left" size={16} color="#E0AAFF" />
          </Pressable>
        </View>
      )}

      <View style={styles.footer}>
        <Text style={styles.footerText}>Hadiyati • Secure Marketplace</Text>
      </View>
      </View>
    </TouchableWithoutFeedback>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 32,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFFFFC',
  },
  logoSection: {
    marginBottom: 48,
    alignItems: 'center',
  },
  logoContainer: {
    marginBottom: 24,
  },
  logoBox: {
    width: 96,
    height: 96,
    backgroundColor: '#E0AAFF',
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 15 },
    shadowOpacity: 0.4,
    shadowRadius: 30,
    elevation: 15,
    transform: [{ rotate: '3deg' }],
    position: 'relative',
  },
  glossyOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 32,
  },
  ribbonVertical: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: '50%',
    width: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.4)',
    transform: [{ translateX: -8 }],
  },
  ribbonHorizontal: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '50%',
    height: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.4)',
    transform: [{ translateY: -8 }],
  },
  sparkle: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 8,
    height: 8,
    backgroundColor: 'white',
    borderRadius: 4,
  },
  brandName: {
    fontSize: 30,
    fontWeight: '900',
    color: '#1F2937',
  },
  brandTagline: {
    fontSize: 14,
    color: '#9CA3AF',
    fontWeight: 'bold',
    marginTop: 8,
  },
  formSection: {
    width: '100%',
    gap: 24,
  },
  formHeader: {
    gap: 8,
    alignItems: 'center',
  },
  formTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#374151',
  },
  formSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: 'bold',
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  inputContainer: {
    position: 'relative',
  },
  phoneInput: {
    width: '100%',
    height: 60,
    backgroundColor: 'white',
    borderWidth: 2,
    borderColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: 80,
    fontSize: 18,
    fontWeight: '900',
    color: '#1F2937',
    textAlign: 'left',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  phoneIcon: {
    position: 'absolute',
    right: 16,
    top: '50%',
    transform: [{ translateY: -11 }],
  },
  countryCode: {
    position: 'absolute',
    left: 16,
    top: '50%',
    transform: [{ translateY: -9 }],
  },
  countryCodeText: {
    fontSize: 14,
    fontWeight: '900',
    color: '#9CA3AF',
  },
  primaryButton: {
    width: '100%',
    height: 60,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#E0AAFF',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 10,
  },
  primaryButtonText: {
    fontSize: 18,
    fontWeight: '900',
    color: 'white',
  },
  otpSubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    fontWeight: 'bold',
  },
  otpContainer: {
    flexDirection: 'row-reverse',
    justifyContent: 'space-between',
    gap: 12,
  },
  otpInput: {
    flex: 1,
    height: 64,
    backgroundColor: 'white',
    borderWidth: 2,
    borderColor: '#F9FAFB',
    borderRadius: 16,
    textAlign: 'center',
    fontSize: 24,
    fontWeight: '900',
    color: '#374151',
    fontFamily: 'monospace',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    writingDirection: 'ltr',
  },
  changeNumberButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    alignSelf: 'center',
  },
  changeNumberText: {
    fontSize: 14,
    fontWeight: '900',
    color: '#E0AAFF',
    textTransform: 'uppercase',
  },
  footer: {
    marginTop: 64,
  },
  footerText: {
    fontSize: 10,
    color: '#D1D5DB',
    fontWeight: '900',
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  errorContainer: {
    backgroundColor: '#FEE2E2',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  errorText: {
    color: '#DC2626',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  timerText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#E0AAFF',
  },
  resendButton: {
    alignSelf: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  resendButtonText: {
    fontSize: 14,
    fontWeight: '900',
    color: '#E0AAFF',
    textTransform: 'uppercase',
  },
  debugText: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
    fontFamily: 'monospace',
  },
});
