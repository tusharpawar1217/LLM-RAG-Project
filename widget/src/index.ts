import { AskDocsWidget } from './widget';
import { WidgetConfig } from './types';

// Export main classes and types for module usage
export { AskDocsWidget } from './widget';
export { AskDocsAPI } from './api';
export { WidgetUI } from './ui';
export * from './types';

// Global namespace for browser usage
declare global {
  interface Window {
    AskDocsWidget: typeof AskDocsWidget;
    askdocs?: {
      widget?: AskDocsWidget;
      config?: WidgetConfig;
    };
  }
}

// Attach to global window object for browser usage
if (typeof window !== 'undefined') {
  window.AskDocsWidget = AskDocsWidget;
  
  // Auto-initialization from global config
  window.addEventListener('DOMContentLoaded', () => {
    // Check for global configuration
    if (window.askdocs?.config) {
      try {
        const widget = new AskDocsWidget(window.askdocs.config);
        window.askdocs.widget = widget;
        console.log('[AskDocs] Widget auto-initialized from global config');
      } catch (error) {
        console.error('[AskDocs] Failed to auto-initialize widget:', error);
      }
    }
  });
}

// Export default for easier imports
export default AskDocsWidget;