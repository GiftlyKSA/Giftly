import * as SecureStore from 'expo-secure-store';

const REFRESH_TOKEN_KEY = 'giftly_refresh_token';

export async function getRefreshToken(): Promise<string | null> {
  try {
    const token = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    return token;
  } catch (error) {
    console.error('Failed to get refresh token from SecureStore:', error);
    return null;
  }
}

export async function saveRefreshToken(token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  } catch (error) {
    console.error('Failed to save refresh token to SecureStore:', error);
    // Don't throw - allow app to continue without secure storage
  }
}

export async function deleteRefreshToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  } catch (error) {
    console.error('Failed to delete refresh token from SecureStore:', error);
    // Don't throw - allow app to continue
  }
}
