import * as Keychain from 'react-native-keychain';

const SERVICE = 'giftly';

export async function getRefreshToken(): Promise<string | null> {
  const credentials = await Keychain.getGenericPassword({ service: SERVICE });
  return credentials?.password || null;
}

export async function saveRefreshToken(token: string): Promise<void> {
  await Keychain.setGenericPassword('refresh', token, { service: SERVICE });
}

export async function deleteRefreshToken(): Promise<void> {
  await Keychain.resetGenericPassword({ service: SERVICE });
}