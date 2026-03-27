/**
 * medicheck.js — MediCheck API Service
 *
 * Centralises all calls from Service 1 (frontend) to Service 2 (Bill Analysis API).
 * No component should make a raw fetch() call to Service 2 — all calls go through
 * this module so the API contract is enforced in one place.
 *
 * Base URL is read from the Vite environment variable VITE_API_URL.
 * Locally this is proxied via vite.config.js to http://localhost:5001.
 * On Render it is set to the Service 2 deployed URL via environment variable.
 *
 * See /docs/api-contract.md for the full request/response schema.
 */

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

// ── Error class ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(errorCode, message, sessionId = null, httpStatus = null) {
    super(message)
    this.name = 'ApiError'
    this.errorCode = errorCode
    this.sessionId = sessionId
    this.httpStatus = httpStatus
  }
}

// ── Internal helper ───────────────────────────────────────────────────────────

async function request(method, path, body = null, isMultipart = false) {
  const options = {
    method,
    headers: isMultipart ? {} : { 'Content-Type': 'application/json' },
    body: isMultipart ? body : body ? JSON.stringify(body) : null
  }

  const response = await fetch(`${BASE_URL}${path}`, options)
  const data = await response.json()

  if (!response.ok) {
    throw new ApiError(
      data.error_code || 'UNKNOWN_ERROR',
      data.message || 'An unexpected error occurred.',
      data.session_id || null,
      response.status
    )
  }

  return data
}

// ── API functions ─────────────────────────────────────────────────────────────

/**
 * Upload one or two PDF documents.
 * @param {File} billFile - Provider bill PDF (required)
 * @param {File|null} eobFile - EOB PDF (optional)
 * @returns {Promise<{session_id, status, extracted_fields, rag_available}>}
 */
export async function uploadDocuments(billFile, eobFile = null) {
  const formData = new FormData()
  formData.append('bill', billFile)
  if (eobFile) formData.append('eob', eobFile)
  return request('POST', '/upload', formData, true)
}

/**
 * Submit user-confirmed field values.
 * Confidence scores are stripped here before sending — per api-contract.md.
 * @param {string} sessionId
 * @param {object} confirmedFields
 * @returns {Promise<{session_id, status}>}
 */
export async function confirmFields(sessionId, confirmedFields) {
  return request('POST', '/confirm', {
    session_id: sessionId,
    confirmed_fields: confirmedFields
  })
}

/**
 * Trigger error detection analysis.
 * Note: HTTP 200 may include rag_available: false on Service 3 timeout.
 * Handle gracefully — show retry option, not an error state.
 * @param {string} sessionId
 * @returns {Promise<{session_id, status, total_errors, total_estimated_savings,
 *                    all_clear, rag_available, errors}>}
 */
export async function analyseSession(sessionId) {
  return request('POST', '/analyse', { session_id: sessionId })
}

/**
 * Request dispute letter generation.
 * @param {string} sessionId
 * @returns {Promise<{session_id, status, downloads: {docx, pdf}}>}
 */
export async function generateLetter(sessionId) {
  return request('POST', '/letter', { session_id: sessionId })
}

/**
 * Retrieve analysis results for an existing session.
 * @param {string} sessionId
 * @returns {Promise<{session_id, status, total_errors, total_estimated_savings,
 *                    all_clear, rag_available, errors, downloads}>}
 */
export async function getReport(sessionId) {
  return request('GET', `/report/${sessionId}`)
}

/**
 * Check Service 2 health.
 * @returns {Promise<{status, service}>}
 */
export async function checkHealth() {
  return request('GET', '/health')
}
