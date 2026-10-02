import { AskDocsAPI } from './api';
import { WidgetUI } from './ui';
import { WidgetConfig, Message, WidgetState, WidgetEventType, WidgetEventCallback } from './types';

export class AskDocsWidget {
  private config: WidgetConfig;
  private api: AskDocsAPI;
  private ui: WidgetUI;
  private state: WidgetState;
  private eventListeners: Map<string, WidgetEventCallback<any>[]> = new Map();

  constructor(config: WidgetConfig) {
    this.validateConfig(config);
    
    this.config = {
      apiUrl: 'http://localhost:8000',
      primaryColor: '#3B82F6',
      botName: 'AI Assistant',
      welcomeMessage: 'Hello! How can I help you today?',
      placeholder: 'Ask a question...',
      position: 'bottom-right',
      autoOpen: false,
      showBranding: true,
      debug: false,
      ...config,
    };

    this.state = {
      isOpen: false,
      isLoading: false,
      isConnected: false,
      messages: [],
    };

    this.api = new AskDocsAPI(
      this.config.apiUrl!,
      this.config.apiKey,
      this.config.debug
    );

    this.ui = new WidgetUI(this.config);
    
    this.initialize();
  }

  private validateConfig(config: WidgetConfig): void {
    if (!config.apiKey) {
      throw new Error('AskDocs Widget: apiKey is required');
    }

    if (config.apiKey && !config.apiKey.startsWith('ask_')) {
      console.warn('AskDocs Widget: API key should start with "ask_" prefix');
    }
  }

  private async initialize(): Promise<void> {
    try {
      // Test API connection
      await this.api.healthCheck();
      this.state.isConnected = true;
      
      // Generate conversation ID
      this.state.conversationId = this.config.conversationId || 
        this.api.generateConversationId();
      
      // Bind UI events
      this.bindUIEvents();
      
      // Auto-open if configured
      if (this.config.autoOpen) {
        this.open();
      }
      
      this.emit('widget:ready', { config: this.config });
      
      this.log('Widget initialized successfully');
    } catch (error) {
      this.log('Failed to initialize widget:', error);
      this.state.error = error instanceof Error ? error.message : 'Initialization failed';
      this.emit('error', { error: this.state.error, details: error });
    }
  }

  private bindUIEvents(): void {
    // Listen for message submissions from UI
    this.addEventListener('message:sent', async (data) => {
      await this.handleUserMessage(data.message);
    });

    // Listen for widget open/close events
    this.addEventListener('widget:open', () => {
      this.state.isOpen = true;
    });

    this.addEventListener('widget:close', () => {
      this.state.isOpen = false;
    });
  }

  private async handleUserMessage(message: Message): Promise<void> {
    try {
      this.state.isLoading = true;
      this.ui.setLoading(true);
      
      // Add user message to state
      this.state.messages.push(message);
      
      this.log('Sending query:', message.content);
      
      // Send query to API
      const response = await this.api.query({
        query: message.content,
        conversation_id: this.state.conversationId,
        enable_verification: true,
        metadata: this.config.metadata,
      });

      // Create bot response message
      const botMessage: Message = {
        id: this.generateMessageId(),
        type: 'bot',
        content: response.answer,
        timestamp: new Date(),
        citations: response.citations,
        confidence: response.confidence_score,
        requiresHandoff: response.requires_human_handoff,
      };

      // Add to state and UI
      this.state.messages.push(botMessage);
      this.ui.addMessage(botMessage);
      
      // Update conversation ID if provided
      if (response.conversation_id) {
        this.state.conversationId = response.conversation_id;
      }

      this.emit('message:received', { message: botMessage });
      
      this.log('Response received:', response);
      
    } catch (error) {
      this.log('Query failed:', error);
      
      const errorMessage: Message = {
        id: this.generateMessageId(),
        type: 'error',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
        timestamp: new Date(),
      };
      
      this.state.messages.push(errorMessage);
      this.ui.addMessage(errorMessage);
      
      this.emit('error', { 
        error: error instanceof Error ? error.message : 'Query failed',
        details: error 
      });
      
    } finally {
      this.state.isLoading = false;
      this.ui.setLoading(false);
    }
  }

  // Public API Methods
  public open(): void {
    this.ui.open();
  }

  public close(): void {
    this.ui.close();
  }

  public toggle(): void {
    this.ui.toggle();
  }

  public sendMessage(content: string): void {
    const message: Message = {
      id: this.generateMessageId(),
      type: 'user',
      content,
      timestamp: new Date(),
    };

    this.ui.addMessage(message);
    this.handleUserMessage(message);
  }

  public getState(): WidgetState {
    return { ...this.state };
  }

  public getMessages(): Message[] {
    return [...this.state.messages];
  }

  public clearMessages(): void {
    this.state.messages = [];
    // Note: UI doesn't support clearing messages yet - would need to re-render
    this.log('Messages cleared from state');
  }

  public updateConfig(newConfig: Partial<WidgetConfig>): void {
    this.config = { ...this.config, ...newConfig };
    
    // Update API if URL or key changed
    if (newConfig.apiUrl || newConfig.apiKey) {
      this.api = new AskDocsAPI(
        this.config.apiUrl!,
        this.config.apiKey,
        this.config.debug
      );
    }
    
    this.log('Config updated:', newConfig);
  }

  public destroy(): void {
    this.ui.destroy();
    this.eventListeners.clear();
    this.log('Widget destroyed');
  }

  // Event System
  public addEventListener<T extends WidgetEventType>(
    eventType: T,
    callback: WidgetEventCallback<T>
  ): void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, []);
    }
    this.eventListeners.get(eventType)!.push(callback);
  }

  public removeEventListener<T extends WidgetEventType>(
    eventType: T,
    callback: WidgetEventCallback<T>
  ): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  private emit<T extends WidgetEventType>(
    eventType: T,
    data: Parameters<WidgetEventCallback<T>>[0]
  ): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          this.log('Event listener error:', error);
        }
      });
    }
  }

  // Utility Methods
  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
  }

  private log(...args: any[]): void {
    if (this.config.debug) {
      console.log('[AskDocs Widget]', ...args);
    }
  }

  // Static factory method for easy initialization
  public static create(config: WidgetConfig): AskDocsWidget {
    return new AskDocsWidget(config);
  }
}