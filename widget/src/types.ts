// Widget Configuration Types
export interface WidgetConfig {
  apiKey: string;
  apiUrl?: string;
  
  // Appearance
  primaryColor?: string;
  botName?: string;
  welcomeMessage?: string;
  placeholder?: string;
  
  // Behavior
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
  autoOpen?: boolean;
  showBranding?: boolean;
  
  // Advanced
  conversationId?: string;
  metadata?: Record<string, any>;
  debug?: boolean;
}

// API Types
export interface QueryRequest {
  query: string;
  conversation_id?: string;
  enable_verification?: boolean;
  metadata?: Record<string, any>;
}

export interface QueryResponse {
  query: string;
  answer: string;
  citations: Citation[];
  confidence_score: number;
  processing_time: number;
  has_sufficient_context: boolean;
  requires_human_handoff: boolean;
  conversation_id?: string;
  status: 'success' | 'error' | 'partial';
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content: string;
  page_number?: number;
  confidence_score: number;
  verified: boolean;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
  type?: string;
}

// Widget Internal Types
export interface Message {
  id: string;
  type: 'user' | 'bot' | 'error' | 'system';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  confidence?: number;
  requiresHandoff?: boolean;
  isStreaming?: boolean;
}

export interface WidgetState {
  isOpen: boolean;
  isLoading: boolean;
  isConnected: boolean;
  messages: Message[];
  conversationId?: string;
  error?: string;
}

// Event Types
export interface WidgetEventMap {
  'widget:ready': { config: WidgetConfig };
  'widget:open': {};
  'widget:close': {};
  'message:sent': { message: Message };
  'message:received': { message: Message };
  'error': { error: string; details?: any };
  'conversation:start': { conversationId: string };
}

export type WidgetEventType = keyof WidgetEventMap;
export type WidgetEventCallback<T extends WidgetEventType> = (data: WidgetEventMap[T]) => void;