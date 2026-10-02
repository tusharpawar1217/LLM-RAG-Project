# AskDocs Frontend Dashboard

A modern, responsive React/Next.js dashboard for managing documents, testing queries, and monitoring analytics in the AskDocs RAG platform.

## 🚀 Features

### 🏠 **Dashboard Overview**
- Real-time statistics and KPIs
- Recent activity feed
- Document status monitoring
- Quick action buttons

### 📄 **Document Management**
- Drag & drop file upload with progress tracking
- Support for PDF, DOC, DOCX, TXT, MD files
- Real-time processing status updates
- Search and filter capabilities
- Document reprocessing and deletion

### 💬 **Interactive Chat Interface**
- Real-time question answering
- Citation display with verification status
- Confidence scoring visualization
- Human handoff detection
- Chat history and conversation management

### 📊 **Analytics Dashboard**
- Query performance metrics
- Document usage statistics
- Cost tracking and billing insights
- Top queries and citation analytics
- Performance monitoring

### 🔐 **Authentication & Security**
- JWT-based authentication
- Role-based access control
- Secure token management
- Auto-logout on expiration

## 🛠️ Tech Stack

- **Frontend Framework**: Next.js 15 with App Router
- **Language**: TypeScript for type safety
- **Styling**: Tailwind CSS with custom design system
- **Icons**: Heroicons React
- **UI Components**: Headless UI for accessible components
- **State Management**: Zustand for lightweight state management
- **Forms**: React Hook Form with validation
- **File Uploads**: React Dropzone with progress tracking
- **Notifications**: React Hot Toast for user feedback
- **HTTP Client**: Axios with interceptors and error handling

## 🏗️ Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── dashboard/         # Dashboard pages
│   │   ├── analytics/     # Analytics dashboard
│   │   ├── chat/         # Chat interface
│   │   ├── documents/    # Document management
│   │   └── layout.tsx    # Dashboard layout wrapper
│   ├── login/            # Authentication pages
│   ├── globals.css       # Global styles
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Home/redirect page
├── components/           # Reusable components
│   └── layout/          # Layout components (Sidebar, Header)
├── lib/                 # Utility libraries
│   ├── api.ts          # API client and endpoints
│   └── utils.ts        # Helper functions and utilities
├── stores/             # State management
│   └── auth.ts         # Authentication store
└── types/              # TypeScript type definitions
    └── index.ts        # All application types
```

## 🔧 Configuration

### Environment Variables
Create a `.env.local` file:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# App Configuration  
NEXT_PUBLIC_APP_NAME="AskDocs"
NEXT_PUBLIC_APP_VERSION="1.0.0"
```

### API Integration
The frontend communicates with the backend via:

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentication**: Bearer token (JWT)
- **Auto-retry**: Failed requests with exponential backoff
- **Error Handling**: Global error interceptors with user-friendly messages

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ and npm
- AskDocs backend running on port 8000

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server  
npm start
```

### Development Workflow

1. **Login Flow**: Start at `/login` → authenticate → redirect to `/dashboard`
2. **Document Upload**: Navigate to Documents → drag/drop files → monitor processing
3. **Test Queries**: Use Chat interface → ask questions → review citations
4. **Monitor Performance**: Check Analytics for usage stats and insights

## 📱 Responsive Design

The dashboard is fully responsive with:

- **Mobile-first**: Optimized for mobile devices
- **Tablet Support**: Collapsible sidebar and touch-friendly interface
- **Desktop**: Full-featured layout with keyboard shortcuts
- **Accessibility**: WCAG 2.1 AA compliant with screen reader support

## 🔒 Security Features

### Authentication
- JWT token storage in localStorage
- Automatic token refresh
- Secure logout with token cleanup
- Route protection for authenticated pages

### API Security
- CSRF protection via SameSite cookies
- Request/response interceptors for token management
- Automatic logout on 401 responses
- Rate limiting awareness with retry logic

### Data Validation
- Client-side form validation
- Type-safe API responses
- Input sanitization for XSS prevention
- File upload security (type/size validation)

## 🎨 Design System

### Colors
- **Primary**: Blue (#3B82F6) for actions and navigation
- **Success**: Green (#10B981) for success states
- **Warning**: Yellow (#F59E0B) for warnings and low confidence
- **Error**: Red (#EF4444) for errors and failures
- **Neutral**: Gray scale for text and backgrounds

### Typography
- **Font**: Inter for clean, modern typography
- **Scale**: Tailwind's default type scale
- **Weights**: Regular (400), Medium (500), Semibold (600)

### Components
- **Cards**: White backgrounds with subtle shadows
- **Buttons**: Consistent sizing and hover states
- **Forms**: Clear validation and error states
- **Tables**: Responsive with mobile-friendly layouts

## 📊 Performance Optimizations

### Code Splitting
- Automatic route-based code splitting via Next.js
- Dynamic imports for heavy components
- Lazy loading for images and large content

### Caching
- API response caching with stale-while-revalidate
- Static asset caching via Next.js
- Browser caching for fonts and images

### Bundle Size
- Tree shaking for unused code elimination
- Optimized dependencies (no unnecessary libraries)
- Compressed production builds

## 🧪 Development Features

### Developer Experience
- **Hot Reloading**: Instant updates during development
- **TypeScript**: Full type safety and IntelliSense
- **ESLint**: Code quality and consistency checking
- **Prettier**: Automatic code formatting

### Debugging
- **React DevTools**: Component inspection
- **Network Tab**: API request monitoring  
- **Console Logging**: Structured error logging
- **Source Maps**: Original source debugging in production

## 🚀 Production Deployment

### Build Process
```bash
# Build optimized production bundle
npm run build

