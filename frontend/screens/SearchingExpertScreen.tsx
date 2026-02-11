
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Image, Pressable } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { webSocketService } from '../WebSocketService';

interface Props {
  orderId: string;
  onNavigateToChat: (orderId: string) => void;
  onBack: () => void;
}

export const SearchingExpertScreen: React.FC<Props> = ({ orderId, onNavigateToChat, onBack }) => {
  const insets = useSafeAreaInsets();
  const [dots, setDots] = useState('');
  const [acceptedCourier, setAcceptedCourier] = useState<{ name: string; id: number } | null>(null);

  useEffect(() => {
    console.log('SearchingExpertScreen: orderId =', orderId);

    if (!orderId) {
      console.error('SearchingExpertScreen: No orderId provided!');
      return;
    }

    // Animate the dots
    const dotsInterval = setInterval(() => {
      setDots(prev => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);

    // Listen for order status changes via WebSocket
    const handleOrderStatusChange = (message: any) => {
      console.log('SearchingExpertScreen: Order status change received:', message);
      if (message.data && message.data.status === 'received by courier') {
        console.log('SearchingExpertScreen: Courier accepted order');

        // Extract courier information from the message
        const courierInfo = message.data.courier_info || message.data;
        if (courierInfo && courierInfo.name) {
          setAcceptedCourier({
            name: courierInfo.name,
            id: courierInfo.id || courierInfo.courier_id
          });
        }

        // Navigate to chat after a short delay to show the courier info
        setTimeout(() => {
          console.log('SearchingExpertScreen: Navigating to chat');
          onNavigateToChat(orderId);
        }, 2000);
      }
    };

    webSocketService.onOrderStatusChange(handleOrderStatusChange);

    return () => {
      clearInterval(dotsInterval);
      webSocketService.off('order_status_change', handleOrderStatusChange);
    };
  }, [orderId, onNavigateToChat]);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 16 }]}>
        <Pressable onPress={onBack} style={styles.backButton}>
          <Feather name="chevron-right" size={24} color="#9CA3AF" />
        </Pressable>
        <Text style={styles.headerTitle}>البحث عن خبير</Text>
        <View style={styles.spacer} />
      </View>

      <View style={styles.loaderContainer}>
        <View style={styles.loaderBackground} />
        <View style={styles.loaderIcon}>
          <Feather name="loader" size={64} color="#E0AAFF" />
        </View>
        <View style={styles.giftIcon}>
          <Feather name="gift" size={20} color="#E0AAFF" />
        </View>
        <View style={styles.shieldIcon}>
          <Feather name="shield" size={20} color="#E0AAFF" />
        </View>
      </View>

      <View style={styles.content}>
        {acceptedCourier ? (
          <>
            <Text style={styles.title}>تم العثور على خبير!</Text>
            <Text style={styles.subtitle}>
              {acceptedCourier.name} سيتولى تنسيق هديتك الآن
            </Text>
            <View style={styles.courierContainer}>
              <View style={styles.courierAvatar}>
                <Feather name="user" size={32} color="#E0AAFF" />
              </View>
              <Text style={styles.courierName}>{acceptedCourier.name}</Text>
              <Text style={styles.courierStatus}>جاري التحضير للدردشة...</Text>
            </View>
          </>
        ) : (
          <>
            <Text style={styles.title}>جاري البحث عن خبير هدايا{dots}</Text>
            <Text style={styles.subtitle}>
              نقوم الآن باختيار أفضل خبير متاح لتنسيق هديتك بكل حب وإتقان
            </Text>

            <View style={styles.expertsContainer}>
              <View style={styles.expertsList}>
                {[1, 2, 3, 4].map(i => (
                  <View key={i} style={styles.expertAvatar}>
                    <Image
                      source={{ uri: `https://picsum.photos/seed/expert${i}/100/100` }}
                      style={styles.expertImage}
                    />
                  </View>
                ))}
              </View>
            </View>
          </>
        )}
      </View>

      <View style={styles.infoBox}>
        <View style={styles.infoIcon}>
          <Feather name="star" size={16} color="#10B981" />
        </View>
        <Text style={styles.infoText}>
          سيقوم الخبير بالتواصل معك فوراً عبر الدردشة لمناقشة تفاصيل الهدية وتنسيقها.
        </Text>
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
    backgroundColor: 'white',
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1F2937',
  },
  spacer: {
    width: 40,
  },
  loaderContainer: {
    marginTop: 48,
    marginBottom: 48,
    position: 'relative',
    alignSelf: 'center',
  },
  loaderBackground: {
    width: 128,
    height: 128,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    borderRadius: 64,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loaderIcon: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: [{ translateX: -32 }, { translateY: -32 }],
  },
  giftIcon: {
    position: 'absolute',
    top: -8,
    right: -8,
    width: 40,
    height: 40,
    backgroundColor: 'white',
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  shieldIcon: {
    position: 'absolute',
    bottom: -8,
    left: -8,
    width: 40,
    height: 40,
    backgroundColor: 'white',
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  content: {
    alignItems: 'center',
    gap: 24,
    marginBottom: 48,
  },
  title: {
    fontSize: 30,
    fontWeight: '900',
    color: '#1F2937',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: '#9CA3AF',
    fontWeight: '500',
    textAlign: 'center',
    maxWidth: 280,
    lineHeight: 24,
  },
  expertsContainer: {
    alignItems: 'center',
    gap: 12,
  },
  expertsList: {
    flexDirection: 'row',
    gap: -12,
  },
  expertAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: 'white',
    backgroundColor: '#F3F4F6',
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  expertImage: {
    width: '100%',
    height: '100%',
  },

  infoBox: {
    position: 'absolute',
    bottom: 48,
    left: 48,
    right: 48,
    backgroundColor: 'white',
    borderRadius: 24,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F9FAFB',
  },
  infoIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoText: {
    fontSize: 10,
    color: '#374151',
    fontWeight: 'bold',
    flex: 1,
    lineHeight: 14,
  },
  courierContainer: {
    alignItems: 'center',
    gap: 16,
  },
  courierAvatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(224, 170, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  courierName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1F2937',
    textAlign: 'center',
  },
  courierStatus: {
    fontSize: 14,
    color: '#10B981',
    fontWeight: '600',
    textAlign: 'center',
  },
});
