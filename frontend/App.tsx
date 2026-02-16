import React, { useState, createContext, useContext, useEffect, useCallback } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { WelcomeScreen } from './screens/WelcomeScreen';
import { LoginScreen } from './screens/LoginScreen';
import { CompleteProfileScreen } from './screens/CompleteProfileScreen';
import { HomeScreen } from './screens/HomeScreen';
import { BudgetScreen } from './screens/BudgetScreen';
import { CitySelectionScreen } from './screens/CitySelectionScreen';
import { ProfileScreen } from './screens/ProfileScreen';
import { CourierChatScreen } from './screens/CourierChatScreen';
import { CustomerChatScreen } from './screens/CustomerChatScreen';
import { SearchingExpertScreen } from './screens/SearchingExpertScreen';
import { CourierHomeScreen } from './screens/CourierHomeScreen';
import { CourierLoginScreen } from './screens/CourierLoginScreen';
import { InvoiceScreen } from './screens/InvoiceScreen';
import { Message } from './types';
import { webSocketService } from './WebSocketService';

type Screen = 'welcome' | 'login' | 'profile' | 'home' | 'budget' | 'citySelection' | 'userProfile' | 'courierChat' | 'customerChat' | 'searchingExpert' | 'courierLogin' | 'courierHome' | 'invoice';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

// Auth Context
interface UserData {
  id: number;
  phone_number: string;
  email: string;
  name: string;
  date_of_birth: string | null;
  national_id: string | null;
  passport_id: string | null;
  is_verified: boolean;
  role: string;
}

interface AuthContextType {
  token: string | null;
  phone: string | null;
  userData: UserData | null;
  login: (token: string, phone: string) => Promise<UserData>;
  logout: () => void;
  fetchUserData: () => Promise<void>;
  updateToken: (newToken: string) => void;
  setAppStateResetCallback: (callback: () => void) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Auth Provider Component
const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [phone, setPhone] = useState<string | null>(null);
  const [userData, setUserData] = useState<UserData | null>(null);
  const [appStateResetCallback, setAppStateResetCallback] = useState<(() => void) | null>(null);

  const login = async (newToken: string, newPhone: string): Promise<UserData> => {
    setToken(newToken);
    setPhone(newPhone);

    // Fetch user data directly from API instead of relying on state
    try {
      const { getUserDetails } = await import('./api');
      const userData = await getUserDetails(newToken);
      console.log('API returned userData:', JSON.stringify(userData));
      setUserData(userData); // Also update the state
      console.log('Set userData state to:', JSON.stringify(userData));
      return userData;
    } catch (error) {
      console.error('Failed to fetch user data in login:', error);
      throw error;
    }
  };

  const updateToken = (newToken: string) => {
    setToken(newToken);
  };

  const logout = async () => {
    try {
      // Call backend logout API to revoke refresh token
      if (token) {
        const { logout: logoutAPI } = await import('./api');
        await logoutAPI(token);
      }
    } catch (error) {
      console.error('Error calling logout API:', error);
      // Continue with frontend cleanup even if API call fails
    }

    // Call the app state reset callback to clear all screen states
    if (appStateResetCallback) {
      appStateResetCallback();
    }

    // Disconnect WebSocket and clear all connections
    webSocketService.disconnect();

    // Clear all auth data
    setToken(null);
    setPhone(null);
    setUserData(null);
  };

  const fetchUserData = async (authToken?: string) => {
    const currentToken = authToken || token;
    if (!currentToken) return;

    try {
      const { getUserDetails } = await import('./api');
      const data = await getUserDetails(currentToken);
      setUserData(data);
    } catch (error) {
      console.error('Failed to fetch user data:', error);
    }
  };

  // Set token update callback for API refresh
  useEffect(() => {
    const { setTokenUpdateCallback } = require('./api');
    setTokenUpdateCallback(updateToken);
  }, []);

  // Connect to WebSocket when token is available
  useEffect(() => {
    if (token) {
      webSocketService.connect(token);
    } else {
      webSocketService.disconnect();
    }

    return () => {
      webSocketService.disconnect();
    };
  }, [token]);

