import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import ConfirmPage from './pages/ConfirmPage';
import ReportPage from './pages/ReportPage';
import LetterPage from './pages/LetterPage';
import Navbar from './components/Navbar';

/**
 * App — root component
 *
 * Defines the four-page routing structure:
 *   /          → UploadPage   (Home — document upload)
 *   /confirm   → ConfirmPage  (Field confirmation)
 *   /report    → ReportPage   (Error report results)
 *   /letter    → LetterPage   (Dispute letter preview and download)
 *
 * Session state is passed via React Router location state between pages.
 * The session_id returned by POST /upload is the key that threads all pages together.
 */
function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/confirm" element={<ConfirmPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/letter" element={<LetterPage />} />
            {/* Catch-all — redirect unknown paths to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
