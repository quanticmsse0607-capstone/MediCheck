import { Outlet, NavLink } from 'react-router-dom'

/**
 * Layout — shared wrapper rendered on every page.
 * NFR-19: Consistent visual design across all four pages.
 */
export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <NavLink to="/">
            <img src="/logo.png" alt="MediCheck" className="h-9 w-auto" />
          </NavLink>
          <span className="hidden md:block text-sm text-gray-500">
            AI-Powered Healthcare Bill Accuracy
          </span>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 py-10">
          <Outlet />
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-5xl mx-auto px-6 text-center text-xs text-gray-400">
          MediCheck — Quantic MSSE Capstone &nbsp;|&nbsp; All patient data is synthetic and generated for demonstration purposes only.
        </div>
      </footer>
    </div>
  )
}