  // Join appropriate room when user data is available
  useEffect(() => {
    if (token && userData && userData.id) {
      // Small delay to ensure this is the current session's userData
      const timeoutId = setTimeout(() => {
        if (userData.role === 'Courier') {
          console.log('Joining couriers room for courier user');
          webSocketService.joinRoom('couriers');
        } else {
          console.log('Joining user room for customer user:', `user_${userData.id}`);
          webSocketService.joinRoom(`user_${userData.id}`);
        }
      }, 500); // Wait 500ms to ensure userData is stable

      return () => clearTimeout(timeoutId);
    }
  }, [token, userData?.id, userData?.role]); // More specific dependencies

  return (
    <AuthContext.Provider value={{ token, phone, userData, login, logout, fetchUserData, updateToken, setAppStateResetCallback }}>
      {children}
    </AuthContext.Provider>
  );
};

const AppContent: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>('welcome');
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [authData, setAuthData] = useState<{ phone: string; otp?: string; token?: string } | null>(null);
  const [orderData, setOrderData] = useState<{ description?: string; cityId?: number; deliveryDate?: Date; images?: (string | null)[] } | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [currentOrderId, setCurrentOrderId] = useState<string | null>(null);
  const [initialHomeTab, setInitialHomeTab] = useState<'home' | 'orders'>('home');
  const [previousScreen, setPreviousScreen] = useState<Screen>('home');
  const [chatStates, setChatStates] = useState<{
    [orderId: string]: {
      messages: Message[];
      input: string;
      order: any;
    };
  }>({});
  const [courierChatStates, setCourierChatStates] = useState<{
    [orderId: string]: {
      messages: Message[];
      input: string;
      order: any;
      conversation: any;
    };
  }>({});
  const [selectedCourierOrderId, setSelectedCourierOrderId] = useState<string | null>(null);
  const [ordersData, setOrdersData] = useState<any[]>([]);
  const { login, token, userData, logout, setAppStateResetCallback } = useAuth();

  // Reset all app states function
  const resetAllAppStates = useCallback(() => {
    setCurrentScreen('welcome');
    setIsDarkMode(false);
    setAuthData(null);
    setOrderData(null);
    setSelectedOrderId(null);
    setCurrentOrderId(null);
    setInitialHomeTab('home');
    setPreviousScreen('home');
    setChatStates({});
    setCourierChatStates({});
    setSelectedCourierOrderId(null);
    setOrdersData([]);
  }, []);

  // Set the reset callback in auth context
  useEffect(() => {
    setAppStateResetCallback(resetAllAppStates);
  }, [setAppStateResetCallback, resetAllAppStates]);

  // Handle WebSocket events
  useEffect(() => {
    const handleOrderStatusChange = (message: any) => {
      console.log('Order status change:', message);
      // Update orders data if this order is in the list
      setOrdersData(prevOrders =>
        prevOrders.map(order =>
          order.id === message.data.order_id
            ? { ...order, status: message.data.status, updated_at: message.data.updated_at }
            : order
        )
      );
    };

    const handleChatMessage = (message: any) => {
      console.log('Chat message received:', message);
      const room = message.room;
      const chatData = message.data;

      // Update chat states if we're in the relevant chat
      if (room.startsWith('chat_')) {
        const conversationId = room.split('_')[1];
        // Find which order this conversation belongs to and update the chat state
        // This would require mapping conversation IDs to order IDs, which might need additional API calls
        // For now, we'll just log it and let the chat screens handle real-time updates
      }
    };

    const handleNewOrder = (message: any) => {
      console.log('New order received:', message);
      // Couriers will receive new orders in real-time
      // The CourierHomeScreen should refresh its available orders
    };

    webSocketService.onOrderStatusChange(handleOrderStatusChange);
    webSocketService.onChatMessage(handleChatMessage);
    webSocketService.on('new_order', handleNewOrder);

    return () => {
      webSocketService.off('order_status_change', handleOrderStatusChange);
      webSocketService.off('chat_message', handleChatMessage);
    };
  }, []);



  const handleChatStateChange = useCallback((state: { messages: Message[]; input: string; order: any }) => {
    if (selectedOrderId) {
      setChatStates(prev => ({
        ...prev,
        [selectedOrderId]: state
      }));
    }
  }, [selectedOrderId]);

  const handleCourierChatStateChange = useCallback((state: { messages: Message[]; input: string; order: any; conversation: any }) => {
    if (selectedCourierOrderId) {
      setCourierChatStates(prev => ({
        ...prev,
        [selectedCourierOrderId]: state
      }));
    }
  }, [selectedCourierOrderId]);

  const currentChatState = selectedOrderId ? chatStates[selectedOrderId] : null;
  const currentCourierChatState = selectedCourierOrderId ? courierChatStates[selectedCourierOrderId] : null;

  const fetchOrders = async () => {
    if (!token) return;
    try {
      const { getUserOrders } = await import('./api');
      const userOrders = await getUserOrders(token);

      // Sort orders: Cancelled orders last, all others by creation date (newest first)
      const sortedOrders = userOrders.sort((a, b) => {
        // First priority: Non-cancelled orders come before cancelled orders
        if (a.status === 'cancelled' && b.status !== 'cancelled') return 1;
        if (a.status !== 'cancelled' && b.status === 'cancelled') return -1;

        // Second priority: Sort by creation date (newest first)
        const dateA = new Date(a.creation_date).getTime();
        const dateB = new Date(b.creation_date).getTime();
        return dateB - dateA;
      });

      setOrdersData(sortedOrders);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    }
  };

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
  };

  // Theme colors based on dark mode
  const theme = {
    backgroundColor: isDarkMode ? '#121212' : '#FFFFFC',
    textColor: isDarkMode ? '#FFFFFF' : '#1F2937',
    secondaryTextColor: isDarkMode ? '#9CA3AF' : '#6B7280',
    cardBackground: isDarkMode ? '#1F2937' : 'white',
    borderColor: isDarkMode ? '#374151' : '#F3F4F6',
  };

  const renderScreen = () => {
    // Role-based screen access control
    const isCourier = userData?.role === 'Courier';
    const isCustomer = !isCourier;

    console.log('renderScreen: currentScreen =', currentScreen, 'userData =', JSON.stringify(userData), 'userRole =', userData?.role, 'isCourier =', isCourier, 'isCustomer =', isCustomer);

    // Define customer-only screens
    const customerScreens = ['home', 'budget', 'citySelection', 'userProfile', 'customerChat', 'searchingExpert'];
    // Define courier-only screens
    const courierScreens = ['courierHome', 'courierChat', 'courierLogin'];
    // Define shared screens (accessible by both)
    const sharedScreens = ['welcome', 'login', 'profile', 'invoice'];

    // Check if current screen is accessible by current user role
    if (customerScreens.includes(currentScreen) && isCourier) {
      // Courier trying to access customer screen - redirect to courier home
      console.warn('Courier attempting to access customer screen, redirecting to courierHome');
      setCurrentScreen('courierHome');
      return <CourierHomeScreen
        onLogout={() => setCurrentScreen('welcome')}
        onAcceptOrder={() => {}}
        onNavigateToChat={(orderId) => {
          setSelectedCourierOrderId(orderId);
          setCurrentScreen('courierChat');
        }}
        isDarkMode={isDarkMode}
        toggleDarkMode={toggleDarkMode}
        theme={theme}
      />;
    }

    if (courierScreens.includes(currentScreen) && isCustomer) {
      // Customer trying to access courier screen - redirect to customer home
      console.warn('Customer attempting to access courier screen, redirecting to home');
      setCurrentScreen('home');
      return (
        <HomeScreen
          onNavigateProfile={() => setCurrentScreen('userProfile')}
          onNavigateCourier={() => setCurrentScreen('courierChat')}
          onStartOrder={() => setCurrentScreen('budget')}
          onShowInvoice={(invoiceId) => {
            setPreviousScreen('home');
            setCurrentOrderId(invoiceId);
            setCurrentScreen('invoice');
          }}
          onNavigateToOrderChat={(orderId) => {
            setSelectedOrderId(orderId);
            setCurrentScreen('customerChat');
          }}
          initialTab={initialHomeTab}
          ordersData={ordersData}
          onOrdersDataChange={setOrdersData}
        />
      );
    }

    switch (currentScreen) {
      case 'welcome':
        return <WelcomeScreen onStart={() => setCurrentScreen('login')} />;
      case 'login':
        return <LoginScreen onNext={async (result) => {
          console.log('🔐 LOGIN PROCESS STARTED');
          console.log('Login result:', { needsProfile: result.needsProfile, hasToken: !!result.token, hasRefreshToken: !!result.refreshToken });

          if (result.needsProfile) {
            console.log('📝 User needs to complete profile');
            setAuthData({ phone: result.phone, otp: result.otp });
            setCurrentScreen('profile');
          } else if (result.token) {
            console.log('✅ User has token, proceeding with login...');

            // Save refresh token and login user
            try {
              if (result.refreshToken) {
                console.log('💾 Saving refresh token...');
                const { saveRefreshToken } = await import('./auth');
                await saveRefreshToken(result.refreshToken);
                console.log('✅ Refresh token saved');
              }

              console.log('🔍 Calling login function...');
              // Login and get user data
              const userData = await login(result.token, result.phone);
              console.log('🎉 Login successful, userData:', userData);
              console.log('👤 User role from API:', userData.role);
              console.log('🆔 User ID:', userData.id);
              console.log('📞 User phone:', userData.phone_number);

              // Route based on user role
              if (userData.role === 'Courier') {
                console.log('🚚 Routing COURIER to courierHome screen');
                setCurrentScreen('courierHome');
                console.log('✅ Screen set to: courierHome');
              } else {
                console.log('👤 Routing CUSTOMER to home screen');
                setCurrentScreen('home');
                console.log('✅ Screen set to: home');
              }

              console.log('🎯 LOGIN PROCESS COMPLETED SUCCESSFULLY');

            } catch (error) {
              console.error('❌ Failed to login user:', error);
              // Fallback to home screen
              setCurrentScreen('home');
              console.log('⚠️ Fallback: Screen set to home due to error');
            }
          } else {
            console.log('❓ No token or profile needed - unexpected state');
          }
        }} />;
      case 'profile':
        return <CompleteProfileScreen
          phone={authData?.phone || ''}
          otp={authData?.otp || ''}
          onNext={async (token, refreshToken) => {
            // Save refresh token and login user
            try {
              const { saveRefreshToken } = await import('./auth');
              await saveRefreshToken(refreshToken);

              // Login and get user data
              const userData = await login(token, authData?.phone || '');
              console.log('Profile completion successful, userData:', userData);

              // Route based on user role
              if (userData.role === 'Courier') {
                console.log('Routing courier to courierHome after profile completion');
                setCurrentScreen('courierHome');
              } else {
                console.log('Routing customer to home after profile completion');
                setCurrentScreen('home');
              }
            } catch (error) {
              console.error('Failed to complete profile:', error);
              // Fallback to home screen
              setCurrentScreen('home');
            }
          }}
        />;
      case 'home':
        return (
          <HomeScreen
            onNavigateProfile={() => setCurrentScreen('userProfile')}
            onNavigateCourier={() => setCurrentScreen('courierChat')}
            onStartOrder={() => setCurrentScreen('budget')}
            onShowInvoice={(invoiceId) => {
              setPreviousScreen('home');
              setCurrentOrderId(invoiceId);
              setCurrentScreen('invoice');
            }}
            onNavigateToOrderChat={(orderId) => {
              setSelectedOrderId(orderId);
              setCurrentScreen('customerChat');
            }}
            initialTab={initialHomeTab}
            ordersData={ordersData}
            onOrdersDataChange={setOrdersData}
          />
        );
      case 'budget':
        return <BudgetScreen
          onNext={(description, deliveryDate, images) => {
            setOrderData({ description, deliveryDate, images });
            setCurrentScreen('citySelection');
          }}
          onBack={() => setCurrentScreen('home')}
        />;
      case 'citySelection':
        return <CitySelectionScreen
          onNext={(orderId) => {
            setSelectedOrderId(orderId);
            setCurrentScreen('searchingExpert');
          }}
          onBack={() => setCurrentScreen('budget')}
          orderData={orderData || undefined}
        />;
      case 'userProfile':
        return <ProfileScreen
          onBack={() => setCurrentScreen('home')}
          onLogout={logout}
          onNavigateHome={() => setCurrentScreen('home')}
          onNavigateOrders={() => setCurrentScreen('home')} // Navigate to home with orders tab
          onNavigateCourier={() => setCurrentScreen('courierChat')}
          isDarkMode={isDarkMode}
          toggleDarkMode={toggleDarkMode}
          theme={theme}
        />;
      case 'courierChat':
        console.log('App.tsx: Rendering CourierChatScreen with selectedCourierOrderId:', selectedCourierOrderId);
        return <CourierChatScreen
          orderId={selectedCourierOrderId}
          chatState={currentCourierChatState}
          onChatStateChange={handleCourierChatStateChange}
          onShowInvoice={(orderId) => {
            console.log('App.tsx: Courier onShowInvoice called with orderId:', orderId);
            setPreviousScreen('courierChat');
            setCurrentOrderId(orderId);
            setCurrentScreen('invoice');
          }}
          onBack={() => {
            setCurrentScreen('courierHome');
          }}
        />;
      case 'customerChat':
        console.log('App.tsx: Rendering CustomerChatScreen with selectedOrderId:', selectedOrderId);
        return <CustomerChatScreen
          orderId={selectedOrderId}
          chatState={currentChatState}
          onChatStateChange={handleChatStateChange}
          onShowInvoice={(orderId) => {
            console.log('App.tsx: onShowInvoice called with orderId:', orderId);
            setPreviousScreen('customerChat');
            setCurrentOrderId(orderId);
            setCurrentScreen('invoice');
          }}
          onBack={() => {
            setInitialHomeTab('orders');
            setCurrentScreen('home');
          }}
        />;
      case 'invoice':
        return <InvoiceScreen
          key={currentOrderId}
          invoiceId={currentOrderId || 0}
          onBack={() => {
            if (previousScreen === 'customerChat') {
              setCurrentScreen('customerChat');
            } else if (previousScreen === 'home') {
              setInitialHomeTab('orders');
              setCurrentScreen('home');
            } else {
              setCurrentScreen(previousScreen);
            }
          }}
        />;
      case 'searchingExpert':
        console.log('App.tsx: Rendering SearchingExpertScreen with orderId =', selectedOrderId);
        return <SearchingExpertScreen
          orderId={selectedOrderId || ''}
          onNavigateToChat={(orderId) => {
            console.log('App.tsx: SearchingExpertScreen onNavigateToChat called with orderId =', orderId);
            setSelectedOrderId(orderId);
            setCurrentScreen('customerChat');
          }}
          onBack={() => {
            setInitialHomeTab('home');
            setCurrentScreen('home');
          }}
        />;
      case 'courierLogin':
        return <CourierLoginScreen onNext={() => setCurrentScreen('courierHome')} onBack={() => setCurrentScreen('login')} />;
      case 'courierHome':
        return <CourierHomeScreen
          onLogout={logout}
          onAcceptOrder={() => {}}
          onNavigateToChat={(orderId) => {
            setSelectedCourierOrderId(orderId);
            setCurrentScreen('courierChat');
          }}
          isDarkMode={isDarkMode}
          toggleDarkMode={toggleDarkMode}
          theme={theme}
        />;
      default:
        return <WelcomeScreen onStart={() => setCurrentScreen('login')} />;
    }
  };

  return (
    <SafeAreaProvider>
      <View style={styles.container}>
        {renderScreen()}
      </View>
    </SafeAreaProvider>
  );
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFC',
    direction: 'rtl',
  },
});

export default App;
