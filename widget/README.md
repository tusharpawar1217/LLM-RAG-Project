# 💬 AskDocs Chat Widget

A lightweight, customizable, embeddable JavaScript chat widget for websites that connects to the AskDocs RAG API to provide AI-powered customer support with document-based answers and citations.

## ✨ Features

- **🚀 Easy Integration** - Single script tag, zero dependencies
- **🎨 Fully Customizable** - Colors, branding, positioning, messages
- **📱 Responsive Design** - Works perfectly on desktop and mobile
- **🔒 Secure** - API key authentication with proper error handling
- **⚡ Real-time Chat** - Instant responses with loading states
- **📚 Citations** - Shows source documents with confidence scores
- **🎯 Event System** - Listen to widget events for analytics/integration
- **🔧 Programmatic API** - Control the widget via JavaScript
- **🌐 Cross-Domain** - Works on any website with CORS support

## 🚀 Quick Start

### 1. Include the Widget Script

```html
<script src="https://cdn.askdocs.ai/widget/v1/askdocs-widget.js"></script>
```

### 2. Initialize the Widget

```javascript
const widget = new AskDocsWidget({
  apiKey: 'your_api_key_here',
  apiUrl: 'https://api.askdocs.ai',
  botName: 'Support Bot',
  primaryColor: '#3b82f6',
  position: 'bottom-right'
});
```

### 3. That's It! 🎉

The widget will appear on your page and users can start asking questions about your documents.

## ⚙️ Configuration Options

```typescript
interface WidgetConfig {
  // Required
  apiKey: string;                    // Your AskDocs API key
  
  // API Configuration
  apiUrl?: string;                   // Default: 'https://api.askdocs.ai'
  
  // Appearance
  primaryColor?: string;             // Default: '#3B82F6'
  botName?: string;                  // Default: 'AI Assistant'
  welcomeMessage?: string;           // Default: auto-generated
  placeholder?: string;              // Default: 'Ask a question...'
  
  // Positioning
  position?: 'bottom-right' |        // Default: 'bottom-right'
             'bottom-left' | 
             'top-right' | 
             'top-left';
  
  // Behavior
  autoOpen?: boolean;                // Default: false
  showBranding?: boolean;            // Default: true
  
  // Advanced
  conversationId?: string;           // For session persistence
  metadata?: Record<string, any>;    // Additional data to send with queries
  debug?: boolean;                   // Default: false
}
```

## 🎨 Customization Examples

### Custom Branding

```javascript
const widget = new AskDocsWidget({
  apiKey: 'your_api_key',
  botName: 'DocBot',
  primaryColor: '#ff6b6b',
  welcomeMessage: 'Hi! I can help you find information in our docs.',
  placeholder: 'What would you like to know?',
  showBranding: false
});
```

### Multiple Positions

```javascript
// Bottom right (default)
const widget1 = new AskDocsWidget({
  apiKey: 'your_api_key',
  position: 'bottom-right'
});

// Bottom left
const widget2 = new AskDocsWidget({
  apiKey: 'your_api_key',
  position: 'bottom-left'
});
```

### Auto-open on Page Load

```javascript
const widget = new AskDocsWidget({
  apiKey: 'your_api_key',
  autoOpen: true
});
```

## 🔧 Programmatic API

### Basic Control

```javascript
// Open/close the widget
widget.open();
widget.close();
widget.toggle();

// Send messages programmatically
widget.sendMessage('What are your office hours?');

// Get widget state
const state = widget.getState();
const messages = widget.getMessages();

// Clear conversation
widget.clearMessages();

// Update configuration
widget.updateConfig({
  primaryColor: '#00ff00',
  botName: 'New Bot Name'
});

// Cleanup
widget.destroy();
```

### Event Listeners

```javascript
// Widget lifecycle events
widget.addEventListener('widget:ready', (data) => {
  console.log('Widget is ready!', data.config);
});

widget.addEventListener('widget:open', () => {
  console.log('Widget opened');
  // Track analytics event
});

widget.addEventListener('widget:close', () => {
  console.log('Widget closed');
});

// Message events
widget.addEventListener('message:sent', (data) => {
  console.log('User sent:', data.message.content);
  // Track user questions
});

widget.addEventListener('message:received', (data) => {
  console.log('Bot replied:', data.message.content);
  console.log('Confidence:', data.message.confidence);
  console.log('Citations:', data.message.citations);
});

// Error handling
widget.addEventListener('error', (data) => {
  console.error('Widget error:', data.error);
  // Show fallback contact info
});

// Conversation events
widget.addEventListener('conversation:start', (data) => {
  console.log('New conversation:', data.conversationId);
});
```

## 🔒 Security & Authentication

### API Key Authentication

