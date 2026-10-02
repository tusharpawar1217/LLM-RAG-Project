import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { toast } from 'react-hot-toast'

// API Base Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => {
        return response
      },
      (error) => {
        if (error.response?.status === 401) {
          this.handleAuthError()
        } else if (error.response?.status >= 500) {
          toast.error('Server error. Please try again later.')
        } else if (error.code === 'ECONNABORTED') {
          toast.error('Request timeout. Please try again.')
        }
        
        return Promise.reject(error)
      }
    )

    // Load token from localStorage on initialization
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('askdocs_token')
    }
  }

  private handleAuthError() {
    this.token = null
    if (typeof window !== 'undefined') {
      localStorage.removeItem('askdocs_token')
      localStorage.removeItem('askdocs_user')
      // Redirect to login page
      window.location.href = '/login'
    }
  }

  setToken(token: string) {
    this.token = token
    if (typeof window !== 'undefined') {
      localStorage.setItem('askdocs_token', token)
    }
  }

  clearToken() {
    this.token = null
    if (typeof window !== 'undefined') {
      localStorage.removeItem('askdocs_token')
      localStorage.removeItem('askdocs_user')
    }
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.client.get(url, config)
    return response.data
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.client.post(url, data, config)
    return response.data
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.client.put(url, data, config)
    return response.data
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.client.patch(url, data, config)
    return response.data
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.client.delete(url, config)
    return response.data
  }

  // File upload with progress
  async uploadFile<T = any>(
    url: string,
    file: File,
    onProgress?: (progress: number) => void,
    additionalData?: Record<string, any>
  ): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (additionalData) {
      Object.keys(additionalData).forEach(key => {
        formData.append(key, additionalData[key])
      })
    }

    const response: AxiosResponse<T> = await this.client.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      },
    })
    
    return response.data
  }
}

// Create singleton instance
export const apiClient = new ApiClient()

// Export specific API functions
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/auth/login', { email, password }),
    
  register: (userData: any) =>
    apiClient.post('/auth/register', userData),
    
  logout: () =>
    apiClient.post('/auth/logout'),
    
  refreshToken: () =>
    apiClient.post('/auth/refresh'),
    
  getProfile: () =>
    apiClient.get('/auth/me'),
    
  updateProfile: (data: any) =>
    apiClient.patch('/auth/me', data),
}

export const documentsApi = {
  getDocuments: (params?: any) =>
    apiClient.get('/documents/', { params }),
    
  getDocument: (id: string) =>
    apiClient.get(`/documents/${id}`),
    
  uploadDocument: (file: File, onProgress?: (progress: number) => void, metadata?: any) =>
    apiClient.uploadFile('/documents/upload', file, onProgress, metadata),
    
  deleteDocument: (id: string) =>
    apiClient.delete(`/documents/${id}`),
    
  reprocessDocument: (id: string) =>
    apiClient.post(`/documents/${id}/reprocess`),
    
  getDocumentStats: () =>
    apiClient.get('/documents/stats'),
}

export const queryApi = {
  askQuestion: (data: any) =>
    apiClient.post('/query/', data),
    
  getSuggestions: () =>
    apiClient.get('/query/suggestions'),
    
  getQueryStats: () =>
    apiClient.get('/query/stats/retrieval'),
    
  getHealth: () =>
    apiClient.get('/query/health'),
}

export const analyticsApi = {
  getAnalytics: (params?: any) =>
    apiClient.get('/analytics/', { params }),
    
  getQueryAnalytics: (params?: any) =>
    apiClient.get('/analytics/queries', { params }),
    
  getDocumentAnalytics: (params?: any) =>
    apiClient.get('/analytics/documents', { params }),
    
  getUsageAnalytics: (params?: any) =>
    apiClient.get('/analytics/usage', { params }),
}

export const apiKeysApi = {
  getApiKeys: () =>
    apiClient.get('/api-keys/'),
    
  createApiKey: (data: any) =>
    apiClient.post('/api-keys/', data),
    
  deleteApiKey: (id: string) =>
    apiClient.delete(`/api-keys/${id}`),
    
  updateApiKey: (id: string, data: any) =>
    apiClient.patch(`/api-keys/${id}`, data),
}

export const tenantsApi = {
  getTenant: () =>
    apiClient.get('/tenants/current'),
    
  updateTenant: (data: any) =>
    apiClient.patch('/tenants/current', data),
    
  getUsers: () =>
    apiClient.get('/tenants/users'),
    
  inviteUser: (data: any) =>
    apiClient.post('/tenants/users/invite', data),
    
  updateUser: (userId: string, data: any) =>
    apiClient.patch(`/tenants/users/${userId}`, data),
    
  removeUser: (userId: string) =>
    apiClient.delete(`/tenants/users/${userId}`),
}

export default apiClient