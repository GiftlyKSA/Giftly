export const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://giftly-backend-tfjada.cranl.net';

export interface SendOTPRequest {
  phone_number: string;
}

export interface OTPVerifyRequest {
  phone_number: string;
  otp: string;
  email?: string;
  name?: string;
  date_of_birth?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  needs_profile: boolean;
}

export const sendOTP = async (phoneNumber: string): Promise<{message: string, otp: string}> => {
  console.log('API_BASE_URL:', API_BASE_URL);
  console.log('Sending POST to:', `${API_BASE_URL}/auth/send-otp`);
  console.log('Body:', JSON.stringify({ phone_number: phoneNumber }));

  const response = await fetch(`${API_BASE_URL}/auth/send-otp`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phone_number: phoneNumber }),
  });

  console.log('Response status:', response.status);
  console.log('Response ok:', response.ok);

  const responseClone = response.clone();
  const fullResponseText = await responseClone.text();
  console.log('Full response body:', fullResponseText);

  if (!response.ok) {
    let errorMessage = 'Failed to send OTP';
    try {
      const responseText = await response.text();
      console.log('Error response text:', responseText);
      const error = JSON.parse(responseText);
      console.log('Error response JSON:', error);
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      console.log('Error parsing response:', e);
      errorMessage = response.statusText || errorMessage;
    }
    console.log('Throwing error:', errorMessage);
    throw new Error(errorMessage);
  }

  const result = await response.json();
  console.log('Success response:', result);
  return result;
};

export interface CreateOrderRequest {
  description?: string;
  city_id: number;
  delivery_date: string; // ISO string
}

export interface OrderResponse {
  id: number;
  order_id: string;
  created_by_user_id: number;
  assigned_to_user_id: number | null;
  description: string | null;
  creation_date: string;
  delivery_date: string | null;
  status: string;
  comments: string | null;
  updated_at: string;
  city_id: number;
  invoice?: InvoiceResponse | null;
}

export const createOrder = async (token: string, data: CreateOrderRequest): Promise<OrderResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to create order';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getUserOrders = async (token: string): Promise<OrderResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/orders/`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch orders';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getOrder = async (token: string, orderId: string): Promise<OrderResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch order';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface CancelOrderRequest {
  reason: string;
}

export const cancelOrder = async (token: string, orderId: string, data: CancelOrderRequest): Promise<OrderResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/cancel`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to cancel order';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const verifyOTP = async (data: OTPVerifyRequest): Promise<TokenResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/verify-otp`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to verify OTP';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      // If response doesn't have JSON body, use status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface UserDetails {
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

export const getUserDetails = async (token: string): Promise<UserDetails> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch user details';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface UpdateUserDetails {
  name?: string;
  email?: string;
  date_of_birth?: string;
}

export const updateUserDetails = async (token: string, data: UpdateUserDetails): Promise<UserDetails> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      if (error.detail && typeof error.detail === 'object') {
        // Field-specific errors
        throw error.detail;
      } else {
        // Generic error
        throw new Error(error.detail || 'Failed to update user details');
      }
    } catch (parseError) {
      throw new Error(response.statusText || 'Failed to update user details');
    }
  }

  return response.json();
};

export const refreshAccessToken = async (refreshToken: string): Promise<TokenResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to refresh token';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const logout = async (token: string): Promise<{message: string}> => {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to logout';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface InvoiceResponse {
  id: number;
  invoice_id: string;
  order_id: number;
  full_amount: number;
  service_fee: number;
  order_only_price: number;
  courier_fee: number;
  status: string;
  description: string | null;
  comment: string | null;
  sent_to_user_via_email: boolean;
  sent_at: string | null;
  due_date: string | null;
  tax_amount: number;
  discount_amount: number;
  created_at: string;
  updated_at: string;
}