# Start production server
npm start
```

### Deployment Options
- **Vercel**: One-click deployment with Next.js optimization
- **Netlify**: Static site deployment with serverless functions
- **Docker**: Containerized deployment for any platform
- **Traditional Hosting**: Static file deployment to any web server

### Performance Monitoring
- **Core Web Vitals**: Automatic performance tracking
- **Error Tracking**: Integration ready for Sentry/LogRocket
- **Analytics**: Google Analytics/Plausible integration ready

## 🔄 API Integration

### Endpoints Used
- `POST /auth/login` - User authentication
- `GET /documents/` - List documents with filtering
- `POST /documents/upload` - File upload with progress
- `DELETE /documents/{id}` - Document deletion
- `POST /query/` - Ask questions and get answers
- `GET /analytics/` - Usage and performance analytics

### Error Handling
- **Network Errors**: Retry with exponential backoff
- **Auth Errors**: Automatic logout and redirect
- **Validation Errors**: Display field-specific messages
- **Server Errors**: User-friendly error messages

## 📈 Future Enhancements

### Planned Features
- **Real-time Updates**: WebSocket support for live document processing
- **Advanced Analytics**: Custom date ranges and detailed metrics
- **User Management**: Team member invitation and role management  
- **API Key Management**: Generate and manage API keys for integrations
- **Settings Page**: Tenant configuration and preferences
- **Dark Mode**: Toggle between light and dark themes

### Technical Improvements  
- **PWA Support**: Offline functionality and app-like experience
- **Internationalization**: Multi-language support
- **Advanced Caching**: React Query for server state management
- **Component Library**: Storybook for component documentation
- **E2E Testing**: Playwright tests for critical user flows

## 🐛 Troubleshooting

### Common Issues

**"Failed to load documents"**
- Check backend server is running on port 8000
- Verify authentication token is valid
- Check browser console for network errors

**"Upload failed"** 
- Ensure file is supported format (PDF, DOC, DOCX, TXT, MD)
- Check file size is under 50MB limit
- Verify backend has sufficient storage space

**"Chat not responding"**
- Confirm documents are uploaded and processed
- Check if questions match document content
- Verify LLM service is configured in backend

### Development Issues

**"Module not found"**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**"Build failed"**
```bash
# Check TypeScript errors
npm run type-check

# Check for ESLint issues  
npm run lint
```

## 🤝 Contributing

1. Follow the existing code style and conventions
2. Add TypeScript types for all new features
3. Test on mobile and desktop breakpoints
4. Update this README for significant changes
5. Ensure all forms have proper validation

## 📄 License

This project is part of the AskDocs RAG platform. See the main project license for details.