import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User, Tenant, LoginResponse } from '@/types'
import { authApi, apiClient } from '@/lib/api'
import { toast } from 'react-hot-toast'

interface AuthState {
  user: User | null
  tenant: Tenant | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  register: (userData: any) => Promise<boolean>
  updateProfile: (data: any) => Promise<boolean>
  checkAuth: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      tenant: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const response: LoginResponse = await authApi.login(email, password)
          
          // Store token
          apiClient.setToken(response.access_token)
          
          // Update state
          set({
            user: response.user,
            tenant: response.tenant,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
          
          toast.success('Login successful!')
          return true
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Login failed'
          set({
            isLoading: false,
            error: errorMessage,
            isAuthenticated: false,
          })
          toast.error(errorMessage)
          return false
        }
      },

      logout: () => {
        // Clear token
        apiClient.clearToken()
        
        // Clear state
        set({
          user: null,
          tenant: null,
          isAuthenticated: false,
          error: null,
        })
        
        // Call logout API (don't wait for response)
        authApi.logout().catch(() => {})
        
        toast.success('Logged out successfully')
      },

      register: async (userData: any) => {
        set({ isLoading: true, error: null })
        
        try {
          const response: LoginResponse = await authApi.register(userData)
          
          // Store token
          apiClient.setToken(response.access_token)
          
          // Update state
          set({
            user: response.user,
            tenant: response.tenant,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
          
          toast.success('Registration successful!')
          return true
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Registration failed'
          set({
            isLoading: false,
            error: errorMessage,
          })
          toast.error(errorMessage)
          return false
        }
      },

      updateProfile: async (data: any) => {
        set({ isLoading: true, error: null })
        
        try {
          const updatedUser: User = await authApi.updateProfile(data)
          
          set({
            user: updatedUser,
            isLoading: false,
            error: null,
          })
          
          toast.success('Profile updated successfully!')
          return true
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Profile update failed'
          set({
            isLoading: false,
            error: errorMessage,
          })
          toast.error(errorMessage)
          return false
        }
      },

      checkAuth: async () => {
        // Only check if we have a token
        if (typeof window === 'undefined') return
        
        const token = localStorage.getItem('askdocs_token')
        if (!token) {
          set({ isAuthenticated: false })
          return
        }

        set({ isLoading: true })
        
        try {
          const user: User = await authApi.getProfile()
          
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch (error) {
          // Token is invalid
          apiClient.clearToken()
          set({
            user: null,
            tenant: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          })
        }
      },

      clearError: () => {
        set({ error: null })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)