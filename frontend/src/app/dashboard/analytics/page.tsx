'use client'

import { useEffect, useState } from 'react'
import {
  ChartBarIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'
import { AnalyticsData } from '@/types'
import { analyticsApi } from '@/lib/api'
import { formatNumber, formatCurrency } from '@/lib/utils'

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState<'7d' | '30d' | '90d'>('30d')

  useEffect(() => {
    loadAnalytics()
  }, [timeframe])

  const loadAnalytics = async () => {
    try {
      setLoading(true)
      const data = await analyticsApi.getAnalytics({ timeframe })
      setAnalytics(data)
    } catch (error) {
      console.error('Failed to load analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
                  <div className="h-8 bg-gray-200 rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const queryStats = [
    {
      name: 'Total Queries',
      value: formatNumber(analytics?.queries.total_queries || 0),
      icon: ChatBubbleLeftRightIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100'
    },
    {
      name: 'Success Rate',
      value: `${Math.round(((analytics?.queries.successful_queries || 0) / Math.max(analytics?.queries.total_queries || 1, 1)) * 100)}%`,
      icon: CheckCircleIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-100'
    },
    {
      name: 'Avg Confidence',
      value: `${Math.round((analytics?.queries.average_confidence || 0) * 100)}%`,
      icon: ChartBarIcon,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100'
    },
    {
      name: 'Human Handoff Rate',
      value: `${Math.round((analytics?.queries.human_handoff_rate || 0) * 100)}%`,
      icon: ExclamationCircleIcon,
      color: 'text-red-600',
      bgColor: 'bg-red-100'
    }
  ]

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Analytics</h1>
          <p className="mt-2 text-sm text-gray-700">
            Insights into your document usage and query performance.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value as '7d' | '30d' | '90d')}
            className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Query statistics */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {queryStats.map((stat) => (
          <div key={stat.name} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className={`flex-shrink-0 ${stat.bgColor} p-2 rounded-lg`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      {stat.name}
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {stat.value}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Document Analytics */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Document Performance</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Total Documents</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatNumber(analytics?.documents.total_documents || 0)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Total Chunks</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatNumber(analytics?.documents.total_chunks || 0)}
                </span>
              </div>
              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Most Cited Documents</h4>
                <div className="space-y-2">
                  {analytics?.documents.most_cited_documents?.slice(0, 5).map((doc, index) => (
                    <div key={doc.document_id} className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 truncate flex-1">
                        {index + 1}. {doc.document_name}
                      </span>
                      <span className="text-sm font-medium text-gray-900 ml-2">
                        {doc.citation_count}
                      </span>
                    </div>
                  )) || (
                    <p className="text-sm text-gray-500">No citation data available</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Usage & Costs */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Usage & Costs</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Storage Used</span>
                <span className="text-sm font-medium text-gray-900">
                  {analytics?.usage.storage_used ? 
                    `${Math.round(analytics.usage.storage_used / 1024 / 1024)} MB` : 
                    '0 MB'
                  }
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Queries This Month</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatNumber(analytics?.usage.queries_this_month || 0)} / {formatNumber(analytics?.usage.queries_limit || 0)}
                </span>
              </div>
              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Monthly Costs</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">LLM</span>
                    <span className="text-xs text-gray-700">
                      {formatCurrency(analytics?.usage.costs?.llm_cost || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Embeddings</span>
                    <span className="text-xs text-gray-700">
                      {formatCurrency(analytics?.usage.costs?.embedding_cost || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Storage</span>
                    <span className="text-xs text-gray-700">
                      {formatCurrency(analytics?.usage.costs?.storage_cost || 0)}
                    </span>
                  </div>
                  <div className="pt-2 border-t border-gray-100 flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-900">Total</span>
                    <span className="text-sm font-medium text-gray-900">
                      {formatCurrency(analytics?.usage.costs?.total_cost || 0)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Performance Metrics</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900">
                {analytics?.performance.average_query_time ? 
                  `${Math.round(analytics.performance.average_query_time * 1000)}ms` : 
                  'N/A'
                }
              </div>
              <div className="text-sm text-gray-600">Avg Query Time</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900">
                {analytics?.performance.p95_query_time ? 
                  `${Math.round(analytics.performance.p95_query_time * 1000)}ms` : 
                  'N/A'
                }
              </div>
              <div className="text-sm text-gray-600">P95 Query Time</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900">
                {analytics?.performance.error_rate ? 
                  `${Math.round(analytics.performance.error_rate * 100)}%` : 
                  '0%'
                }
              </div>
              <div className="text-sm text-gray-600">Error Rate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900">
                {analytics?.performance.uptime_percentage ? 
                  `${Math.round(analytics.performance.uptime_percentage * 100)}%` : 
                  '100%'
                }
              </div>
              <div className="text-sm text-gray-600">Uptime</div>
            </div>
          </div>
        </div>
      </div>

      {/* Top Queries */}
      {analytics?.queries.top_queries && analytics.queries.top_queries.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Top Queries</h3>
            <div className="space-y-3">
              {analytics.queries.top_queries.slice(0, 10).map((query, index) => (
                <div key={index} className="flex justify-between items-center py-2">
                  <div className="flex-1">
                    <div className="text-sm text-gray-900 truncate">
                      {query.query}
                    </div>
                    <div className="text-xs text-gray-500">
                      Avg confidence: {Math.round(query.avg_confidence * 100)}%
                    </div>
                  </div>
                  <div className="text-sm font-medium text-gray-600 ml-4">
                    {query.count} times
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}