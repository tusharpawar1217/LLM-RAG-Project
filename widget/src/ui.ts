import { WidgetConfig, Message, Citation } from './types';

export class WidgetUI {
  private container: HTMLElement;
  private config: WidgetConfig;
  private isOpen: boolean = false;
  private messageContainer: HTMLElement;
  private inputContainer: HTMLElement;
  private toggleButton: HTMLElement;

  constructor(config: WidgetConfig) {
    this.config = config;
    this.container = this.createContainer();
    this.render();
    this.bindEvents();
  }

  private createContainer(): HTMLElement {
    const container = document.createElement('div');
    container.id = 'askdocs-widget';
    container.className = 'askdocs-widget-container';
    
    // Add to document
    document.body.appendChild(container);
    
    return container;
  }

  private render(): void {
    const position = this.config.position || 'bottom-right';
    const primaryColor = this.config.primaryColor || '#3B82F6';
    
    this.container.innerHTML = `
      <!-- Widget Styles -->
      <style>
        .askdocs-widget-container {
          position: fixed;
          z-index: 2147483647;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 14px;
          line-height: 1.5;
        }
        
        .askdocs-widget-container * {
          box-sizing: border-box;
        }
        
        /* Position variants */
        .askdocs-position-bottom-right {
          bottom: 20px;
          right: 20px;
        }
        
        .askdocs-position-bottom-left {
          bottom: 20px;
          left: 20px;
        }
        
        .askdocs-position-top-right {
          top: 20px;
          right: 20px;
        }
        
        .askdocs-position-top-left {
          top: 20px;
          left: 20px;
        }
        
        /* Toggle Button */
        .askdocs-toggle {
          width: 60px;
          height: 60px;
          border-radius: 50%;
          background-color: ${primaryColor};
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          transition: all 0.3s ease;
        }
        
        .askdocs-toggle:hover {
          transform: scale(1.05);
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
        }
        
        .askdocs-toggle-icon {
          width: 24px;
          height: 24px;
          fill: white;
        }
        
        /* Widget Window */
        .askdocs-widget {
          width: 400px;
          height: 600px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
          display: none;
          flex-direction: column;
          overflow: hidden;
          margin-bottom: 80px;
        }
        
        .askdocs-widget.open {
          display: flex;
        }
        
        /* Widget Header */
        .askdocs-header {
          background-color: ${primaryColor};
          color: white;
          padding: 16px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        
        .askdocs-header-title {
          font-weight: 600;
          font-size: 16px;
        }
        
        .askdocs-close {
          background: none;
          border: none;
          color: white;
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
        }
        
        .askdocs-close:hover {
          background-color: rgba(255, 255, 255, 0.1);
        }
        
        /* Messages */
        .askdocs-messages {
          flex: 1;
          padding: 20px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
          background-color: #f9fafb;
        }
        
        .askdocs-message {
          display: flex;
          align-items: flex-start;
          gap: 8px;
        }
        
        .askdocs-message.user {
          flex-direction: row-reverse;
        }
        
        .askdocs-message-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 600;
          flex-shrink: 0;
        }
        
        .askdocs-message.user .askdocs-message-avatar {
          background-color: ${primaryColor};
          color: white;
        }
        
        .askdocs-message.bot .askdocs-message-avatar {
          background-color: #6b7280;
          color: white;
        }
        
        .askdocs-message-content {
          max-width: 80%;
          padding: 12px 16px;
          border-radius: 12px;
          position: relative;
        }
        
        .askdocs-message.user .askdocs-message-content {
          background-color: ${primaryColor};
          color: white;
        }
        
        .askdocs-message.bot .askdocs-message-content {
          background-color: white;
          border: 1px solid #e5e7eb;
        }
        
        .askdocs-message-text {
          margin: 0;
          white-space: pre-wrap;
        }
        
        .askdocs-message-meta {
          font-size: 11px;
          opacity: 0.7;
          margin-top: 4px;
        }
        
        /* Citations */
        .askdocs-citations {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #e5e7eb;
        }
        
        .askdocs-citations-title {
          font-size: 11px;
          font-weight: 600;
          color: #6b7280;
          margin-bottom: 8px;
        }
        
        .askdocs-citation {
          background-color: #f3f4f6;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          padding: 8px;
          margin-bottom: 4px;
          font-size: 11px;
        }
        
        .askdocs-citation-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 4px;
        }
        
        .askdocs-citation-doc {
          font-weight: 600;
          color: #374151;
        }
        
        .askdocs-citation-confidence {
          background-color: #10b981;
          color: white;
          padding: 1px 6px;
          border-radius: 10px;
          font-size: 10px;
        }
        
        .askdocs-citation-content {
          color: #6b7280;
          line-height: 1.4;
        }
        
        /* Input Area */
        .askdocs-input {
          padding: 20px;
          border-top: 1px solid #e5e7eb;
          background: white;
        }
        
        .askdocs-input-form {
          display: flex;
          gap: 8px;
          align-items: flex-end;
        }
        
        .askdocs-input-field {
          flex: 1;
          border: 1px solid #e5e7eb;
          border-radius: 20px;
          padding: 10px 16px;
          resize: none;
          outline: none;
          font-family: inherit;
          font-size: 14px;
          max-height: 100px;
        }
        
        .askdocs-input-field:focus {
          border-color: ${primaryColor};
        }
        
        .askdocs-send {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background-color: ${primaryColor};
          border: none;
          color: white;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: opacity 0.2s;
        }
        
        .askdocs-send:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .askdocs-send:not(:disabled):hover {
          opacity: 0.9;
        }
        
        /* Loading State */
        .askdocs-loading {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #6b7280;
          font-style: italic;
        }
        
        .askdocs-loading-dots {
          display: inline-flex;
          gap: 2px;
        }
        
        .askdocs-loading-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background-color: #6b7280;
          animation: askdocs-pulse 1.4s infinite ease-in-out both;
        }
        
        .askdocs-loading-dot:nth-child(1) { animation-delay: -0.32s; }
        .askdocs-loading-dot:nth-child(2) { animation-delay: -0.16s; }
        .askdocs-loading-dot:nth-child(3) { animation-delay: 0s; }
        
        @keyframes askdocs-pulse {
          0%, 80%, 100% { 
            opacity: 0.3;
            transform: scale(0.8);
          }
          40% { 
            opacity: 1;
            transform: scale(1);
          }
        }
        
        /* Branding */
        .askdocs-branding {
          text-align: center;
          padding: 8px;
          background-color: #f9fafb;
          border-top: 1px solid #e5e7eb;
          font-size: 11px;
          color: #6b7280;
        }
        
        .askdocs-branding a {
          color: ${primaryColor};
          text-decoration: none;
        }
        
        /* Responsive */
        @media (max-width: 480px) {
          .askdocs-widget {
            width: calc(100vw - 40px);
            height: calc(100vh - 100px);
          }
        }
      </style>
      
      <!-- Toggle Button -->
      <div class="askdocs-position-${position}">
        <button class="askdocs-toggle" id="askdocs-toggle">
          <svg class="askdocs-toggle-icon" viewBox="0 0 24 24">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
          </svg>
        </button>
        
        <!-- Widget Window -->
        <div class="askdocs-widget" id="askdocs-widget">
          <!-- Header -->
          <div class="askdocs-header">
            <div class="askdocs-header-title">${this.config.botName || 'AI Assistant'}</div>
            <button class="askdocs-close" id="askdocs-close">✕</button>
          </div>
          
          <!-- Messages -->
          <div class="askdocs-messages" id="askdocs-messages">
            ${this.renderWelcomeMessage()}
          </div>
          
          <!-- Input -->
          <div class="askdocs-input">
            <form class="askdocs-input-form" id="askdocs-form">
              <textarea 
                class="askdocs-input-field" 
                id="askdocs-input" 
                placeholder="${this.config.placeholder || 'Ask a question...'}"
                rows="1"
              ></textarea>
              <button type="submit" class="askdocs-send" id="askdocs-send">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </button>
            </form>
          </div>
          
          ${this.config.showBranding !== false ? `
          <div class="askdocs-branding">
            Powered by <a href="https://askdocs.ai" target="_blank">AskDocs</a>
          </div>
          ` : ''}
        </div>
      </div>
    `;

    // Cache DOM elements
    this.toggleButton = this.container.querySelector('#askdocs-toggle')!;
    this.messageContainer = this.container.querySelector('#askdocs-messages')!;
    this.inputContainer = this.container.querySelector('#askdocs-form')!;
  }

