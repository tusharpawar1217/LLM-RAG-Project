'use client'

import { useEffect, useState } from 'react'
import {
  CreditCardIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CloudArrowUpIcon,
  KeyIcon,
  UsersIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline'
import { formatCurrency, formatBytes, formatDate } from '@/lib/utils'

interface Plan {
  id: string
  name: string
  tier: string
  description?: string
  price_monthly: number
  price_yearly: number
  yearly_discount_percent?: number
  max_documents: number
  max_queries_per_month: number
  max_storage_mb: number
  max_api_keys: number
  max_team_members: number
  features: string[]
  is_popular: boolean
}

interface LimitCheck {
  current: number
  limit: number
  can_add: boolean
  usage_percent: number
}

interface BillingData {
  subscription: {
    plan_tier: string
    plan_name: string
    status: string
    billing_cycle: string
    current_period_end: string | null
    is_trial: boolean
    trial_end: string | null
  }
  usage: {
    queries_count: number
    documents_count: number
    storage_mb: number
    api_calls_count: number
    costs: {
      embedding_cost: number
      llm_cost: number
      storage_cost: number
      total_cost: number
    }
  }
  limits: {
    max_documents: number
    max_queries_per_month: number
    max_storage_mb: number
    max_api_keys: number
    max_team_members: number
  }
  limit_checks: {
    documents: LimitCheck
    queries: LimitCheck
    storage: LimitCheck
    api_keys: LimitCheck
    team_members: LimitCheck
  }
}

export default function BillingPage() {
  const [billingData, setBillingData] = useState<BillingData | null>(null)
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [upgrading, setUpgrading] = useState(false)

  useEffect(() => {
    loadBillingData()
    loadPlans()
  }, [])

  const loadBillingData = async () => {
    try {
      const response = await fetch('/api/v1/billing/subscription', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('askdocs_token')}`
        }
      })
      const data = await response.json()
      setBillingData(data)
    } catch (error) {
      console.error('Failed to load billing data:', error)
    }
  }

  const loadPlans = async () => {
    try {
      const response = await fetch('/api/v1/billing/plans')
      const data = await response.json()
      setPlans(data)
    } catch (error) {
      console.error('Failed to load plans:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (planTier: string, billingCycle: 'monthly' | 'yearly') => {
    setUpgrading(true)
    try {
      const response = await fetch('/api/v1/billing/checkout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('askdocs_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          plan_tier: planTier,
          billing_cycle: billingCycle,
          success_url: `${window.location.origin}/dashboard/billing?success=true`,
          cancel_url: `${window.location.origin}/dashboard/billing?canceled=true`
        })
      })
      
      const data = await response.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    } catch (error) {
      console.error('Failed to create checkout session:', error)
    } finally {
      setUpgrading(false)
    }
  }

  const openCustomerPortal = async () => {
    try {
      const response = await fetch('/api/v1/billing/customer-portal', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('askdocs_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          return_url: window.location.href
        })
      })
      
      const data = await response.json()
      if (data.portal_url) {
        window.open(data.portal_url, '_blank')
      }
    } catch (error) {
      console.error('Failed to open customer portal:', error)
    }
  }

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'text-red-600 bg-red-100'
    if (percentage >= 75) return 'text-yellow-600 bg-yellow-100'
    return 'text-green-600 bg-green-100'
  }

  const getUsageBarColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500'
    if (percentage >= 75) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
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

  const usageItems = billingData ? [
    {
      name: 'Documents',
      icon: DocumentTextIcon,
      current: billingData.limit_checks.documents.current,
      limit: billingData.limit_checks.documents.limit,
      usage_percent: billingData.limit_checks.documents.usage_percent,
      unit: 'documents'
    },
    {
      name: 'Queries',
      icon: ChatBubbleLeftRightIcon,
      current: billingData.limit_checks.queries.current,
      limit: billingData.limit_checks.queries.limit,
      usage_percent: billingData.limit_checks.queries.usage_percent,
      unit: 'this month'
    },
    {
      name: 'Storage',
      icon: CloudArrowUpIcon,
      current: billingData.limit_checks.storage.current,
      limit: billingData.limit_checks.storage.limit,
      usage_percent: billingData.limit_checks.storage.usage_percent,
      unit: 'MB',
      formatter: (value: number) => formatBytes(value * 1024 * 1024)
    },
    {
      name: 'API Keys',
      icon: KeyIcon,
      current: billingData.limit_checks.api_keys.current,
      limit: billingData.limit_checks.api_keys.limit,
      usage_percent: billingData.limit_checks.api_keys.usage_percent,
      unit: 'keys'
    },
    {
      name: 'Team Members',
      icon: UsersIcon,
      current: billingData.limit_checks.team_members.current,
      limit: billingData.limit_checks.team_members.limit,
      usage_percent: billingData.limit_checks.team_members.usage_percent,
      unit: 'members'
    }
  ] : []

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Billing & Usage</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage your subscription, view usage, and upgrade your plan.
          </p>
        </div>
        {billingData?.subscription.plan_tier !== 'free' && (
          <button
            onClick={openCustomerPortal}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
          >
            <CreditCardIcon className="h-4 w-4 mr-2" />
            Manage Billing
          </button>
        )}
      </div>

      {/* Current Plan */}
      {billingData && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Current Plan</h3>
            <div className="sm:flex sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center space-x-3">
                  <h4 className="text-xl font-semibold text-gray-900">
                    {billingData.subscription.plan_name}
                  </h4>
                  {billingData.subscription.is_trial && (
                    <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
                      Trial
                    </span>
                  )}
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    billingData.subscription.status === 'active' 
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {billingData.subscription.status}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mt-1">
                  {billingData.subscription.billing_cycle === 'yearly' ? 'Yearly' : 'Monthly'} billing
                  {billingData.subscription.current_period_end && (
                    <span> • Renews {formatDate(billingData.subscription.current_period_end)}</span>
                  )}
                </p>
                {billingData.subscription.is_trial && billingData.subscription.trial_end && (
                  <p className="text-sm text-yellow-600 mt-1">
                    Trial ends {formatDate(billingData.subscription.trial_end)}
                  </p>
                )}
              </div>
              {billingData.subscription.plan_tier === 'free' && (
                <div className="mt-4 sm:mt-0">
                  <button
                    onClick={() => handleUpgrade('starter', 'monthly')}
                    disabled={upgrading}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                  >
                    Upgrade Plan
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Usage Overview */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Usage Overview</h3>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {usageItems.map((item) => (
              <div key={item.name} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <item.icon className="h-5 w-5 text-gray-400" />
                    <span className="text-sm font-medium text-gray-700">{item.name}</span>
                  </div>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${getUsageColor(item.usage_percent)}`}>
                    {Math.round(item.usage_percent)}%
                  </span>
                </div>
                
                <div className="mt-2">
                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-semibold text-gray-900">
                      {item.formatter ? item.formatter(item.current) : item.current.toLocaleString()}
                    </span>
                    <span className="text-sm text-gray-500">
                      / {item.formatter ? item.formatter(item.limit) : item.limit.toLocaleString()} {item.unit}
                    </span>
                  </div>
                  
                  <div className="mt-2 bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${getUsageBarColor(item.usage_percent)}`}
                      style={{ width: `${Math.min(item.usage_percent, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Cost Breakdown */}
      {billingData && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Cost Breakdown (This Month)</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="text-center">
                <div className="text-2xl font-semibold text-gray-900">
                  {formatCurrency(billingData.usage.costs.llm_cost)}
                </div>
                <div className="text-sm text-gray-600">LLM Costs</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-semibold text-gray-900">
                  {formatCurrency(billingData.usage.costs.embedding_cost)}
                </div>
                <div className="text-sm text-gray-600">Embeddings</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-semibold text-gray-900">
                  {formatCurrency(billingData.usage.costs.storage_cost)}
                </div>
                <div className="text-sm text-gray-600">Storage</div>
              </div>
              <div className="text-center border-l border-gray-200 pl-4">
                <div className="text-3xl font-semibold text-primary-600">
                  {formatCurrency(billingData.usage.costs.total_cost)}
                </div>
                <div className="text-sm text-gray-600">Total</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Available Plans */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Available Plans</h3>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`relative border rounded-lg p-6 ${
                  plan.is_popular 
                    ? 'border-primary-500 bg-primary-50' 
                    : 'border-gray-200'
                }`}
              >
                {plan.is_popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <span className="bg-primary-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                      Popular
                    </span>
                  </div>
                )}
                
                <div className="text-center">
                  <h4 className="text-xl font-semibold text-gray-900">{plan.name}</h4>
                  {plan.description && (
                    <p className="text-sm text-gray-600 mt-2">{plan.description}</p>
                  )}
                  
                  <div className="mt-4">
                    <span className="text-4xl font-bold text-gray-900">
                      {formatCurrency(plan.price_monthly)}
                    </span>
                    <span className="text-gray-600">/month</span>
                    
                    {plan.yearly_discount_percent && plan.price_yearly > 0 && (
                      <div className="mt-2">
                        <span className="text-lg text-gray-700">
                          {formatCurrency(plan.price_yearly)}/year
                        </span>
                        <span className="ml-2 text-sm text-green-600 font-medium">
                          Save {Math.round(plan.yearly_discount_percent)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <ul className="mt-6 space-y-2">
                  {plan.features.slice(0, 5).map((feature, index) => (
                    <li key={index} className="flex items-center space-x-2 text-sm">
                      <CheckCircleIcon className="h-4 w-4 text-green-500" />
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                  {plan.features.length > 5 && (
                    <li className="text-sm text-gray-500">
                      +{plan.features.length - 5} more features
                    </li>
                  )}
                </ul>

                <div className="mt-6 space-y-2">
                  {billingData?.subscription.plan_tier !== plan.tier && (
                    <>
                      <button
                        onClick={() => handleUpgrade(plan.tier, 'monthly')}
                        disabled={upgrading}
                        className="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                      >
                        {plan.price_monthly === 0 ? 'Downgrade' : 'Upgrade'} - Monthly
                      </button>
                      {plan.price_yearly > 0 && (
                        <button
                          onClick={() => handleUpgrade(plan.tier, 'yearly')}
                          disabled={upgrading}
                          className="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                        >
                          {plan.price_yearly === 0 ? 'Downgrade' : 'Upgrade'} - Yearly
                        </button>
                      )}
                    </>
                  )}
                  
                  {billingData?.subscription.plan_tier === plan.tier && (
                    <div className="w-full inline-flex justify-center items-center px-4 py-2 border border-green-300 text-sm font-medium rounded-md text-green-700 bg-green-50">
                      <CheckCircleIcon className="h-4 w-4 mr-2" />
                      Current Plan
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}