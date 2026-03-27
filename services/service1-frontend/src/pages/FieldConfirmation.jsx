import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { confirmFields, ApiError } from '../api/medicheck'

/**
 * FieldConfirmation — Screen 2
 *
 * Displays extracted fields from the uploaded documents.
 * Every field — including individual line items — is editable inline.
 * Fields with confidence below 80% are highlighted in amber.
 * Confidence scores are stripped before POST /confirm.
 *
 * Layout: CSS Grid two-column on desktop, single column on mobile.
 *
 * Requirements: FR-06, FR-07, FR-08, FR-09, NFR-21, NFR-22
 */
export default function FieldConfirmation() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  const initial = location.state?.extracted_fields || {
    patient_name: '',
    provider_name: '',
    date_of_service: '',
    total_billed: '',
    line_items: []
  }

  const [fields, setFields] = useState(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFieldChange = (key, value) => {
    setFields(prev => ({ ...prev, [key]: value }))
  }

  const handleLineItemChange = (index, key, value) => {
    setFields(prev => {
      const updated = [...prev.line_items]
      updated[index] = { ...updated[index], [key]: value }
      return { ...prev, line_items: updated }
    })
  }

  const handleConfirm = async () => {
    setLoading(true)
    setError(null)

    // Strip confidence scores and description before sending — per api-contract.md
    const confirmedFields = {
      patient_name: fields.patient_name,
      provider_name: fields.provider_name,
      date_of_service: fields.date_of_service,
      total_billed: parseFloat(fields.total_billed) || 0,
      line_items: (fields.line_items || []).map(({ confidence, description, ...rest }) => ({
        ...rest,
        amount: parseFloat(rest.amount) || 0,
        quantity: parseInt(rest.quantity) || 1
      }))
    }

    try {
      await confirmFields(sessionId, confirmedFields)
      navigate(`/report/${sessionId}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Confirmation failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const requiredFilled = fields.patient_name && fields.provider_name && fields.date_of_service
  const lowConfidenceCount = (fields.line_items || []).filter(i => i.confidence < 0.80).length

  return (
    <div className="max-w-5xl mx-auto">

      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Review Extracted Fields</h1>
        <p className="text-gray-500 text-sm">
          Check that the information below matches your bill. Edit any field that looks
          incorrect, then click Confirm &amp; Analyse.
        </p>
        {lowConfidenceCount > 0 && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200
                        rounded px-3 py-2 mt-3 inline-block">
            ⚠ {lowConfidenceCount} field{lowConfidenceCount > 1 ? 's' : ''} highlighted
            in amber have low OCR confidence — please review carefully.
          </p>
        )}
      </div>

      {/* Session ID notice — FR-27 */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-6
                      text-xs text-gray-500">
        Session ID:{' '}
        <span className="font-mono font-medium text-gray-700">{sessionId}</span>
        &nbsp;— Save this to access your results later.
      </div>

      {/* CSS Grid — two columns on desktop, single column on mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

        {/* Left column — patient & provider details */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4 h-full">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Patient &amp; Provider
            </h2>
            <EditableField
              label="Patient Name"
              value={fields.patient_name}
              onChange={(v) => handleFieldChange('patient_name', v)}
              required
            />
            <EditableField
              label="Provider Name"
              value={fields.provider_name}
              onChange={(v) => handleFieldChange('provider_name', v)}
              required
            />
            <EditableField
              label="Date of Service"
              value={fields.date_of_service}
              onChange={(v) => handleFieldChange('date_of_service', v)}
              placeholder="YYYY-MM-DD"
              required
            />
            <EditableField
              label="Total Billed ($)"
              value={fields.total_billed}
              onChange={(v) => handleFieldChange('total_billed', v)}
              placeholder="0.00"
            />
          </div>
        </div>

        {/* Right column — line items table */}
        <div className="lg:col-span-2">
          <div className="bg-white border border-gray-200 rounded-lg p-6 h-full">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Line Items
            </h2>
            {!fields.line_items?.length ? (
              <p className="text-sm text-gray-400 italic">
                No line items extracted. Line items will populate from OCR output
                once Service 2 is connected.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
                      <th className="pb-2 pr-2 font-medium">Line</th>
                      <th className="pb-2 pr-2 font-medium">CPT Code</th>
                      <th className="pb-2 pr-2 font-medium">Qty</th>
                      <th className="pb-2 pr-2 font-medium">Amount ($)</th>
                      <th className="pb-2 pr-2 font-medium">Source</th>
                      <th className="pb-2 font-medium">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {fields.line_items.map((item, idx) => (
                      <LineItemRow
                        key={idx}
                        item={item}
                        onChange={(key, value) => handleLineItemChange(idx, key, value)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4
                        text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => navigate('/')}
          className="px-6 py-3 border border-gray-300 rounded-lg text-sm font-medium
                     text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={loading || !requiredFilled}
          className="flex-1 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-300
                     text-white font-semibold py-3 px-6 rounded-lg transition-colors
                     disabled:cursor-not-allowed"
        >
          {loading ? 'Confirming…' : 'Confirm & Analyse'}
        </button>
      </div>

    </div>
  )
}

// ── LineItemRow — inline editable table row ───────────────────────────────────

function LineItemRow({ item, onChange }) {
  const isLow = item.confidence < 0.80
  return (
    <tr className={isLow ? 'bg-amber-50' : ''}>
      <td className="py-2 pr-2 text-xs text-gray-400">{item.line_number}</td>

      <td className="py-2 pr-2">
        <input type="text" value={item.cpt_code || ''}
          onChange={(e) => onChange('cpt_code', e.target.value)}
          className={`w-24 border rounded px-2 py-1 text-xs font-mono focus:outline-none
                      focus:ring-1 focus:ring-blue-500
                      ${isLow ? 'border-amber-300 bg-amber-50' : 'border-gray-300 bg-white'}`}
        />
      </td>

      <td className="py-2 pr-2">
        <input type="number" min="1" value={item.quantity || 1}
          onChange={(e) => onChange('quantity', e.target.value)}
          className={`w-16 border rounded px-2 py-1 text-xs focus:outline-none
                      focus:ring-1 focus:ring-blue-500
                      ${isLow ? 'border-amber-300 bg-amber-50' : 'border-gray-300 bg-white'}`}
        />
      </td>

      <td className="py-2 pr-2">
        <input type="number" min="0" step="0.01" value={item.amount || ''}
          onChange={(e) => onChange('amount', e.target.value)}
          className={`w-24 border rounded px-2 py-1 text-xs focus:outline-none
                      focus:ring-1 focus:ring-blue-500
                      ${isLow ? 'border-amber-300 bg-amber-50' : 'border-gray-300 bg-white'}`}
        />
      </td>

      <td className="py-2 pr-2">
        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
          {item.source}
        </span>
      </td>

      <td className="py-2">
        <span className={`text-xs font-medium ${isLow ? 'text-amber-600' : 'text-gray-400'}`}>
          {Math.round((item.confidence || 0) * 100)}%{isLow && ' ⚠'}
        </span>
      </td>
    </tr>
  )
}

// ── EditableField ─────────────────────────────────────────────────────────────

function EditableField({ label, value, onChange, placeholder, required = false }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">
        {label}{required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || ''}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none
                    focus:ring-2 focus:ring-blue-500 transition-colors bg-white
                    ${!value && required ? 'border-red-300' : 'border-gray-300'}`}
      />
      {!value && required && (
        <p className="text-xs text-red-500 mt-1">This field is required before you can proceed.</p>
      )}
    </div>
  )
}
