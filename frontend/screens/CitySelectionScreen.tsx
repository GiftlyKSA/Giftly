
import React, { useState, useEffect } from 'react';
import { View, Text, Pressable, ScrollView, StyleSheet, Dimensions, Alert, ActivityIndicator } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../App';
import { createOrder, getCities, CityResponse } from '../api';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

interface Props {
  onNext: (orderId: string) => void;
  onBack: () => void;
  orderData?: { description?: string; deliveryDate?: Date };
}

export const CitySelectionScreen: React.FC<Props> = ({ onNext, onBack, orderData }) => {
  const insets = useSafeAreaInsets();
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(false);
  const [cities, setCities] = useState<CityResponse[]>([]);
  const [citiesLoading, setCitiesLoading] = useState(true);
  const [citiesError, setCitiesError] = useState<string | null>(null);
  const { token } = useAuth();

  // Fetch cities on component mount
  useEffect(() => {
    const fetchCities = async () => {
      try {
        setCitiesLoading(true);
        setCitiesError(null);
        const fetchedCities = await getCities();
        setCities(fetchedCities);
      } catch (error) {
        console.error('Failed to fetch cities:', error);
        setCitiesError('فشل في تحميل المدن');
      } finally {
        setCitiesLoading(false);
      }
    };

    fetchCities();
  }, []);

  const handleConfirm = async () => {
    console.log('CitySelectionScreen: Starting order creation');
    console.log('CitySelectionScreen: selected =', selected);
    console.log('CitySelectionScreen: orderData =', orderData);
    console.log('CitySelectionScreen: token =', token ? 'present' : 'missing');

    if (!selected || !orderData?.deliveryDate || !token) {
      Alert.alert('خطأ', 'يرجى اختيار المدينة');
      return;
    }

    setLoading(true);
    try {
      console.log('CitySelectionScreen: Calling createOrder API');
      const order = await createOrder(token, {
        description: orderData?.description || '',
        city_id: parseInt(selected),
        delivery_date: orderData.deliveryDate.toISOString(),
      });
      console.log('CitySelectionScreen: Order created successfully:', order);
      console.log('CitySelectionScreen: Order ID =', order.order_id);

      // Proceed to next screen with order ID
      console.log('CitySelectionScreen: Calling onNext with orderId =', order.order_id);
      onNext(order.order_id);
    } catch (error) {
      console.error('CitySelectionScreen: Error creating order:', error);
      Alert.alert('خطأ', 'فشل في إنشاء الطلب');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + screenHeight * 0.03 }]}>
        <Pressable onPress={onBack} style={styles.backButton}>
          <Feather name="chevron-right" size={20} color="#9CA3AF" />
        </Pressable>
        <Text style={styles.title}>اختر مدينتك</Text>
        <View style={styles.spacer} />
      </View>

      {citiesLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#E0AAFF" />
          <Text style={styles.loadingText}>جاري تحميل المدن...</Text>
        </View>
      ) : citiesError ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{citiesError}</Text>
          <Pressable
            onPress={() => {
              setCitiesLoading(true);
              setCitiesError(null);
              getCities()
                .then(setCities)
                .catch(() => setCitiesError('فشل في تحميل المدن'))
                .finally(() => setCitiesLoading(false));
            }}
            style={styles.retryButton}
          >
            <Text style={styles.retryText}>إعادة المحاولة</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView style={styles.scrollView} contentContainerStyle={styles.grid}>
          {cities.map((city) => (
            <Pressable
              key={city.id}
              onPress={() => setSelected(city.id.toString())}
              style={[
                styles.cityButton,
                selected === city.id.toString() && styles.selectedCityButton,
              ]}
            >
              <Text style={styles.cityIcon}>{city.icon || '🏙️'}</Text>
              <Text style={[styles.cityName, selected === city.id.toString() && styles.selectedCityName]}>{city.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      <View style={styles.bottomContainer}>
        <Pressable
          disabled={!selected || loading}
          onPress={handleConfirm}
          style={[
            styles.confirmButton,
            (!selected || loading) && styles.disabledButton,
          ]}
        >
          <Text style={styles.confirmText}>
            {loading ? 'جاري الإنشاء...' : 'تأكيد والمتابعة للدردشة'}
          </Text>
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Math.max(16, screenWidth * 0.04),
    paddingBottom: screenHeight * 0.04,
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
    fontSize: screenWidth * 0.05,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  spacer: {
    width: screenWidth * 0.1,
  },
  scrollView: {
    flex: 1,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: screenWidth * 0.06,
    paddingBottom: screenHeight * 0.12,
    justifyContent: 'space-between',
  },
  cityButton: {
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: screenWidth * 0.04,
    borderRadius: 24,
    minHeight: screenHeight * 0.12,
    borderWidth: 2,
    borderColor: '#F9FAFB',
    backgroundColor: 'white',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    width: '30%',
    marginBottom: screenHeight * 0.02,
  },
  selectedCityButton: {
    backgroundColor: '#E0AAFF',
    borderColor: '#E0AAFF',
  },
  cityIcon: {
    fontSize: screenWidth * 0.07,
    marginBottom: screenHeight * 0.01,
  },
  cityName: {
    fontSize: screenWidth * 0.025,
    fontWeight: '900',
    textAlign: 'center',
    lineHeight: screenWidth * 0.03,
    color: '#374151',
  },
  selectedCityName: {
    color: 'white',
  },
  bottomContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: screenWidth * 0.06,
    paddingVertical: screenHeight * 0.03,
    backgroundColor: '#FFFFFC',
  },
  confirmButton: {
    width: '100%',
    height: screenHeight * 0.08,
    borderRadius: 16,
    backgroundColor: '#E0AAFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  disabledButton: {
    backgroundColor: '#E5E7EB',
  },
  confirmText: {
    fontSize: screenWidth * 0.045,
    fontWeight: '900',
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
    textAlign: 'center',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  errorText: {
    fontSize: 16,
    color: '#EF4444',
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: '#E0AAFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
