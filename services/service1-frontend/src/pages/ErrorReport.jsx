import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analyseSession, generateLetter, ApiError } from '../api/medicheck'

/**
 * ErrorReport — Screen 3
 *
 * Layout:
 *  - Summary header: Flexbox row, space-between
 *  - Error cards: CSS Grid, two columns on large screens, one on mobile
 *  - Each card: Flexbox column internally
 *
 * Requirements: FR-10–FR-16, FR-18, FR-19, NFR-01, NFR-02, NFR-20, NFR-22
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

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="text-4xl">⚙️</div>
      <h2 className="text-xl font-semibold text-gray-800">Running analysis…</h2>
      <p className="text-gray-500 text-sm text-center max-w-sm">
        Checking for duplicate charges, rate outliers, EOB mismatches,
        and No Surprises Act violations.
      </p>
      <p className="text-gray-400 text-xs">This may take up to 30 seconds.</p>
    </div>
  )

  // ── Error ─────────────────────────────────────────────────────────────────
  if (error) return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-5 text-sm text-red-700">
        <p className="font-semibold mb-1">Analysis failed</p>
        <p>{error}</p>
        <button onClick={() => navigate('/')} className="mt-4 underline text-xs">
          Start over
        </button>
      </div>
    </div>
  )

  // ── All clear ─────────────────────────────────────────────────────────────
  if (results?.all_clear) return (
    <div className="flex flex-col items-center text-center py-16 gap-4">
      <div className="text-5xl">✅</div>
      <h1 className="text-2xl font-bold text-gray-900">No obvious errors found</h1>
      <p className="text-gray-500 text-sm max-w-md">
        We checked for duplicate charges, Medicare rate outliers, EOB mismatches,
        and No Surprises Act violations. Your bill appears accurate.
      </p>
      <button onClick={() => navigate('/')} className="mt-4 text-blue-700 underline text-sm">
        Analyse another bill
      </button>
    </div>
  )

  // ── Results ───────────────────────────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto">

      {/* Summary header — Flexbox row, space between */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between
                      gap-4 bg-white border border-gray-200 rounded-lg px-6 py-5 mb-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-gray-900">
            {results?.total_errors} {results?.total_errors === 1 ? 'error' : 'errors'} found
          </h1>
          <p className="text-gray-500 text-sm">
            Estimated potential savings:{' '}
            <span className="font-semibold text-green-600">
              ${results?.total_estimated_savings?.toFixed(2)}
            </span>
          </p>
        </div>
        <button
          onClick={handleGenerateLetter}
          disabled={generatingLetter}
          className="bg-blue-700 hover:bg-blue-600 disabled:bg-gray-300 text-white
                     font-semibold py-2 px-5 rounded-lg text-sm transition-colors
                     disabled:cursor-not-allowed whitespace-nowrap"
        >
          {generatingLetter ? 'Generating…' : 'Generate Dispute Letter'}
        </button>
      </div>

      {/* RAG unavailable notice */}
      {results?.rag_available === false && (
        <div className="flex items-center gap-2 bg-amber-50 border border-amber-200
                        rounded-lg px-4 py-3 mb-4 text-sm text-amber-700">
          <span>Explanations are temporarily unavailable.</span>
          <button className="underline ml-1" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      )}

      {/* Error cards — CSS Grid, two columns on large screens */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {results?.errors?.map((err) => (
          <ErrorCard key={err.error_id} error={err} />
        ))}
      </div>

    </div>
  )
}

// ── ErrorCard — Flexbox column internally ─────────────────────────────────────

function ErrorCard({ error }) {
  const [expanded, setExpanded] = useState(false)
  const styles = SEVERITY_STYLES[error.confidence] || SEVERITY_STYLES.low

  return (
    <div className={`flex flex-col border ${styles.border} ${styles.bg} rounded-lg p-5 gap-3`}>

      {/* Card header — Flexbox row, space between */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded self-start ${styles.badge}`}>
            {styles.label}
          </span>
          <span className="text-xs text-gray-500">{error.module?.replace(/_/g, ' ')}</span>
        </div>
        <span className="text-sm font-bold text-gray-800 whitespace-nowrap">
          ${error.estimated_dollar_impact?.toFixed(2)}
        </span>
      </div>

      {/* Error details — Flexbox column */}
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-gray-900">{error.error_type}</h3>
        <p className="text-sm text-gray-700">{error.description}</p>
        <p className="text-xs text-gray-500">
          Affected line items: {error.line_items_affected?.join(', ')}
        </p>
      </div>

      {/* Explanation — toggleable */}
      {error.explanation ? (
        <div className="flex flex-col gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-700 underline self-start"
          >
            {expanded ? 'Hide explanation' : 'Show explanation & citations'}
          </button>
          {expanded && (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-gray-700">{error.explanation}</p>
              {error.citations?.map((c, i) => (
                c.url
                  ? <a key={i} href={c.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline">
                      📄 {c.source}{c.section ? ` — ${c.section}` : ''}
                    </a>
                  : <span key={i} className="text-xs text-gray-500">
                      📄 {c.source}{c.section ? ` — ${c.section}` : ''}
                    </span>
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
