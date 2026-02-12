import AsyncStorage from '@react-native-async-storage/async-storage';

const SERVICE = 'giftly';
const REFRESH_TOKEN_KEY = '@giftly_refresh_token';

// Safely import Keychain
let Keychain: any = null;
let isKeychainAvailable = false;

try {
  Keychain = require('react-native-keychain');
  isKeychainAvailable = Keychain &&
                       typeof Keychain.setGenericPassword === 'function' &&
                       typeof Keychain.getGenericPassword === 'function' &&
                       typeof Keychain.resetGenericPassword === 'function';
} catch (error) {
  console.warn('Keychain import failed, using AsyncStorage fallback:', error);
  isKeychainAvailable = false;
}

export async function getRefreshToken(): Promise<string | null> {
  try {
    if (isKeychainAvailable) {
      const credentials = await Keychain.getGenericPassword({ service: SERVICE });
      if (credentials?.password) {
        return credentials.password;
      }
    }

    // Fallback to AsyncStorage if Keychain is not available or empty
    console.warn('Using AsyncStorage fallback for refresh token');
    const token = await AsyncStorage.getItem(REFRESH_TOKEN_KEY);
    return token;
  } catch (error) {
    console.error('Failed to get refresh token:', error);
    return null;
  }
}

export async function saveRefreshToken(token: string): Promise<void> {
  try {
    if (isKeychainAvailable) {
      // Note: Keychain API uses "password" as generic term for stored value
      // We're storing refresh tokens, not actual passwords
      await Keychain.setGenericPassword('refresh', token, { service: SERVICE });
    } else {
      // Fallback to AsyncStorage
      console.warn('Using AsyncStorage fallback for refresh token storage');
      await AsyncStorage.setItem(REFRESH_TOKEN_KEY, token);
    }
  } catch (error) {
    console.error('Failed to save refresh token:', error);
    // Try AsyncStorage as last resort
    try {
      await AsyncStorage.setItem(REFRESH_TOKEN_KEY, token);
    } catch (fallbackError) {
      console.error('Failed to save to AsyncStorage fallback:', fallbackError);
    }
  }
}

export async function deleteRefreshToken(): Promise<void> {
  try {
    if (isKeychainAvailable) {
      await Keychain.resetGenericPassword({ service: SERVICE });
    }

    // Always clear AsyncStorage fallback
    await AsyncStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch (error) {
    console.error('Failed to delete refresh token:', error);
    // Try to clear AsyncStorage anyway
    try {
      await AsyncStorage.removeItem(REFRESH_TOKEN_KEY);
    } catch (fallbackError) {
      console.error('Failed to clear AsyncStorage fallback:', fallbackError);
    }
  }
}
