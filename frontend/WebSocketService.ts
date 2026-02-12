import { API_BASE_URL } from './api';

interface WebSocketMessage {
  action?: string;
  room?: string;
  content?: string;
  message_type?: string;
  invoice_description?: string;
  invoice_gift_price?: number;
  invoice_service_fee?: number;
  invoice_delivery_fee?: number;
  invoice_total?: number;
}

interface WebSocketEvent {
  event: string;
  room: string;
  data: any;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000; // Start with 1 second
  private token: string | null = null;
  private eventListeners: { [event: string]: ((data: any) => void)[] } = {};

  connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    if (!API_BASE_URL) {
      console.error('Cannot connect to WebSocket: API_BASE_URL is undefined');
      return;
    }

    this.token = token;
    let wsUrl = API_BASE_URL;
    if (wsUrl.startsWith('https://')) {
      wsUrl = wsUrl.replace('https://', 'wss://');
    } else if (wsUrl.startsWith('http://')) {
      wsUrl = wsUrl.replace('http://', 'ws://');
    }
    wsUrl = `${wsUrl}/ws?token=${encodeURIComponent(token)}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectInterval = 1000;
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketEvent = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        this.handleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.handleReconnect();
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.token = null;
    this.reconnectAttempts = 0;
  }

  private handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts || !this.token) {
      console.log('Max reconnect attempts reached or no token');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${this.reconnectInterval}ms`);

    setTimeout(() => {
      if (this.token) {
        this.connect(this.token);
      }
    }, this.reconnectInterval);

    // Exponential backoff
    this.reconnectInterval = Math.min(this.reconnectInterval * 2, 30000);
  }

  private handleMessage(message: WebSocketEvent) {
    console.log('Received WebSocket message:', message);

    // Handle room join/leave confirmations
    if (message.action === 'joined_room') {
      console.log(`Joined room: ${message.room}`);
      return;
    }

    if (message.action === 'left_room') {
      console.log(`Left room: ${message.room}`);
      return;
    }

    // Emit event to listeners
    const listeners = this.eventListeners[message.event];
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(message);
        } catch (error) {
          console.error('Error in WebSocket event listener:', error);
        }
      });
    }
  }

  sendMessage(message: WebSocketMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  joinRoom(room: string) {
    this.sendMessage({ action: 'join_room', room });
  }

  leaveRoom(room: string) {
    this.sendMessage({ action: 'leave_room', room });
  }

  sendChatMessage(room: string, content: string, messageType: string = 'text', invoiceData?: any) {
    const message: WebSocketMessage = {
      action: 'send_message',
      room,
      content,
      message_type: messageType,
      ...invoiceData
    };
    this.sendMessage(message);
  }

  on(event: string, callback: (data: any) => void) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  off(event: string, callback?: (data: any) => void) {
    if (!this.eventListeners[event]) return;

    if (callback) {
      const index = this.eventListeners[event].indexOf(callback);
      if (index > -1) {
        this.eventListeners[event].splice(index, 1);
      }
    } else {
      delete this.eventListeners[event];
    }
  }

  // Convenience methods for specific events
  onOrderStatusChange(callback: (data: any) => void) {
    this.on('order_status_change', callback);
  }

  onChatMessage(callback: (data: any) => void) {
    this.on('chat_message', callback);
  }

  onInvoiceCreated(callback: (data: any) => void) {
    this.on('invoice_created', callback);
  }
}

export const webSocketService = new WebSocketService();