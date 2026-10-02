// API Response Types
export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
}

// Auth Types
export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  settings: TenantSettings;
  created_at: string;
  updated_at: string;
}

export interface TenantSettings {
  max_documents?: number;
  max_queries_per_month?: number;
  features?: string[];
}

export enum UserRole {
  OWNER = 'owner',
  ADMIN = 'admin',
  MEMBER = 'member',
  VIEWER = 'viewer'
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  tenant: Tenant;
}

// Document Types
export interface Document {
  id: string;
  tenant_id: string;
  name: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  status: DocumentStatus;
  upload_url?: string;
  error_message?: string;
  metadata: DocumentMetadata;
  created_at: string;
  updated_at: string;
}

export enum DocumentStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  ARCHIVED = 'archived'
}

export interface DocumentMetadata {
  page_count?: number;
  word_count?: number;
  language?: string;
  chunk_count?: number;
  processing_time?: number;
  source?: string;
}

export interface DocumentUploadRequest {
  file: File;
  name?: string;
  metadata?: Partial<DocumentMetadata>;
}

// Query Types
export interface QueryRequest {
  query: string;
  document_ids?: string[];
  enable_verification?: boolean;
  conversation_id?: string;
  max_chunks?: number;
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

// Analytics Types
export interface AnalyticsData {
  queries: QueryAnalytics;
  documents: DocumentAnalytics;
  usage: UsageAnalytics;
  performance: PerformanceAnalytics;
}

export interface QueryAnalytics {
  total_queries: number;
  successful_queries: number;
  average_confidence: number;
  human_handoff_rate: number;
  top_queries: Array<{
    query: string;
    count: number;
    avg_confidence: number;
  }>;
  queries_by_day: Array<{
    date: string;
    count: number;
  }>;
}

export interface DocumentAnalytics {
  total_documents: number;
  documents_by_status: Record<DocumentStatus, number>;
  total_chunks: number;
  most_cited_documents: Array<{
    document_id: string;
    document_name: string;
    citation_count: number;
  }>;
  upload_trends: Array<{
    date: string;
    count: number;
  }>;
}

export interface UsageAnalytics {
  storage_used: number;
  storage_limit: number;
  queries_this_month: number;
  queries_limit: number;
  api_calls: number;
  costs: {
    embedding_cost: number;
    llm_cost: number;
    storage_cost: number;
    total_cost: number;
  };
}

export interface PerformanceAnalytics {
  average_query_time: number;
  p95_query_time: number;
  error_rate: number;
  uptime_percentage: number;
  component_health: {
    database: 'healthy' | 'degraded' | 'down';
    vector_store: 'healthy' | 'degraded' | 'down';
    llm_service: 'healthy' | 'degraded' | 'down';
    background_jobs: 'healthy' | 'degraded' | 'down';
  };
}

// API Key Types
export interface ApiKey {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string;
  last_used_at?: string;
  expires_at?: string;
  is_active: boolean;
  permissions: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateApiKeyRequest {
  name: string;
  permissions: string[];
  expires_at?: string;
}

export interface CreateApiKeyResponse {
  api_key: ApiKey;
  secret_key: string; // Full key - only shown once
}

// Settings Types
export interface UserSettings {
  notifications: {
    email_notifications: boolean;
    document_processing: boolean;
    query_alerts: boolean;
    security_alerts: boolean;
  };
  preferences: {
    timezone: string;
    date_format: string;
    theme: 'light' | 'dark' | 'system';
  };
}

// Common Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface FilterOptions {
  search?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

// Error Types
export interface AppError {
  code: string;
  message: string;
  details?: any;
  timestamp: string;
}