  private renderWelcomeMessage(): string {
    const welcomeMessage = this.config.welcomeMessage || 
      `Hello! I'm ${this.config.botName || 'your AI assistant'}. How can I help you today?`;
    
    return `
      <div class="askdocs-message bot">
        <div class="askdocs-message-avatar">🤖</div>
        <div class="askdocs-message-content">
          <p class="askdocs-message-text">${welcomeMessage}</p>
        </div>
      </div>
    `;
  }

  private bindEvents(): void {
    // Toggle button
    this.toggleButton.addEventListener('click', () => {
      this.toggle();
    });

    // Close button
    const closeButton = this.container.querySelector('#askdocs-close');
    closeButton?.addEventListener('click', () => {
      this.close();
    });

    // Form submission
    this.inputContainer.addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleSubmit();
    });

    // Auto-resize textarea
    const input = this.container.querySelector('#askdocs-input') as HTMLTextAreaElement;
    input?.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    });

    // Enter to send (Shift+Enter for new line)
    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSubmit();
      }
    });
  }

  private handleSubmit(): void {
    const input = this.container.querySelector('#askdocs-input') as HTMLTextAreaElement;
    const message = input.value.trim();
    
    if (!message) return;

    // Create user message
    const userMessage: Message = {
      id: this.generateMessageId(),
      type: 'user',
      content: message,
      timestamp: new Date(),
    };

    // Add to UI and clear input
    this.addMessage(userMessage);
    input.value = '';
    input.style.height = 'auto';

    // Emit event
    this.emit('message:sent', { message: userMessage });
  }

  public open(): void {
    const widget = this.container.querySelector('#askdocs-widget');
    widget?.classList.add('open');
    this.isOpen = true;
    this.emit('widget:open', {});
  }

  public close(): void {
    const widget = this.container.querySelector('#askdocs-widget');
    widget?.classList.remove('open');
    this.isOpen = false;
    this.emit('widget:close', {});
  }

  public toggle(): void {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  public addMessage(message: Message): void {
    const messageElement = this.createMessageElement(message);
    this.messageContainer.appendChild(messageElement);
    this.scrollToBottom();
  }

  public setLoading(loading: boolean): void {
    const sendButton = this.container.querySelector('#askdocs-send') as HTMLButtonElement;
    const input = this.container.querySelector('#askdocs-input') as HTMLTextAreaElement;
    
    if (loading) {
      sendButton.disabled = true;
      input.disabled = true;
      this.addLoadingMessage();
    } else {
      sendButton.disabled = false;
      input.disabled = false;
      this.removeLoadingMessage();
    }
  }

  private createMessageElement(message: Message): HTMLElement {
    const messageEl = document.createElement('div');
    messageEl.className = `askdocs-message ${message.type}`;
    messageEl.innerHTML = `
      <div class="askdocs-message-avatar">
        ${message.type === 'user' ? '👤' : '🤖'}
      </div>
      <div class="askdocs-message-content">
        <p class="askdocs-message-text">${this.escapeHtml(message.content)}</p>
        ${this.renderMessageMeta(message)}
        ${this.renderCitations(message.citations)}
      </div>
    `;
    return messageEl;
  }

  private renderMessageMeta(message: Message): string {
    const meta = [];
    
    if (message.confidence !== undefined) {
      meta.push(`${Math.round(message.confidence * 100)}% confidence`);
    }
    
    if (message.requiresHandoff) {
      meta.push('May need human help');
    }

    return meta.length > 0 ? `<div class="askdocs-message-meta">${meta.join(' • ')}</div>` : '';
  }

  private renderCitations(citations?: Citation[]): string {
    if (!citations || citations.length === 0) return '';
    
    const citationsList = citations.map(citation => `
      <div class="askdocs-citation">
        <div class="askdocs-citation-header">
          <div class="askdocs-citation-doc">${this.escapeHtml(citation.document_name)}</div>
          <div class="askdocs-citation-confidence">${Math.round(citation.confidence_score * 100)}%</div>
        </div>
        <div class="askdocs-citation-content">
          "${this.escapeHtml(citation.content.substring(0, 150))}${citation.content.length > 150 ? '...' : ''}"
        </div>
      </div>
    `).join('');

    return `
      <div class="askdocs-citations">
        <div class="askdocs-citations-title">Sources:</div>
        ${citationsList}
      </div>
    `;
  }

  private addLoadingMessage(): void {
    const loadingEl = document.createElement('div');
    loadingEl.className = 'askdocs-message bot';
    loadingEl.id = 'askdocs-loading-message';
    loadingEl.innerHTML = `
      <div class="askdocs-message-avatar">🤖</div>
      <div class="askdocs-message-content">
        <div class="askdocs-loading">
          <span>Thinking</span>
          <div class="askdocs-loading-dots">
            <div class="askdocs-loading-dot"></div>
            <div class="askdocs-loading-dot"></div>
            <div class="askdocs-loading-dot"></div>
          </div>
        </div>
      </div>
    `;
    this.messageContainer.appendChild(loadingEl);
    this.scrollToBottom();
  }

  private removeLoadingMessage(): void {
    const loadingEl = this.container.querySelector('#askdocs-loading-message');
    loadingEl?.remove();
  }

  private scrollToBottom(): void {
    this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
  }

  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
  }

  private emit(eventType: string, data: any): void {
    // For now, just log events - can be enhanced with proper event system
    if (this.config.debug) {
      console.log(`[AskDocs Widget] Event: ${eventType}`, data);
    }
  }

  public destroy(): void {
    this.container.remove();
  }
}