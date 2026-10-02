'use client'

import { useState, useRef, useEffect } from 'react'
import {
  PaperAirplaneIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  UserIcon,
  ComputerDesktopIcon
} from '@heroicons/react/24/outline'
import { toast } from 'react-hot-toast'
import { QueryRequest, QueryResponse, Citation } from '@/types'
import { queryApi } from '@/lib/api'
import { getConfidenceBadgeColor, formatDate } from '@/lib/utils'

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  citations?: Citation[]
  confidence?: number
  requiresHandoff?: boolean
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [enableVerification, setEnableVerification] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async (question: string) => {
    if (!question.trim() || loading) return

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: question.trim(),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const request: QueryRequest = {
        query: question.trim(),
        enable_verification: enableVerification
      }

      const response: QueryResponse = await queryApi.askQuestion(request)

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        citations: response.citations,
        confidence: response.confidence_score,
        requiresHandoff: response.requires_human_handoff
      }

      setMessages(prev => [...prev, assistantMessage])

      if (response.requires_human_handoff) {
        toast.error('This query may require human assistance for the most accurate answer.')
      } else if (response.confidence_score < 0.7) {
        toast('Answer confidence is lower than usual. Please verify the information.', {
          icon: '⚠️'
        })
      }
    } catch (error: any) {
      console.error('Query failed:', error)
      
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: 'I apologize, but I encountered an error processing your question. Please try again or contact support if the issue persists.',
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, errorMessage])
      toast.error('Failed to get answer: ' + (error.response?.data?.detail || error.message))
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([])
  }

  const suggestedQuestions = [
    "What is our remote work policy?",
    "How do I submit expense reports?", 
    "What are the company benefits?",
    "What is our vacation policy?",
    "How do I request time off?"
  ]

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Chat with Your Documents</h1>
            <p className="mt-1 text-sm text-gray-600">
              Ask questions about your uploaded documents and get AI-powered answers with citations.
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={enableVerification}
                onChange={(e) => setEnableVerification(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">Enable verification</span>
            </label>
            <button
              onClick={clearChat}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Clear Chat
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto bg-gray-50 px-6 py-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <ComputerDesktopIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                Start a conversation
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                Ask any question about your uploaded documents.
              </p>
              
              {/* Suggested questions */}
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Try asking:</h4>
                <div className="flex flex-wrap justify-center gap-2">
                  {suggestedQuestions.map((question, index) => (
                    <button
                      key={index}
                      onClick={() => sendMessage(question)}
                      className="px-3 py-1 text-xs bg-white border border-gray-300 rounded-full text-gray-700 hover:bg-gray-50 hover:border-primary-300"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`flex max-w-3xl ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    {/* Avatar */}
                    <div className={`flex-shrink-0 ${message.type === 'user' ? 'ml-3' : 'mr-3'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        message.type === 'user' 
                          ? 'bg-primary-600' 
                          : 'bg-gray-600'
                      }`}>
                        {message.type === 'user' ? (
                          <UserIcon className="w-5 h-5 text-white" />
                        ) : (
                          <ComputerDesktopIcon className="w-5 h-5 text-white" />
                        )}
                      </div>
                    </div>

                    {/* Message content */}
                    <div className={`flex-1 ${message.type === 'user' ? 'text-right' : 'text-left'}`}>
                      <div className={`inline-block p-3 rounded-lg ${
                        message.type === 'user'
                          ? 'bg-primary-600 text-white'
                          : 'bg-white border border-gray-200 text-gray-900'
                      }`}>
                        <div className="whitespace-pre-wrap">{message.content}</div>
                      </div>

                      {/* Assistant message metadata */}
                      {message.type === 'assistant' && (
                        <div className="mt-2 text-xs text-gray-500 space-y-2">
                          <div className="flex items-center space-x-2">
                            <span>{formatDate(message.timestamp)}</span>
                            {message.confidence !== undefined && (
                              <span className={`px-2 py-1 rounded-full text-xs ${getConfidenceBadgeColor(message.confidence)}`}>
                                {Math.round(message.confidence * 100)}% confidence
                              </span>
                            )}
                            {message.requiresHandoff && (
                              <span className="px-2 py-1 rounded-full text-xs bg-yellow-100 text-yellow-800 flex items-center">
                                <ExclamationTriangleIcon className="w-3 h-3 mr-1" />
                                May need human help
                              </span>
                            )}
                          </div>

                          {/* Citations */}
                          {message.citations && message.citations.length > 0 && (
                            <div className="space-y-1">
                              <div className="font-medium text-gray-700">Sources:</div>
                              {message.citations.map((citation, index) => (
                                <div
                                  key={index}
                                  className="bg-gray-50 border border-gray-200 rounded p-2 text-xs"
                                >
                                  <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center space-x-2">
                                      <DocumentTextIcon className="w-4 h-4 text-gray-400" />
                                      <span className="font-medium text-gray-700">
                                        {citation.document_name}
                                      </span>
                                      {citation.page_number && (
                                        <span className="text-gray-500">
                                          (Page {citation.page_number})
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex items-center space-x-2">
                                      <span className={`px-1 py-0.5 rounded text-xs ${getConfidenceBadgeColor(citation.confidence_score)}`}>
                                        {Math.round(citation.confidence_score * 100)}%
                                      </span>
                                      {citation.verified ? (
                                        <CheckCircleIcon className="w-4 h-4 text-green-600" title="Verified" />
                                      ) : (
                                        <ExclamationTriangleIcon className="w-4 h-4 text-yellow-600" title="Not verified" />
                                      )}
                                    </div>
                                  </div>
                                  <div className="text-gray-600 text-xs">
                                    "{citation.content.substring(0, 200)}{citation.content.length > 200 ? '...' : ''}"
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex justify-start">
                  <div className="flex max-w-3xl">
                    <div className="flex-shrink-0 mr-3">
                      <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                        <ComputerDesktopIcon className="w-5 h-5 text-white" />
                      </div>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-3">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input form */}
      <div className="flex-shrink-0 bg-white border-t border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="flex space-x-4">
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask a question about your documents..."
                className="block w-full border border-gray-300 rounded-md px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                rows={1}
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <PaperAirplaneIcon className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}