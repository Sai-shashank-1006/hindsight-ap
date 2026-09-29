import { lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/layout/Layout';

// Each page is its own chunk: charts (Recharts) load only on the pages that draw them.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const InvoiceReview = lazy(() => import('./pages/InvoiceReview'));
const VendorMemory = lazy(() => import('./pages/VendorMemory'));
const NotFound = lazy(() => import('./pages/NotFound'));

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="review" element={<InvoiceReview />} />
          <Route path="vendors" element={<VendorMemory />} />
          <Route path="vendors/:name" element={<VendorMemory />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