export const getInvoiceByOrder = async (token: string, orderId: number): Promise<InvoiceResponse> => {
  const response = await fetch(`${API_BASE_URL}/invoices/order/${orderId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch invoice';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getInvoice = async (token: string, invoiceId: string): Promise<InvoiceResponse> => {
  const response = await fetch(`${API_BASE_URL}/invoices/${invoiceId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch invoice';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const downloadInvoicePDF = async (token: string, invoiceId: number): Promise<Blob> => {
  const response = await fetch(`${API_BASE_URL}/invoices/id/${invoiceId}/pdf`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to download PDF';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.blob();
};

export interface CompleteProfileRequest {
  phone_number: string;
  name: string;
  email: string;
  date_of_birth: string;
  role?: string;
  national_id?: string;
  passport_id?: string;
}

export const completeProfile = async (data: CompleteProfileRequest): Promise<TokenResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/complete-profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to complete profile';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

// Chat API functions
export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_id: number;
  content: string;
  sent_at: string;
  message_type: string;
  invoice_description?: string;
  invoice_gift_price?: number;
  invoice_service_fee?: number;
  invoice_delivery_fee?: number;
  invoice_total?: number;
}

export interface Conversation {
  id: number;
  customer_id: number;
  courier_id: number | null;
  order_id: number;
  status: string;
  created_at: string;
}

export interface SendMessageRequest {
  content: string;
  message_type?: string;
  invoice_description?: string;
  invoice_gift_price?: number;
  invoice_service_fee?: number;
  invoice_delivery_fee?: number;
  invoice_total?: number;
}

export const getConversationMessages = async (token: string, conversationId: number, skip: number = 0, limit: number = 50): Promise<ChatMessage[]> => {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}/messages?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch messages';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const sendMessage = async (token: string, conversationId: number, message: SendMessageRequest): Promise<ChatMessage> => {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to send message';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getUserConversations = async (token: string): Promise<Conversation[]> => {
  const response = await fetch(`${API_BASE_URL}/chat/conversations`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch conversations';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const createOrGetConversation = async (token: string, otherUserId: number): Promise<Conversation> => {
  const response = await fetch(`${API_BASE_URL}/chat/conversations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ other_user_id: otherUserId }),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to create conversation';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getConversationByOrder = async (token: string, orderId: number): Promise<Conversation> => {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/by-order/${orderId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch conversation';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getCities = async (): Promise<CityResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/cities/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch cities';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface WalletResponse {
  id: number;
  user_id: number;
  balance: number;
  created_at: string;
  updated_at: string;
}

export const getWallet = async (token: string): Promise<WalletResponse> => {
  const response = await fetch(`${API_BASE_URL}/wallets/my-wallet`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch wallet';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface WalletPaymentResponse {
  message: string;
  payment_id: number;
  remaining_balance: number;
}

export const payWithWallet = async (token: string, invoiceId: number, couponCode?: string): Promise<WalletPaymentResponse> => {
  const response = await fetch(`${API_BASE_URL}/payments/pay-with-wallet/${invoiceId}?coupon_code=${couponCode || ''}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to process wallet payment';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface ChargeWalletRequest {
  amount: number;
}

export interface ChargeWalletResponse {
  message: string;
  new_balance: number;
}

export const chargeWallet = async (token: string, amount: number): Promise<ChargeWalletResponse> => {
  const response = await fetch(`${API_BASE_URL}/wallets/charge-wallet`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ amount }),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to charge wallet';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface RequestDepositRequest {
  amount: number;
}

export interface RequestDepositResponse {
  message: string;
  requested_amount: number;
  current_balance: number;
}

export const requestWalletDeposit = async (token: string, amount: number): Promise<RequestDepositResponse> => {
  const response = await fetch(`${API_BASE_URL}/wallets/request-deposit`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ amount }),
  });

  if (!response.ok) {
    let errorMessage = 'Failed to request deposit';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

// Courier-specific API functions
export const getAvailableOrdersForCourier = async (token: string): Promise<OrderResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/orders/courier/available`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch available orders';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const acceptOrder = async (token: string, orderId: string): Promise<OrderResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/accept`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to accept order';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getCourierActiveOrders = async (token: string): Promise<OrderResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/orders/courier/active`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch active orders';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const getCourierAllOrders = async (token: string): Promise<OrderResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/orders/courier/all`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch courier orders';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export const completeOrder = async (token: string, orderId: string): Promise<OrderResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/complete`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to complete order';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface CourierStatsResponse {
  active_orders_count: number;
  todays_earnings: number; // in cents/halaym
}

export const getCourierStats = async (token: string): Promise<CourierStatsResponse> => {
  const response = await fetch(`${API_BASE_URL}/orders/courier/stats`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = 'Failed to fetch courier stats';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch (e) {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json();
};

export interface CreateInvoiceRequest {
  order_id: number;
  description?: string;
  full_amount: number;
  service_fee: number;
  order_only_price: number;
  courier_fee: number;
  tax_amount?: number;
  discount_amount?: number;
  due_date?: string;
  comment?: string;
}

export const createInvoice = async (token: string, invoiceData: CreateInvoiceRequest): Promise<InvoiceResponse> => {
  console.log('createInvoice: Sending data:', invoiceData);

  const response = await fetch(`${API_BASE_URL}/invoices/courier/create`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(invoiceData),
  });

  console.log('createInvoice: Response status:', response.status);
  console.log('createInvoice: Response ok:', response.ok);

  if (!response.ok) {
    let errorMessage = 'Failed to create invoice';
    try {
      const responseText = await response.text();
      console.log('createInvoice: Error response text:', responseText);

      const error = JSON.parse(responseText);
      console.log('createInvoice: Parsed error:', error);

      // Handle different error formats
      if (error.detail) {
        if (Array.isArray(error.detail)) {
          // Handle array of errors
          errorMessage = error.detail.map((err: any) => {
            if (typeof err === 'string') return err;
            if (err.msg) return err.msg;
            if (err.message) return err.message;
            return JSON.stringify(err);
          }).join(', ');
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail;
        } else if (typeof error.detail === 'object') {
          // Handle object with field-specific errors
          const fieldErrors = Object.entries(error.detail).map(([field, messages]) => {
            if (Array.isArray(messages)) {
              return `${field}: ${messages.join(', ')}`;
            }
            return `${field}: ${messages}`;
          });
          errorMessage = fieldErrors.join('; ');
        }
      } else if (error.message) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
    } catch (parseError) {
      console.log('createInvoice: Error parsing response:', parseError);
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  console.log('createInvoice: Success result:', result);
  return result;
};

export const updateInvoice = async (token: string, invoiceId: string, invoiceData: CreateInvoiceRequest): Promise<InvoiceResponse> => {
  console.log('updateInvoice: Sending data:', invoiceData);

  const response = await fetch(`${API_BASE_URL}/invoices/courier/update/${invoiceId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(invoiceData),
  });

  console.log('updateInvoice: Response status:', response.status);
  console.log('updateInvoice: Response ok:', response.ok);

  if (!response.ok) {
    let errorMessage = 'Failed to update invoice';
    try {
      const responseText = await response.text();
      console.log('updateInvoice: Error response text:', responseText);

      const error = JSON.parse(responseText);
      console.log('updateInvoice: Parsed error:', error);

      // Handle different error formats
      if (error.detail) {
        if (Array.isArray(error.detail)) {
          // Handle array of errors
          errorMessage = error.detail.map((err: any) => {
            if (typeof err === 'string') return err;
            if (err.msg) return err.msg;
            if (err.message) return err.message;
            return JSON.stringify(err);
          }).join(', ');
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail;
        } else if (typeof error.detail === 'object') {
          // Handle object with field-specific errors
          const fieldErrors = Object.entries(error.detail).map(([field, messages]) => {
            if (Array.isArray(messages)) {
              return `${field}: ${messages.join(', ')}`;
            }
            return `${field}: ${messages}`;
          });
          errorMessage = fieldErrors.join('; ');
        }
      } else if (error.message) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
    } catch (parseError) {
      console.log('updateInvoice: Error parsing response:', parseError);
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  console.log('updateInvoice: Success result:', result);
  return result;
};
