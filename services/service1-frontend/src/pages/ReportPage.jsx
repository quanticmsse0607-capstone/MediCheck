import { useNavigate, useLocation } from 'react-router-dom';
import { requestLetter } from '../services/api';
import { useState } from 'react';

/**
 * ReportPage — Screen 3
 *
 * Requirements covered:
 *   FR-10  All four checks produce a result or explicit all-clear
 *   FR-16  Each error result includes all six required fields
 *   FR-18  Plain-English explanation with citation for each error
 *   NFR-01 Analysis results displayed within 30 seconds
 *   NFR-02 Graceful degradation when RAG unavailable
 *   NFR-19 Consistent design across all four pages
 *   NFR-20 Severity shown by colour indicator AND text label
 *   NFR-22 Responsive layout
 */
function ReportPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId, results } = location.state || {};

  const [letterLoading, setLetterLoading] = useState(false);
  const [letterError, setLetterError] = useState(null);

  // Redirect to upload if arrived without session data
  if (!sessionId || !results) {
    navigate('/', { replace: true });
    return null;
  }

  const handleGenerateLetter = async () => {
    setLetterError(null);
    setLetterLoading(true);
    try {
      const letterData = await requestLetter(sessionId);
      navigate('/letter', { state: { sessionId, letterData } });
    } catch (err) {
      setLetterError(err.message || 'Letter generation failed. Please try again.');
    } finally {
      setLetterLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">

      {/* Summary header */}
      <div className="mb-8">
        {results.all_clear ? (
          <div className="p-6 bg-severity-info-bg border border-green-200 rounded-lg">
            <h1 className="text-2xl font-bold text-green-800 mb-2">
              ✓ No obvious billing errors found
            </h1>
            <p className="text-green-700">
              We checked your bill for duplicate charges, Medicare rate outliers,
              EOB mismatches, and No Surprises Act violations. Everything looks normal.
            </p>
          </div>
        ) : (
          <div>
            <h1 className="text-2xl font-bold text-brand-dark mb-1">
              {results.total_errors} error{results.total_errors !== 1 ? 's' : ''} found
            </h1>
            <p className="text-xl text-green-700 font-semibold">
              ${results.total_estimated_savings?.toFixed(2)} potential savings
            </p>
          </div>
        )}
      </div>

      {/* RAG unavailable notice — NFR-02 */}
      {!results.rag_available && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded">
          <p className="text-sm text-amber-800">
            ⚠ Explanations are temporarily unavailable. Error detection results are shown below.
            Refresh the page to retry loading explanations.
          </p>
        </div>
      )}

      {/* Error cards — NFR-20: colour + text label */}
      <div className="space-y-4 mb-8">
        {results.errors?.map((error) => (
          <ErrorCard key={error.error_id} error={error} />
        ))}
      </div>

      {/* Actions */}
      {!results.all_clear && (
        <div>
          {letterError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {letterError}
            </div>
          )}
          <button
            onClick={handleGenerateLetter}
            disabled={letterLoading}
            className="w-full py-3 px-6 bg-brand-primary text-white font-semibold rounded
                       hover:bg-brand-dark disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors"
          >
            {letterLoading ? 'Generating dispute letter…' : 'Generate Dispute Letter'}
          </button>
        </div>
      )}

    </div>
  );
}

/**
 * ErrorCard — displays a single detected error
 * NFR-20: colour-coded by severity with text label
 * FR-16: shows all six required error result fields
 */
function ErrorCard({ error }) {
  const [expanded, setExpanded] = useState(false);

  // NFR-20: severity thresholds
  const severity = error.estimated_dollar_impact > 500
    ? { label: 'High Impact', bg: 'bg-severity-high-bg', border: 'border-red-200', text: 'text-red-700', badge: 'bg-red-100 text-red-700' }
    : error.estimated_dollar_impact >= 100
    ? { label: 'Medium Impact', bg: 'bg-severity-medium-bg', border: 'border-orange-200', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-700' }
    : { label: 'Informational', bg: 'bg-severity-info-bg', border: 'border-green-200', text: 'text-green-700', badge: 'bg-green-100 text-green-700' };

  return (
    <div className={`border rounded-lg p-5 ${severity.bg} ${severity.border}`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className={`text-xs font-semibold uppercase tracking-wide px-2 py-1 rounded ${severity.badge}`}>
            {severity.label}
          </span>
          <h3 className={`text-base font-semibold mt-2 ${severity.text}`}>
            {error.error_type}
          </h3>
        </div>
        <div className="text-right">
          <p className={`text-lg font-bold ${severity.text}`}>
            ${error.estimated_dollar_impact?.toFixed(2)}
          </p>
          <p className="text-xs text-gray-500">estimated savings</p>
        </div>
      </div>

      <p className="text-sm text-gray-700 mb-3">{error.description}</p>

      <p className="text-xs text-gray-500 mb-3">
        Affects line item{error.line_items_affected?.length !== 1 ? 's' : ''}{' '}
        {error.line_items_affected?.join(', ')} ·{' '}
        Confidence: <span className="font-medium">{error.confidence}</span>
      </p>

      {/* RAG explanation — FR-18 */}
      {error.explanation && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-brand-primary font-medium hover:underline"
          >
            {expanded ? 'Hide explanation ▲' : 'Show explanation ▼'}
          </button>
          {expanded && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-sm text-gray-700 mb-2">{error.explanation}</p>
              {error.citations?.map((citation, i) => (
                <p key={i} className="text-xs text-gray-500">
                  Source:{' '}
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brand-primary hover:underline"
                  >
                    {citation.source}{citation.section ? ` — ${citation.section}` : ''}
                  </a>
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ReportPage;
