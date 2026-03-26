import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analyseSession, generateLetter, ApiError } from '../api/medicheck'

/**
 * ErrorReport — Screen 3
 * Requirements: FR-10–FR-16, FR-18, FR-19, NFR-01, NFR-02, NFR-20
 */

const SEVERITY_STYLES = {
  high:   { border: 'border-red-300',   bg: 'bg-red-50',   badge: 'bg-red-100 text-red-700',    label: 'High Impact' },
  medium: { border: 'border-amber-300', bg: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700', label: 'Medium Impact' },
  low:    { border: 'border-green-300', bg: 'bg-green-50', badge: 'bg-green-100 text-green-700', label: 'Informational' },
}

export default function ErrorReport() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generatingLetter, setGeneratingLetter] = useState(false)

  useEffect(() => {
    analyseSession(sessionId)
      .then(setResults)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Analysis failed.'))
      .finally(() => setLoading(false))
  }, [sessionId])

  const handleGenerateLetter = async () => {
    setGeneratingLetter(true)
    try {
      await generateLetter(sessionId)
      navigate(`/letter/${sessionId}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Letter generation failed.')
      setGeneratingLetter(false)
    }
  }

  if (loading) return (
    <div className="max-w-2xl mx-auto text-center py-20">
      <div className="text-4xl mb-4">⚙️</div>
      <h2 className="text-xl font-semibold text-gray-800 mb-2">Running analysis…</h2>
      <p className="text-gray-500 text-sm">Checking for duplicate charges, rate outliers, EOB mismatches, and No Surprises Act violations.</p>
      <p className="text-gray-400 text-xs mt-3">This may take up to 30 seconds.</p>
    </div>
  )

  if (error) return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-5 text-sm text-red-700">
        <p className="font-semibold mb-1">Analysis failed</p>
        <p>{error}</p>
        <button onClick={() => navigate('/')} className="mt-4 underline text-xs">Start over</button>
      </div>
    </div>
  )

  if (results?.all_clear) return (
    <div className="max-w-2xl mx-auto text-center py-16">
      <div className="text-5xl mb-4">✅</div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">No obvious errors found</h1>
      <p className="text-gray-500 text-sm max-w-md mx-auto">
        We checked for duplicate charges, Medicare rate outliers, EOB mismatches, and No Surprises Act violations.
        Your bill appears accurate based on the information provided.
      </p>
      <button onClick={() => navigate('/')} className="mt-8 text-blue-700 underline text-sm">
        Analyse another bill
      </button>
    </div>
  )

  return (
    <div className="max-w-3xl mx-auto">
      {/* Summary header */}
      <div className="bg-white border border-gray-200 rounded-lg px-6 py-5 mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {results?.total_errors} {results?.total_errors === 1 ? 'error' : 'errors'} found
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Estimated potential savings:{' '}
            <span className="font-semibold text-green-600">${results?.total_estimated_savings?.toFixed(2)}</span>
          </p>
        </div>
        <button onClick={handleGenerateLetter} disabled={generatingLetter}
          className="bg-blue-700 hover:bg-blue-600 disabled:bg-gray-300 text-white
                     font-semibold py-2 px-5 rounded-lg text-sm transition-colors disabled:cursor-not-allowed">
          {generatingLetter ? 'Generating…' : 'Generate Dispute Letter'}
        </button>
      </div>

      {/* RAG unavailable notice — NFR-02 */}
      {results?.rag_available === false && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4 text-sm text-amber-700">
          Explanations are temporarily unavailable.{' '}
          <button className="underline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {/* Error cards */}
      <div className="space-y-4">
        {results?.errors?.map((err) => <ErrorCard key={err.error_id} error={err} />)}
      </div>
    </div>
  )
}

function ErrorCard({ error }) {
  const [expanded, setExpanded] = useState(false)
  const styles = SEVERITY_STYLES[error.confidence] || SEVERITY_STYLES.low

  return (
    <div className={`border ${styles.border} ${styles.bg} rounded-lg p-5`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${styles.badge} mr-2`}>
            {styles.label}
          </span>
          <span className="text-xs text-gray-500">{error.module?.replace(/_/g, ' ')}</span>
        </div>
        <span className="text-sm font-bold text-gray-800">${error.estimated_dollar_impact?.toFixed(2)}</span>
      </div>

      <h3 className="text-sm font-semibold text-gray-900 mb-1">{error.error_type}</h3>
      <p className="text-sm text-gray-700 mb-2">{error.description}</p>
      <p className="text-xs text-gray-500 mb-3">
        Affected line items: {error.line_items_affected?.join(', ')}
      </p>

      {error.explanation ? (
        <div>
          <button onClick={() => setExpanded(!expanded)} className="text-xs text-blue-700 underline">
            {expanded ? 'Hide explanation' : 'Show explanation & citations'}
          </button>
          {expanded && (
            <div className="mt-3 space-y-2">
              <p className="text-sm text-gray-700">{error.explanation}</p>
              {error.citations?.map((c, i) => (
                <a key={i} href={c.url} target="_blank" rel="noopener noreferrer"
                  className="block text-xs text-blue-600 hover:underline">
                  📄 {c.source} — {c.section}
                </a>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic">Explanation temporarily unavailable.</p>
      )}
    </div>
  )
}