```javascript
const widget = new AskDocsWidget({
  apiKey: 'ask_1234567890abcdef', // Your API key from AskDocs dashboard
  // ... other config
});
```

### Scoped API Keys

For security, create widget-specific API keys with limited permissions:

```bash
# In your AskDocs dashboard, create an API key with only 'query' permission
# This prevents the widget from accessing admin functions
```

### CORS Configuration

Ensure your API server allows requests from your domain:

```javascript
// Backend CORS configuration should include your website domain
const allowedOrigins = [
  'https://yourwebsite.com',
  'https://www.yourwebsite.com'
];
```

## 📱 Responsive Design

The widget automatically adapts to different screen sizes:

- **Desktop**: Fixed size (400x600px) positioned as configured
- **Mobile**: Full-width with responsive height
- **Tablet**: Optimized touch interactions

### Custom CSS Overrides

```html
<style>
/* Override widget styles if needed */
.askdocs-widget-container {
  /* Your custom styles */
}

/* Mobile customizations */
@media (max-width: 768px) {
  .askdocs-widget {
    /* Mobile-specific styles */
  }
}
</style>
```

## 🔧 Development

### Prerequisites
- Node.js 16+
- npm or yarn

### Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/askdocs.git
cd askdocs/widget

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint
```

### Development Server

The development server includes:
- **Hot reloading** for instant updates
- **Demo page** at http://localhost:3001/demo.html
- **Source maps** for debugging

### Build Output

```bash
npm run build
```

Generates:
- `dist/askdocs-widget.js` - Production bundle
- `dist/askdocs-widget.js.map` - Source map (dev only)
- `dist/demo.html` - Demo page

### Testing

```javascript
// Use demo API key for testing
const widget = new AskDocsWidget({
  apiKey: 'demo_key_123',
  apiUrl: 'http://localhost:8000', // Local development API
  debug: true // Enable console logging
});
```

## 🚀 Deployment

### CDN Hosting

Upload the built widget to your CDN:

```html
<script src="https://your-cdn.com/askdocs-widget.js"></script>
```

### Self-Hosting

1. Build the widget: `npm run build`
2. Copy `dist/askdocs-widget.js` to your web server
3. Include it in your HTML

### Version Management

```html
<!-- Always get the latest version -->
<script src="https://cdn.askdocs.ai/widget/latest/askdocs-widget.js"></script>

<!-- Pin to specific version -->
<script src="https://cdn.askdocs.ai/widget/v1.2.3/askdocs-widget.js"></script>
```

## 🔍 Troubleshooting

### Common Issues

**Widget doesn't appear**
- Check API key is valid
- Verify API URL is correct
- Check browser console for errors
- Ensure CORS is configured properly

**Messages not sending**
- Verify API key has 'query' permission
- Check network requests in browser dev tools
- Enable debug mode: `debug: true`

**Styling conflicts**
- Widget uses isolated CSS classes
- Override with more specific selectors if needed
- Check for z-index conflicts

**Mobile issues**
- Widget automatically adapts to mobile
- Ensure viewport meta tag is present
- Test on actual devices, not just browser dev tools

### Debug Mode

```javascript
const widget = new AskDocsWidget({
  apiKey: 'your_api_key',
  debug: true // Enables console logging
});
```

### Browser Compatibility

- **Modern Browsers**: Chrome 70+, Firefox 65+, Safari 12+, Edge 79+
- **Mobile**: iOS Safari 12+, Chrome Mobile 70+
- **Features Used**: Fetch API, CSS Grid, ES2020 features

## 📊 Analytics Integration

### Google Analytics

```javascript
widget.addEventListener('message:sent', (data) => {
  gtag('event', 'widget_message_sent', {
    message_length: data.message.content.length
  });
});

widget.addEventListener('message:received', (data) => {
  gtag('event', 'widget_message_received', {
    confidence: data.message.confidence,
    has_citations: data.message.citations?.length > 0
  });
});
```

### Custom Analytics

```javascript
widget.addEventListener('widget:open', () => {
  // Track widget engagement
  analytics.track('Widget Opened');
});

widget.addEventListener('message:received', (data) => {
  // Track successful responses
  analytics.track('Answer Provided', {
    confidence: data.message.confidence,
    citation_count: data.message.citations?.length || 0
  });
});
```

## 🔄 Migration Guide

### From v1.0 to v1.1

```javascript
// Old way
const widget = new AskDocsWidget('your_api_key');

// New way (v1.1+)
const widget = new AskDocsWidget({
  apiKey: 'your_api_key'
});
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Run linting: `npm run lint`
6. Submit a pull request

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details.

---

<div align="center">

**Need help?** Check out the [AskDocs Documentation](https://docs.askdocs.ai) or [open an issue](https://github.com/your-repo/askdocs/issues).

</div>