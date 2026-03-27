import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getReport, ApiError } from '../api/medicheck'

/**
 * DisputeLetter — Screen 4
 *
 * Layout:
 *  - Download buttons: CSS Grid, two equal columns
 *  - Letter contents checklist: Flexbox column
 *  - Action buttons: Flexbox row
 *
 * Requirements: FR-21, FR-22, FR-23, NFR-22
 */
export default function DisputeLetter() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [downloads, setDownloads] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getReport(sessionId)
      .then((data) => {
        if (data.downloads) setDownloads(data.downloads)
        else setError('Dispute letter not yet available. Please generate it from the error report.')
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not retrieve letter.'))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (loading) return (
    <div className="flex flex-col items-center justify-center py-24 gap-3">
      <p className="text-gray-500 text-sm">Preparing your dispute letter…</p>
    </div>
  )

  if (error) return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-5 text-sm text-red-700">
        <p className="font-semibold mb-1">Letter unavailable</p>
        <p>{error}</p>
        <button onClick={() => navigate(`/report/${sessionId}`)}
          className="mt-4 underline text-xs">
          Back to error report
        </button>
      </div>
    </div>
  )

  return (
    // Flexbox column — centred content
    <div className="flex flex-col items-center">
      <div className="w-full max-w-2xl">

        {/* Header — Flexbox column, centred */}
        <div className="flex flex-col items-center text-center mb-8 gap-3">
          <div className="text-5xl">📄</div>
          <h1 className="text-2xl font-bold text-gray-900">Your dispute letter is ready</h1>
          <p className="text-gray-500 text-sm max-w-md">
            Download in Word format to add your personal details before sending,
            or download the PDF for a ready-to-print version.
          </p>
        </div>

        {/* Session ID */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-6
                        text-xs text-gray-500 text-center">
          Session ID:{' '}
          <span className="font-mono font-medium text-gray-700">{sessionId}</span>
        </div>

        {/* Download buttons — CSS Grid, two equal columns — FR-21, FR-23 */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <a
            href={downloads?.docx}
            download
            className="flex flex-col items-center justify-center bg-blue-700
                       hover:bg-blue-600 text-white font-semibold py-5 px-4
                       rounded-lg transition-colors text-center gap-2"
          >
            <span className="text-2xl">📝</span>
            <span className="text-sm">Download Word</span>
            <span className="text-xs font-normal opacity-75">Editable — recommended</span>
          </a>

          <a
            href={downloads?.pdf}
            download
            className="flex flex-col items-center justify-center bg-white
                       border-2 border-blue-700 text-blue-700 hover:bg-blue-50
                       font-semibold py-5 px-4 rounded-lg transition-colors
                       text-center gap-2"
          >
            <span className="text-2xl">🖨️</span>
            <span className="text-sm">Download PDF</span>
            <span className="text-xs font-normal opacity-75">Ready to print or attach</span>
          </a>
        </div>

        {/* What's in the letter — Flexbox column — FR-22 */}
        <div className="flex flex-col gap-3 bg-gray-50 border border-gray-200
                        rounded-lg p-5 mb-6">
          <h2 className="font-semibold text-gray-800 text-sm">
            What&#39;s included in the letter
          </h2>
          <ul className="flex flex-col gap-1.5 text-sm text-gray-600">
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Patient name and insurance member ID</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Provider name and identifier</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Numbered list of each detected error with CPT code, billed amount, and estimated overcharge</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Regulatory citations for each error (CMS, No Surprises Act)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Total estimated overcharge across all errors</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Formal written dispute request paragraph</span>
            </li>
          </ul>
        </div>

        {/* Action buttons — Flexbox row */}
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/report/${sessionId}`)}
            className="px-5 py-3 border border-gray-300 rounded-lg text-sm font-medium
                       text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Back to error report
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-5 py-3 border border-gray-300 rounded-lg text-sm font-medium
                       text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Analyse another bill
          </button>
        </div>

      </div>
    </div>
  )
}
