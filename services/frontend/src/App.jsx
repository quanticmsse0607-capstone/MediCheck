import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Upload from './pages/Upload'
import FieldConfirmation from './pages/FieldConfirmation'
import ErrorReport from './pages/ErrorReport'
import DisputeLetter from './pages/DisputeLetter'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Upload />} />
          <Route path="confirm/:sessionId" element={<FieldConfirmation />} />
          <Route path="report/:sessionId" element={<ErrorReport />} />
          <Route path="letter/:sessionId" element={<DisputeLetter />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}