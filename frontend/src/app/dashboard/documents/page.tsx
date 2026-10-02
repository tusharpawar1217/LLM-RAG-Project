'use client'

import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  TrashIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline'
import { toast } from 'react-hot-toast'
import { Document, DocumentStatus } from '@/types'
import { documentsApi } from '@/lib/api'
import { formatBytes, formatDate, getStatusBadgeColor, getFileIcon } from '@/lib/utils'

interface UploadProgress {
  [key: string]: number
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | 'all'>('all')

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const data = await documentsApi.getDocuments({
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined
      })
      setDocuments(data.items || data)
    } catch (error) {
      console.error('Failed to load documents:', error)
      toast.error('Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    acceptedFiles.forEach((file) => {
      uploadDocument(file)
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md']
    },
    multiple: true
  })

  const uploadDocument = async (file: File) => {
    const fileId = `${file.name}-${Date.now()}`
    
    try {
      setUploadProgress(prev => ({ ...prev, [fileId]: 0 }))
      
      const result = await documentsApi.uploadDocument(
        file,
        (progress) => {
          setUploadProgress(prev => ({ ...prev, [fileId]: progress }))
        },
        { name: file.name }
      )

      setUploadProgress(prev => {
        const { [fileId]: _, ...rest } = prev
        return rest
      })

      toast.success(`${file.name} uploaded successfully`)
      loadDocuments() // Refresh the list
    } catch (error: any) {
      console.error('Upload failed:', error)
      toast.error(`Failed to upload ${file.name}: ${error.response?.data?.detail || error.message}`)
      
      setUploadProgress(prev => {
        const { [fileId]: _, ...rest } = prev
        return rest
      })
    }
  }

  const deleteDocument = async (documentId: string, documentName: string) => {
    if (!confirm(`Are you sure you want to delete "${documentName}"?`)) {
      return
    }

    try {
      await documentsApi.deleteDocument(documentId)
      toast.success('Document deleted successfully')
      loadDocuments()
    } catch (error) {
      console.error('Failed to delete document:', error)
      toast.error('Failed to delete document')
    }
  }

  const reprocessDocument = async (documentId: string, documentName: string) => {
    try {
      await documentsApi.reprocessDocument(documentId)
      toast.success(`${documentName} queued for reprocessing`)
      loadDocuments()
    } catch (error) {
      console.error('Failed to reprocess document:', error)
      toast.error('Failed to reprocess document')
    }
  }

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = !searchQuery || 
      doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter

    return matchesSearch && matchesStatus
  })

  const uploadingFiles = Object.keys(uploadProgress)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Documents</h1>
          <p className="mt-2 text-sm text-gray-700">
            Upload and manage your documents for AI-powered question answering.
          </p>
        </div>
      </div>

      {/* Upload area */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              isDragActive 
                ? 'border-primary-500 bg-primary-50' 
                : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }`}
          >
            <input {...getInputProps()} />
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4">
              <p className="text-lg font-medium text-gray-900">
                {isDragActive ? 'Drop files here' : 'Upload documents'}
              </p>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop files here, or click to browse
              </p>
              <p className="mt-1 text-xs text-gray-500">
                Supports PDF, DOC, DOCX, TXT, MD (max 50MB each)
              </p>
            </div>
          </div>

          {/* Upload progress */}
          {uploadingFiles.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="text-sm font-medium text-gray-900">Uploading...</h4>
              {uploadingFiles.map(fileId => {
                const fileName = fileId.split('-').slice(0, -1).join('-')
                const progress = uploadProgress[fileId]
                return (
                  <div key={fileId} className="flex items-center space-x-3">
                    <div className="flex-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 truncate">{fileName}</span>
                        <span className="text-gray-500">{progress}%</span>
                      </div>
                      <div className="mt-1 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary-600 h-2 rounded-full transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="sm:flex sm:items-center sm:space-x-4">
            <div className="flex-1">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
            </div>
            <div className="mt-3 sm:mt-0">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as DocumentStatus | 'all')}
                className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
              >
                <option value="all">All Status</option>
                <option value={DocumentStatus.PENDING}>Pending</option>
                <option value={DocumentStatus.PROCESSING}>Processing</option>
                <option value={DocumentStatus.COMPLETED}>Completed</option>
                <option value={DocumentStatus.FAILED}>Failed</option>
              </select>
            </div>
            <button
              onClick={loadDocuments}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <FunnelIcon className="h-4 w-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Documents list */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Your Documents ({filteredDocuments.length})
          </h3>
          
          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse flex items-center space-x-4">
                  <div className="w-10 h-10 bg-gray-200 rounded"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                    <div className="h-3 bg-gray-200 rounded w-1/4"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
              <p className="mt-1 text-sm text-gray-500">
                {searchQuery || statusFilter !== 'all' 
                  ? 'No documents match your filters.' 
                  : 'Get started by uploading your first document.'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredDocuments.map((document) => (
                <div
                  key={document.id}
                  className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50"
                >
                  <div className="flex items-center space-x-4">
                    <div className="text-2xl">
                      {getFileIcon(document.original_filename)}
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-gray-900">
                        {document.name}
                      </h4>
                      <p className="text-sm text-gray-600">
                        {document.original_filename}
                      </p>
                      <div className="flex items-center space-x-4 mt-1">
                        <span className="text-xs text-gray-500">
                          {formatBytes(document.file_size)}
                        </span>
                        <span className="text-xs text-gray-500">
                          {formatDate(document.created_at)}
                        </span>
                        {document.metadata.chunk_count && (
                          <span className="text-xs text-gray-500">
                            {document.metadata.chunk_count} chunks
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadgeColor(document.status)}`}>
                      {document.status}
                    </span>
                    
                    <div className="flex items-center space-x-2">
                      {document.status === DocumentStatus.FAILED && (
                        <button
                          onClick={() => reprocessDocument(document.id, document.name)}
                          className="p-1 text-gray-400 hover:text-blue-600"
                          title="Reprocess document"
                        >
                          <ArrowPathIcon className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteDocument(document.id, document.name)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Delete document"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}