import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { confirmFields, ApiError } from '../api/medicheck'

/**
 * FieldConfirmation — Screen 2
 * Requirements: FR-06, FR-07, FR-08, FR-09, NFR-21
 */
export default function FieldConfirmation() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Extracted fields passed from Upload page via navigation state
  const initial = location.state?.extracted_fields || {
    patient_name: '', provider_name: '', date_of_service: '', total_billed: '', line_items: []
  }

  const [fields, setFields] = useState(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleConfirm = async () => {
    setLoading(true)
    setError(null)

    // Strip confidence scores before sending — per api-contract.md
    const confirmedFields = {
      patient_name: fields.patient_name,
      provider_name: fields.provider_name,
      date_of_service: fields.date_of_service,
      total_billed: parseFloat(fields.total_billed) || 0,
      line_items: (fields.line_items || []).map(({ confidence, ...rest }) => rest)
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

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Review Extracted Fields</h1>
        <p className="text-gray-500 text-sm">
          Check that the information below matches your bill. Edit any field that looks incorrect,
          then click Confirm &amp; Analyse.
        </p>
        <p className="text-xs text-amber-600 mt-2">
          Fields highlighted in yellow have low OCR confidence — please review carefully.
        </p>
      </div>

      {/* Session ID — FR-27 */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-6 text-xs text-gray-500">
        Session ID: <span className="font-mono font-medium text-gray-700">{sessionId}</span>
        &nbsp;— Save this to access your results later.
      </div>

      {/* Key fields */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
          Patient &amp; Provider Details
        </h2>
        <EditableField label="Patient Name" value={fields.patient_name}
          onChange={(v) => setFields(f => ({ ...f, patient_name: v }))} required />
        <EditableField label="Provider Name" value={fields.provider_name}
          onChange={(v) => setFields(f => ({ ...f, provider_name: v }))} required />
        <EditableField label="Date of Service" value={fields.date_of_service}
          onChange={(v) => setFields(f => ({ ...f, date_of_service: v }))}
          placeholder="YYYY-MM-DD" required />
        <EditableField label="Total Billed ($)" value={fields.total_billed}
          onChange={(v) => setFields(f => ({ ...f, total_billed: v }))} placeholder="0.00" />
      </div>

      {/* Line items */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
          Line Items
        </h2>
        {!fields.line_items?.length ? (
          <p className="text-sm text-gray-400 italic">No line items extracted.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
                <th className="pb-2 pr-3">Line</th>
                <th className="pb-2 pr-3">CPT Code</th>
                <th className="pb-2 pr-3">Qty</th>
                <th className="pb-2 pr-3">Amount</th>
                <th className="pb-2 pr-3">Source</th>
                <th className="pb-2">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {fields.line_items.map((item, idx) => (
                <tr key={idx}
                  className={`border-b border-gray-100 ${item.confidence < 0.80 ? 'bg-amber-50' : ''}`}>
                  <td className="py-2 pr-3 text-gray-500">{item.line_number}</td>
                  <td className="py-2 pr-3 font-mono">{item.cpt_code}</td>
                  <td className="py-2 pr-3">{item.quantity}</td>
                  <td className="py-2 pr-3">${item.amount?.toFixed(2)}</td>
                  <td className="py-2 pr-3">
                    <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">{item.source}</span>
                  </td>
                  <td className="py-2">
                    <span className={`text-xs ${item.confidence < 0.80 ? 'text-amber-600 font-medium' : 'text-gray-400'}`}>
                      {Math.round(item.confidence * 100)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={() => navigate('/')}
          className="px-6 py-3 border border-gray-300 rounded-lg text-sm font-medium
                     text-gray-700 hover:bg-gray-50 transition-colors">
          Back
        </button>
        <button onClick={handleConfirm} disabled={loading || !requiredFilled}
          className="flex-1 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-300
                     text-white font-semibold py-3 px-6 rounded-lg transition-colors
                     disabled:cursor-not-allowed">
          {loading ? 'Confirming…' : 'Confirm & Analyse'}
        </button>
      </div>
    </div>
  )
}

function EditableField({ label, value, onChange, placeholder, required = false }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">
        {label}{required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || ''}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none
                    focus:ring-2 focus:ring-blue-500 transition-colors border-gray-300 bg-white
                    ${!value && required ? 'border-red-300' : ''}`} />
      {!value && required && (
        <p className="text-xs text-red-500 mt-1">This field is required before you can proceed.</p>
      )}
    </div>
  )
}
