'use client'

import { useEffect, useState } from 'react'
import { 
  DocumentTextIcon, 
  ChatBubbleLeftRightIcon, 
  ChartBarIcon,
  CloudArrowUpIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { formatNumber, getStatusBadgeColor, formatDate } from '@/lib/utils'
import { documentsApi, queryApi, analyticsApi } from '@/lib/api'

interface DashboardStats {
  documents: {
    total: number
    processing: number
    completed: number
    failed: number
  }
  queries: {
    today: number
    thisMonth: number
    averageConfidence: number
  }
  usage: {
    storageUsed: number
    queriesThisMonth: number
    queriesLimit: number
  }
}

interface RecentActivity {
  id: string
  type: 'document_upload' | 'query' | 'document_processed'
  title: string
  description: string
  timestamp: string
  status?: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      
      const [documentsData, queryData, analyticsData] = await Promise.all([
        documentsApi.getDocumentStats(),
        queryApi.getQueryStats(),
        analyticsApi.getAnalytics()
      ])

      setStats({
        documents: documentsData,
        queries: queryData,
        usage: analyticsData.usage
      })

      // Mock recent activity - replace with real API call
      setRecentActivity([
        {
          id: '1',
          type: 'document_upload',
          title: 'New document uploaded',
          description: 'company-policy.pdf',
          timestamp: new Date().toISOString(),
          status: 'completed'
        },
        {
          id: '2', 
          type: 'query',
          title: 'Question answered',
          description: 'What is our remote work policy?',
          timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString()
        },
        {
          id: '3',
          type: 'document_processed',
          title: 'Document processing completed',
          description: 'employee-handbook.docx',
          timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
          status: 'completed'
        }
      ])
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white overflow-hidden shadow rounded-lg animate-pulse">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="w-8 h-8 bg-gray-200 rounded"></div>
                  <div className="ml-5 w-0 flex-1">
                    <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                    <div className="h-6 bg-gray-200 rounded w-1/2"></div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const statsCards = [
    {
      name: 'Total Documents',
      value: stats?.documents.total || 0,
      icon: DocumentTextIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100'
    },
    {
      name: 'Queries Today', 
      value: stats?.queries.today || 0,
      icon: ChatBubbleLeftRightIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-100'
    },
    {
      name: 'Average Confidence',
      value: `${Math.round((stats?.queries.averageConfidence || 0) * 100)}%`,
      icon: ChartBarIcon,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100'
    },
    {
      name: 'Monthly Queries',
      value: `${stats?.usage.queriesThisMonth || 0}/${stats?.usage.queriesLimit || 1000}`,
      icon: CloudArrowUpIcon,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100'
    }
  ]

  const getActivityIcon = (type: string, status?: string) => {
    switch (type) {
      case 'document_upload':
        return <DocumentTextIcon className="h-6 w-6 text-blue-600" />
      case 'document_processed':
        return status === 'completed' 
          ? <CheckCircleIcon className="h-6 w-6 text-green-600" />
          : <ExclamationCircleIcon className="h-6 w-6 text-red-600" />
      case 'query':
        return <ChatBubbleLeftRightIcon className="h-6 w-6 text-green-600" />
      default:
        return <ClockIcon className="h-6 w-6 text-gray-600" />
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-sm text-gray-700">
          Welcome back! Here's what's happening with your documents and queries.
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {statsCards.map((card) => (
          <div key={card.name} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className={`flex-shrink-0 ${card.bgColor} p-2 rounded-lg`}>
                  <card.icon className={`h-6 w-6 ${card.color}`} aria-hidden="true" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      {card.name}
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {typeof card.value === 'number' ? formatNumber(card.value) : card.value}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Document Status */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Document Status</h3>
            <div className="space-y-3">
              {[
                { label: 'Completed', value: stats?.documents.completed || 0, color: 'text-green-600' },
                { label: 'Processing', value: stats?.documents.processing || 0, color: 'text-yellow-600' },
                { label: 'Failed', value: stats?.documents.failed || 0, color: 'text-red-600' }
              ].map((item) => (
                <div key={item.label} className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">{item.label}</span>
                  <span className={`text-sm font-medium ${item.color}`}>
                    {formatNumber(item.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start space-x-3">
                  <div className="flex-shrink-0">
                    {getActivityIcon(activity.type, activity.status)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      {activity.title}
                    </p>
                    <p className="text-sm text-gray-600 truncate">
                      {activity.description}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatDate(activity.timestamp)}
                    </p>
                  </div>
                  {activity.status && (
                    <div className={`px-2 py-1 text-xs rounded-full ${getStatusBadgeColor(activity.status)}`}>
                      {activity.status}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => window.location.href = '/dashboard/documents'}
              className="inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <DocumentTextIcon className="h-4 w-4 mr-2" />
              Upload Document
            </button>
            <button
              onClick={() => window.location.href = '/dashboard/chat'}
              className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <ChatBubbleLeftRightIcon className="h-4 w-4 mr-2" />
              Test Chat
            </button>
            <button
              onClick={() => window.location.href = '/dashboard/api-keys'}
              className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <ChartBarIcon className="h-4 w-4 mr-2" />
              View API Keys
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}