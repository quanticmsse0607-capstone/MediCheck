import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocuments, ApiError } from '../api/medicheck'

/**
 * Upload — Screen 1 (Home)
 *
 * Layout: Flexbox column, centred, max-width constrained.
 * Upload zones use Flexbox column alignment internally.
 *
 * Requirements: FR-01, FR-02, FR-03, FR-04, FR-05, FR-24, FR-27
 */
export default function Upload() {
  const navigate = useNavigate()
  const [billFile, setBillFile] = useState(null)
  const [eobFile, setEobFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sessionInput, setSessionInput] = useState('')
  const [sessionError, setSessionError] = useState(null)

  const handleRetrieve = () => {
    const id = sessionInput.trim()
    if (!id) {
      setSessionError('Please enter a session ID.')
      return
    }
    navigate(`/report/${id}`)
  }

  const handleUpload = async () => {
    if (!billFile) {
      setError('Please upload your provider bill before continuing.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await uploadDocuments(billFile, eobFile)
      navigate(`/confirm/${data.session_id}`, {
        state: { extracted_fields: data.extracted_fields }
      })
    } catch (err) {
      setError(err instanceof ApiError
        ? err.message
        : 'Upload failed. Please check your connection and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    // Flexbox column — centred content with max width
    <div className="flex flex-col items-center">
      <div className="w-full max-w-2xl">

        {/* Hero — Flexbox column, centred text */}
        <div className="flex flex-col items-center text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Check your medical bill for errors in 60 seconds
          </h1>
          <p className="text-gray-500 text-base max-w-xl">
            80% of US medical bills contain errors, costing patients an estimated $68 billion
            annually. Upload your provider bill and optional Explanation of Benefits.
          </p>
          <p className="text-gray-500 text-base max-w-xl mt-3">
            MediCheck checks for duplicate charges, Medicare rate outliers, EOB mismatches,
            and No Surprises Act violations, then generates a ready-to-send dispute letter.
            Free to use. No account required.
          </p>
        </div>

        {/* How it works — 3 steps */}
        <div className="grid grid-cols-3 gap-4 mb-8 text-center">
          <div className="flex flex-col items-center gap-1">
            <span className="text-2xl">📄</span>
            <span className="text-xs font-semibold text-gray-700">1. Upload</span>
            <span className="text-xs text-gray-400">Your bill and optional EOB</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <span className="text-2xl">🔍</span>
            <span className="text-xs font-semibold text-gray-700">2. Review</span>
            <span className="text-xs text-gray-400">Confirm extracted fields</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <span className="text-2xl">📬</span>
            <span className="text-xs font-semibold text-gray-700">3. Dispute</span>
            <span className="text-xs text-gray-400">Download your letter</span>
          </div>
        </div>

        {/* Pilot notice */}
        <div className="flex items-start gap-2 bg-blue-50 border border-blue-200
                        rounded-lg px-4 py-3 mb-6 text-sm text-blue-800">
          <span className="mt-0.5">ℹ️</span>
          <span>
            <span className="font-semibold">Pilot programme — South &amp; North Carolina.</span>{' '}
            MediCheck currently supports bills from providers in South Carolina and North Carolina.
            Medicare rate benchmarks and No Surprises Act locality data are scoped to these states.
          </span>
        </div>

        {/* Upload zones — Flexbox column with gap */}
        <div className="flex flex-col gap-4 mb-6">
          <UploadZone
            label="Provider Bill (PDF)"
            hint="Required · Max 20 pages · Max 10 MB"
            file={billFile}
            onFileChange={setBillFile}
            id="bill-upload"
          />
          <UploadZone
            label="Explanation of Benefits — EOB (PDF)"
            hint="Optional — enables EOB reconciliation check"
            file={eobFile}
            onFileChange={setEobFile}
            id="eob-upload"
            optional
          />
        </div>

        {/* Session ID privacy notice — FR-24, FR-27 */}
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200
                        rounded-lg px-4 py-3 mb-6 text-sm text-amber-800">
          <span className="mt-0.5">⚠</span>
          <span>
            Save your session ID to retrieve your results later. No account or
            email address is required.
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4
                          text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!billFile || loading}
          className="w-full bg-blue-700 hover:bg-blue-600 disabled:bg-gray-300
                     text-white font-semibold py-3 px-6 rounded-lg transition-colors
                     disabled:cursor-not-allowed"
        >
          {loading ? 'Uploading & extracting fields…' : 'Upload & Extract Fields'}
        </button>

        {loading && (
          <p className="text-center text-sm text-gray-500 mt-3">
            This may take up to 60 seconds. Please do not close this page.
          </p>
        )}

        {/* Divider */}
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400 uppercase tracking-wide">or retrieve existing results</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        {/* Retrieve session — FR-27 */}
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={sessionInput}
              onChange={(e) => { setSessionInput(e.target.value); setSessionError(null) }}
              onKeyDown={(e) => e.key === 'Enter' && handleRetrieve()}
              placeholder="Enter your session ID"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-sm
                         font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleRetrieve}
              className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700
                         font-semibold py-3 px-5 rounded-lg text-sm transition-colors
                         whitespace-nowrap"
            >
              Retrieve Results
            </button>
          </div>
          {sessionError && (
            <p className="text-xs text-red-600">{sessionError}</p>
          )}
        </div>

      </div>
    </div>
  )
}

// ── UploadZone — Flexbox column, centred content ──────────────────────────────

function UploadZone({ label, hint, file, onFileChange, id, optional = false }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label}{optional && <span className="text-gray-400 font-normal ml-1">(optional)</span>}
      </label>
      <label
        htmlFor={id}
        className="flex flex-col items-center justify-center w-full h-32
                   border-2 border-dashed border-gray-300 rounded-lg
                   bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
      >
        {file ? (
          <span className="text-sm text-blue-700 font-medium px-4 text-center">
            ✓ {file.name}
          </span>
        ) : (
          <div className="flex flex-col items-center gap-1">
            <span className="text-sm text-gray-500">Drag and drop or click to browse</span>
            <span className="text-xs text-gray-400">{hint}</span>
          </div>
        )}
        <input
          id={id}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => { if (e.target.files[0]) onFileChange(e.target.files[0]) }}
        />
      </label>
    </div>
  )
}
