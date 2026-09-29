import { Suspense, useCallback, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';
import Sidebar from './Sidebar';
import LoadingSpinner from '../common/LoadingSpinner';
import { useHealth } from '../../hooks/useDashboard';

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { health, error, checking, refresh } = useHealth();
  const openMenu = useCallback(() => setMenuOpen(true), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-slate-50 to-slate-100">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-white px-4 py-2 font-medium text-blue-700 shadow focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <Navbar health={health} healthError={error} checking={checking} menuOpen={menuOpen} onOpenMenu={openMenu} />
      <div className="mx-auto flex max-w-[1440px]">
        <Sidebar
          open={menuOpen}
          onClose={closeMenu}
          health={health}
          healthError={error}
          checking={checking}
          onRefreshHealth={refresh}
        />
        <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<LoadingSpinner message="Loading page…" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
