/**
 * Unit tests for medicheck.js — API client module.
 * All fetch() calls are mocked. No live HTTP traffic.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ApiError, analyseSession, confirmFields, uploadDocuments, getReport } from './medicheck'

// ── ApiError ──────────────────────────────────────────────────────────────────

describe('ApiError', () => {
  it('stores all constructor fields', () => {
    const err = new ApiError('SESSION_NOT_FOUND', 'Not found', 'abc-123', 404)
    expect(err.name).toBe('ApiError')
    expect(err.errorCode).toBe('SESSION_NOT_FOUND')
    expect(err.message).toBe('Not found')
    expect(err.sessionId).toBe('abc-123')
    expect(err.httpStatus).toBe(404)
  })

  it('defaults sessionId and httpStatus to null', () => {
    const err = new ApiError('ERR', 'Something went wrong')
    expect(err.sessionId).toBeNull()
    expect(err.httpStatus).toBeNull()
  })

  it('is an instance of Error', () => {
    expect(new ApiError('E', 'msg')).toBeInstanceOf(Error)
  })
})

// ── request — error handling ──────────────────────────────────────────────────

describe('request — error handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('throws ApiError with server error_code on non-OK response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error_code: 'SESSION_NOT_FOUND',
        message: 'Session not found.',
        session_id: null,
      }),
    })

    await expect(analyseSession('bad-id')).rejects.toMatchObject({
      errorCode: 'SESSION_NOT_FOUND',
      httpStatus: 404,
    })
  })

  it('throws ApiError with INVALID_RESPONSE when response body is not JSON (H4 fix)', async () => {
    // Simulates Render 502 returning an HTML error page instead of JSON
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => { throw new SyntaxError('Unexpected token < in JSON') },
    })

    await expect(analyseSession('any-id')).rejects.toMatchObject({
      errorCode: 'INVALID_RESPONSE',
      httpStatus: 502,
    })
  })

  it('returns parsed data on a successful response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'abc-123', status: 'analysed', total_errors: 2 }),
    })

    const result = await analyseSession('abc-123')
    expect(result.session_id).toBe('abc-123')
    expect(result.total_errors).toBe(2)
  })
})

// ── confirmFields ─────────────────────────────────────────────────────────────

describe('confirmFields', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('sends session_id and confirmed_fields in the request body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'abc', status: 'confirmed' }),
    })

    await confirmFields('abc', { patient_name: 'Jane Doe', total_billed: 1250.00 })

    const [, options] = globalThis.fetch.mock.calls[0]
    const body = JSON.parse(options.body)
    expect(body.session_id).toBe('abc')
    expect(body.confirmed_fields.patient_name).toBe('Jane Doe')
    expect(body.confirmed_fields.total_billed).toBe(1250.00)
  })
})

// ── uploadDocuments ───────────────────────────────────────────────────────────

describe('uploadDocuments', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('includes bill file in FormData', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'xyz', status: 'extracted' }),
    })

    const billFile = new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], 'bill.pdf', {
      type: 'application/pdf',
    })
    await uploadDocuments(billFile)

    const [, options] = globalThis.fetch.mock.calls[0]
    expect(options.body).toBeInstanceOf(FormData)
    expect(options.body.get('bill')).toBe(billFile)
    expect(options.body.get('eob')).toBeNull()
  })

  it('appends EOB to FormData when provided', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'xyz', status: 'extracted' }),
    })

    const billFile = new File([new Uint8Array([0x25])], 'bill.pdf')
    const eobFile = new File([new Uint8Array([0x25])], 'eob.pdf')
    await uploadDocuments(billFile, eobFile)

    const [, options] = globalThis.fetch.mock.calls[0]
    expect(options.body.get('eob')).toBe(eobFile)
  })
})

// ── getReport ─────────────────────────────────────────────────────────────────

describe('getReport', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('calls GET /report/<sessionId>', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'abc', status: 'analysed' }),
    })

    await getReport('abc')

    const [url] = globalThis.fetch.mock.calls[0]
    expect(url).toContain('/report/abc')
  })
})
