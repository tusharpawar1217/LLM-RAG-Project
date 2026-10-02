import { QueryRequest, QueryResponse, ErrorResponse } from './types';

export class AskDocsAPI {
  private apiUrl: string;
  private apiKey: string;
  private debug: boolean;

  constructor(apiUrl: string, apiKey: string, debug: boolean = false) {
    this.apiUrl = apiUrl.replace(/\/$/, ''); // Remove trailing slash
    this.apiKey = apiKey;
    this.debug = debug;
  }

  private log(...args: any[]): void {
    if (this.debug) {
      console.log('[AskDocs Widget]', ...args);
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.apiUrl}/api/v1${endpoint}`;
    
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
        ...options.headers,
      },
    };

    const requestOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    this.log('Making request to:', url, requestOptions);

    try {
      const response = await fetch(url, requestOptions);
      const data = await response.json();

      if (!response.ok) {
        const error: ErrorResponse = data;
        throw new Error(error.detail || error.error || `HTTP ${response.status}`);
      }

      this.log('Response received:', data);
      return data as T;
    } catch (error) {
      this.log('Request failed:', error);
      throw error;
    }
  }

  async query(request: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>('/query/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health');
  }

  // Create a new conversation ID for session tracking
  generateConversationId(): string {
    return `widget_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
  }

  // Stream-enabled query (for future implementation)
  async *queryStream(request: QueryRequest): AsyncGenerator<Partial<QueryResponse>, QueryResponse, unknown> {
    // For now, just return the full response
    // In the future, this could use Server-Sent Events or WebSocket
    const response = await this.query(request);
    yield response;
    return response;
  }
}