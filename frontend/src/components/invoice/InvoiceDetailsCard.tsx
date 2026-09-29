import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Receipt } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import { QUEUE_STATUS_META } from '../../utils/constants';
import { cx, formatCurrency, formatDate, formatNumber } from '../../utils/formatters';
import type { Invoice, QueueStatus } from '../../types';

interface InvoiceDetailsCardProps {
  invoice: Invoice;
  status?: QueueStatus;
  footer?: ReactNode;
  className?: string;
}

function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={cx('min-w-0', wide && 'col-span-2')}>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-slate-900">{children}</dd>
    </div>
  );
}

export default function InvoiceDetailsCard({ invoice, status, footer, className = '' }: InvoiceDetailsCardProps) {
  const total = invoice.invoice_total ?? invoice.invoice_price * invoice.quantity;

  return (
    <BentoCard
      className={className}
      hoverable={false}
      icon={<Receipt className="h-5 w-5" aria-hidden="true" />}
      title={<span className="font-mono">{invoice.invoice_id}</span>}
      subtitle={`Dated ${formatDate(invoice.invoice_date)}`}
      action={
        status && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            <span className={cx('h-1.5 w-1.5 rounded-full', QUEUE_STATUS_META[status].dot)} aria-hidden="true" />
            {QUEUE_STATUS_META[status].label}
          </span>
        )
      }
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
        <Field label="Vendor" wide>
          <Link to={`/vendors/${encodeURIComponent(invoice.vendor)}`} className="text-lg font-semibold hover:text-blue-700">
            {invoice.vendor}
          </Link>
        </Field>
        {invoice.item && (
          <Field label="Item" wide>
            <span className="text-sm text-slate-700">{invoice.item}</span>
          </Field>
        )}
        <Field label="Unit price billed">
          <span className="tabular text-2xl font-bold">{formatCurrency(invoice.invoice_price)}</span>
        </Field>
        <Field label="Quantity">
          <span className="tabular text-2xl font-bold">{formatNumber(invoice.quantity)}</span>
        </Field>
        <Field label="Invoice total">
          <span className="tabular font-semibold">{formatCurrency(total)}</span>
        </Field>
        <Field label="Purchase order">
          {invoice.po_id ? (
            <span className="font-mono text-sm">{invoice.po_id}</span>
          ) : (
            <span className="text-sm text-slate-600">The vendor's PO on file</span>
          )}
        </Field>
        {invoice.po_price != null && (
          <Field label="PO price quoted on invoice" wide>
            <span className="tabular font-semibold">{formatCurrency(invoice.po_price)}</span>
            <span className="ml-2 text-xs text-slate-500">For reference only: checks use the PO record on file.</span>
          </Field>
        )}
      </dl>
      {footer && <div className="mt-6 border-t border-slate-100 pt-5">{footer}</div>}
    </BentoCard>
  );
}
