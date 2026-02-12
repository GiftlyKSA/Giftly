
import React, { useState } from 'react';
import { View, Text, Pressable,TextInput, ScrollView, StyleSheet, Dimensions,Platform, Modal, Image, Alert } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import DateTimePicker from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import { MediaType } from 'expo-image-picker';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

interface Props {
  onNext: (description: string, deliveryDate: Date, images?: (string | null)[]) => void;
  onBack: () => void;
}

export const BudgetScreen: React.FC<Props> = ({ onNext, onBack }) => {
  const insets = useSafeAreaInsets();
  const [description, setDescription] = useState('');
  const [deliveryDate, setDeliveryDate] = useState<Date | null>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [dateError, setDateError] = useState('');
  const [tempDate, setTempDate] = useState<Date>(new Date());
  const [showImagePickerModal, setShowImagePickerModal] = useState(false);
  const [selectedImages, setSelectedImages] = useState<(string | null)[]>([null, null, null]);

  const formatArabicDate = (date: Date) => {
    const arabicMonths = [
      'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
      'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
    ];

    const day = date.getDate();
    const month = arabicMonths[date.getMonth()];
    const year = date.getFullYear();

    return `${day} ${month} ${year}`;
  };

  const handleImageSelect = (index: number) => {
    setShowImagePickerModal(true);
    // Store which image slot we're selecting
    (setShowImagePickerModal as any).currentIndex = index;
  };

  const handleImagePickerOption = async (source: 'camera' | 'gallery') => {
    const currentIndex = (setShowImagePickerModal as any).currentIndex;
    setShowImagePickerModal(false);

    try {
      // Request permissions
      if (source === 'camera') {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('خطأ', 'يجب السماح بالوصول للكاميرا');
          return;
        }
      }
        else if (source === 'gallery') {
          const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
          if (status !== 'granted') {
            Alert.alert('خطأ', 'يجب السماح بالوصول للمعرض');
            return;
          }
      }

      // Launch image picker or camera
      const result = source === 'gallery'
        ? await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ['images'],
            allowsEditing: true,
            aspect: [4, 3],
            quality: 0.8,
            base64: true,
          })
        : await ImagePicker.launchCameraAsync({
            mediaTypes: ['images'],
            allowsEditing: true,
            aspect: [4, 3],
            quality: 0.8,
            base64: true,
          });

      if (!result.canceled && result.assets && result.assets[0]) {
        const imageUri = result.assets[0].uri;
        // Convert to base64 for storage
        const response = await fetch(imageUri);
        const blob = await response.blob();
        const base64 = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.readAsDataURL(blob);
        });

        // Update selected images
        const newImages = [...selectedImages];
        newImages[currentIndex] = base64;
        setSelectedImages(newImages);
      }
    } catch (error) {
      console.error('Image picker error:', error);
      Alert.alert('خطأ', 'فشل في اختيار الصورة');
    }
  };

  const removeImage = (index: number) => {
    const newImages = [...selectedImages];
    newImages[index] = null;
    setSelectedImages(newImages);
  };

  const handleNext = () => {
    // Clear previous errors
    setDateError('');

    // Validate delivery date
    if (!deliveryDate) {
      setDateError('يرجى اختيار تاريخ التوصيل');
      return;
    }

    // Proceed to next screen
    onNext(description, deliveryDate, selectedImages);
  };
  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingTop: insets.top + screenHeight * 0.03 }]}>
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.backButton}>
          <Feather name="chevron-right" size={20} color="#9CA3AF" />
        </Pressable>
        <Text style={styles.title}>وصف الهدية</Text>
        <View style={styles.spacer} />
      </View>

      <View style={styles.mainContent}>
        {/* Delivery Date Picker */}
        <View style={styles.datePickerContainer}>
          <Text style={styles.datePickerLabel}>تاريخ التوصيل</Text>
          <Pressable onPress={() => setShowDatePicker(true)} style={[styles.datePickerButton, dateError ? styles.datePickerError : null]}>
            <Text style={[styles.datePickerText, !deliveryDate && styles.datePickerPlaceholder]}>
              { deliveryDate ? formatArabicDate(deliveryDate) : 'اختر تاريخ التوصيل'}
            </Text>
            <Feather name="calendar" size={20} color={dateError ? "#EF4444" : "#E0AAFF"} />
          </Pressable>
          {dateError ? <Text style={styles.errorText}>{dateError}</Text> : null}
        </View>

        <View style={styles.instruction}>
          <Feather name="star" size={18} color="#E0AAFF" />
          <Text style={styles.instructionText}>اكتب وصف الهدية المخصصة المناسبة لك</Text>
        </View>

        <View style={styles.textAreaContainer}>
          <TextInput
            style={styles.textArea}
            value={description}
            onChangeText={setDescription}
            placeholder="مثال: أريد باقة ورد حمراء مع شوكولاتة باتشي مغلفة بشريطة ذهبية وكرت مكتوب عليه..."
            placeholderTextColor="#9CA3AF"
            multiline
            textAlignVertical="top"
          />
          <View style={styles.penIcon}>
            <Feather name="edit-2" size={20} color="#D1D5DB" />
          </View>
        </View>

        <View style={styles.infoBox}>
          <View style={styles.infoIcon}>
            <Feather name="message-circle" size={14} color="#3B82F6" />
          </View>
          <Text style={styles.infoText}>
            اذا ماتعرف وش الهديه لاتشيل هم اترك الوصف وحدد تاريخ تسليم الهديه وخل المندوب يضبطك .
          </Text>
        </View>

        {/* Image Selection Section */}
        <View style={styles.imageSection}>
          <Text style={styles.imageSectionTitle}>صور الطلب (اختياري - حد أقصى 3 صور)</Text>
          <View style={styles.imageGrid}>
            {[0, 1, 2].map((index) => (
              <View key={index} style={styles.imageSlot}>
                {selectedImages[index] ? (
                  <View style={styles.imageContainer}>
                    <Image source={{ uri: selectedImages[index]! }} style={styles.selectedImage} />
                    <Pressable
                      onPress={() => removeImage(index)}
                      style={styles.removeImageButton}
                    >
                      <Feather name="x" size={16} color="white" />
                    </Pressable>
                  </View>
                ) : (
                  <Pressable
                    onPress={() => handleImageSelect(index)}
                    style={styles.addImageButton}
                  >
                    <Feather name="plus" size={24} color="#E0AAFF" />
                    <Text style={styles.addImageText}>إضافة صورة</Text>
                  </Pressable>
                )}
              </View>
            ))}
          </View>
        </View>
        </View>

        <Modal
          visible={showDatePicker}
          transparent
          animationType="fade"
          onRequestClose={() => setShowDatePicker(false)}
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
                minimumDate={(() => {
                  const today = new Date();
                  today.setHours(0, 0, 0, 0);
                  return today;
                })()}
                maximumDate={(() => {
                  const maxDate = new Date();
                  maxDate.setFullYear(maxDate.getFullYear() + 1);
                  return maxDate;
                })()}
                locale="en-US"
                accentColor="#000000"
                textColor="#000000"
                onChange={(_, date) => {
                  if (date) setTempDate(date); // only update temp dateit
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
                <Pressable onPress={() => setShowDatePicker(false)}>
                  <Text style={{ color: '#6B7280', fontSize: 16 }}>
                    إلغاء
                  </Text>
                </Pressable>

                <Pressable
                  onPress={() => {
                    setDeliveryDate(tempDate); // just set the date
                    setDateError(''); // Clear error when date is selected
                    setShowDatePicker(false);
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

        {/* Image Picker Modal */}
        <Modal
          visible={showImagePickerModal}
          animationType="fade"
          transparent={true}
          onRequestClose={() => setShowImagePickerModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.imagePickerModal}>
              <View style={styles.imagePickerModalHeader}>
                <Text style={styles.imagePickerModalTitle}>اختر صورة</Text>
                <Pressable onPress={() => setShowImagePickerModal(false)} style={styles.closeButton}>
                  <Feather name="x" size={20} color="#9CA3AF" />
                </Pressable>
              </View>

              <View style={styles.imagePickerOptions}>
                <Pressable
                  onPress={() => handleImagePickerOption('gallery')}
                  style={styles.imagePickerOption}
                >
                  <View style={styles.imagePickerOptionIcon}>
                    <Feather name="image" size={24} color="#E0AAFF" />
                  </View>
                  <Text style={styles.imagePickerOptionText}>من المعرض</Text>
                </Pressable>
                <Pressable
                  onPress={() => handleImagePickerOption('camera')}
                  style={styles.imagePickerOption}
                >
                  <View style={styles.imagePickerOptionIcon}>
                    <Feather name="camera" size={24} color="#E0AAFF" />
                  </View>
                  <Text style={styles.imagePickerOptionText}>الكاميرا</Text>
                </Pressable>
              </View>
            </View>
          </View>
        </Modal>

        <View style={styles.buttonContainer}>
          <Pressable onPress={handleNext} style={styles.button}>
            <Text style={styles.buttonText}>
              {description.trim() ? 'المتابعة لاختيار المدينة' : 'خلّ المندوب يضبطك'}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFC',
  },
  content: {
    paddingHorizontal: screenWidth * 0.06, // 6% of screen width
    paddingBottom: screenHeight * 0.15,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Math.max(16, screenWidth * 0.04),
    marginBottom: screenHeight * 0.04,
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
    fontSize: screenWidth * 0.05, // Responsive font size
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'right',
  },
  spacer: {
    width: screenWidth * 0.1,
  },
  mainContent: {
    flex: 1,
  },
  instruction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: screenHeight * 0.03,
  },
  instructionText: {
    fontSize: screenWidth * 0.045,
    fontWeight: 'bold',
    color: '#4B5563',
    flex: 1,
    lineHeight: screenWidth * 0.06,
    textAlign: 'right',
  },
  textAreaContainer: {
    position: 'relative',
    marginBottom: screenHeight * 0.03,
  },
  textArea: {
    width: '100%',
    height: screenHeight * 0.15, // 15% of screen height
    backgroundColor: 'white',
    borderWidth: 2,
    borderColor: '#F9FAFB',
    borderRadius: 32,
    padding: screenWidth * 0.08,
    fontSize: screenWidth * 0.035,
    fontWeight: '500',
    color: '#1F2937',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    textAlign: 'right',
  },
  penIcon: {
    position: 'absolute',
    top: screenHeight * 0.02,
    left: screenWidth * 0.06,
  },
  infoBox: {
    backgroundColor: 'rgba(219, 234, 254, 0.5)',
    borderRadius: 16,
    padding: screenWidth * 0.04,
    flexDirection: 'row',
    alignItems: 'center',
    gap: screenWidth * 0.03,
    borderWidth: 1,
    borderColor: 'rgba(219, 234, 254, 1)',
    minHeight: screenHeight * 0.1,
  },
  infoIcon: {
    width: screenWidth * 0.08,
    height: screenWidth * 0.08,
    borderRadius: screenWidth * 0.04,
    backgroundColor: 'rgba(219, 234, 254, 1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoText: {
    fontSize: screenWidth * 0.025,
    color: '#2563EB',
    fontWeight: '900',
    flex: 1,
    lineHeight: screenWidth * 0.035,
    textAlign: 'right',
  },
  buttonContainer: {
    paddingTop: screenHeight * 0.03,
  },
  button: {
    width: '100%',
    height: screenHeight * 0.08,
    backgroundColor: '#E0AAFF',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  buttonText: {
    fontSize: screenWidth * 0.045,
    fontWeight: '900',
    color: 'white',
    textAlign: 'right',
  },
  datePickerContainer: {
    marginBottom: screenHeight * 0.03,
  },
  datePickerLabel: {
    fontSize: screenWidth * 0.04,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: screenHeight * 0.01,
    textAlign: 'right',
  },
  datePickerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'white',
    borderWidth: 2,
    borderColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: screenWidth * 0.04,
    paddingVertical: screenHeight * 0.015,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  datePickerText: {
    fontSize: screenWidth * 0.035,
    fontWeight: '500',
    color: '#1F2937',
    textAlign: 'right',
  },
  datePickerPlaceholder: {
    color: '#9CA3AF',
  },
  datePickerError: {
    borderColor: '#EF4444',
  },
  errorText: {
    fontSize: screenWidth * 0.03,
    color: '#EF4444',
    fontWeight: '500',
    textAlign: 'right',
    marginTop: screenHeight * 0.005,
  },
  imageSection: {
    paddingTop: screenHeight * 0.02,
    paddingBottom: screenHeight * 0.03,
  },
  imageSectionTitle: {
    fontSize: screenWidth * 0.04,
    fontWeight: 'bold',
    color: '#1F2937',
    marginBottom: screenHeight * 0.02,
    textAlign: 'right',
  },
  imageGrid: {
    flexDirection: 'row',
    gap: screenWidth * 0.03,
  },
  imageSlot: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 16,
    overflow: 'hidden',
  },
  addImageButton: {
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderWidth: 2,
    borderColor: 'rgba(224, 170, 255, 0.3)',
    borderStyle: 'dashed',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    gap: screenHeight * 0.01,
  },
  addImageText: {
    fontSize: screenWidth * 0.03,
    fontWeight: 'bold',
    color: '#E0AAFF',
    textAlign: 'center',
  },
  imageContainer: {
    width: '100%',
    height: '100%',
    position: 'relative',
  },
  selectedImage: {
    width: '100%',
    height: '100%',
    borderRadius: 16,
  },
  removeImageButton: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.8)',
    borderRadius: 12,
    padding: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  imagePickerModal: {
    backgroundColor: 'white',
    borderRadius: 32,
    padding: 24,
    width: '90%',
    maxWidth: 400,
  },
  imagePickerModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  imagePickerModalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1F2937',
  },
  closeButton: {
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
  },
  imagePickerOptions: {
    gap: 16,
  },
  imagePickerOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  imagePickerOptionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  imagePickerOptionText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#1F2937',
  },
});
