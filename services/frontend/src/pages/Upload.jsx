import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocuments, ApiError } from '../api/medicheck'

/**
 * Upload — Screen 1 (Home)
 * Requirements: FR-01, FR-02, FR-03, FR-04, FR-05, FR-24, FR-27
 */
export default function Upload() {
  const navigate = useNavigate()
  const [billFile, setBillFile] = useState(null)
  const [eobFile, setEobFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!billFile) {
      setError('Please upload your provider bill before continuing.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await uploadDocuments(billFile, eobFile)
      navigate(`/confirm/${data.session_id}`, { state: { extracted_fields: data.extracted_fields } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please check your connection and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          Check your medical bill for errors in 30 seconds
        </h1>
        <p className="text-gray-500 text-base">
          Upload your provider bill and optional EOB. MediCheck detects billing errors
          and generates a dispute letter — no medical expertise required.
        </p>
      </div>

      <div className="space-y-4 mb-6">
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
      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-6 text-sm text-amber-800">
        ⚠ Your session ID is the only way to access your results. Save it before proceeding.
        No account or email address is required.
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4 text-sm text-red-700">
          {error}
        </div>
      )}

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
    </div>
  )
}

function UploadZone({ label, hint, file, onFileChange, id, optional = false }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label} {optional && <span className="text-gray-400 font-normal">(optional)</span>}
      </label>
      <label
        htmlFor={id}
        className="flex flex-col items-center justify-center w-full h-32
                   border-2 border-dashed border-gray-300 rounded-lg
                   bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
      >
        {file ? (
          <span className="text-sm text-blue-700 font-medium">{file.name}</span>
        ) : (
          <>
            <span className="text-sm text-gray-500">Drag and drop or click to browse</span>
            <span className="text-xs text-gray-400 mt-1">{hint}</span>
          </>
        )}
        <input id={id} type="file" accept="application/pdf" className="hidden"
          onChange={(e) => { if (e.target.files[0]) onFileChange(e.target.files[0]) }} />
      </label>
    </div>
  )
}
