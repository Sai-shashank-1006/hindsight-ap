import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type ReactNode } from 'react';
import { FileJson, Keyboard, Play, Upload } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import ErrorAlert from '../common/ErrorAlert';
import GradientButton from '../common/GradientButton';
import { cx, formatCurrency, formatDate, formatNumber, todayIso } from '../../utils/formatters';
import { EMPTY_INVOICE_FORM, parseInvoiceJson, validateInvoiceForm, type FieldErrors, type InvoiceFormValues } from '../../utils/validators';
import type { ProcessInvoiceRequest } from '../../types';

interface InvoiceUploadProps {
  onProcess: (invoice: ProcessInvoiceRequest) => void;
  processing?: boolean;
  vendorNames: string[];
  className?: string;
}

type Tab = 'form' | 'file';

interface FieldProps {
  id: keyof InvoiceFormValues;
  label: string;
  error?: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}

function Field({ id, label, error, hint, children, className = '' }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={`invoice-${id}`} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {error ? (
        <p id={`invoice-${id}-error`} className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  );
}

const inputClass = (invalid: boolean) =>
  cx(
    'h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-900 shadow-sm transition-colors placeholder:text-slate-400',
    'focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20',
    invalid ? 'border-red-400' : 'border-slate-300',
  );

export default function InvoiceUpload({ onProcess, processing = false, vendorNames, className = '' }: InvoiceUploadProps) {
  const [tab, setTab] = useState<Tab>('form');
  const [values, setValues] = useState<InvoiceFormValues>(() => ({ ...EMPTY_INVOICE_FORM, invoice_date: todayIso() }));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [fileInvoices, setFileInvoices] = useState<ProcessInvoiceRequest[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const update = (field: keyof InvoiceFormValues) => (event: ChangeEvent<HTMLInputElement>) => {
    setValues((current) => ({ ...current, [field]: event.target.value }));
    if (errors[field]) setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submitForm = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const { errors: found, invoice } = validateInvoiceForm(values);
    setErrors(found);
    if (invoice) onProcess(invoice);
  };

  const readFile = async (file: File) => {
    setFileName(file.name);
    const { invoices, error } = parseInvoiceJson(await file.text());
    setFileInvoices(invoices);
    setFileError(error);
  };

  const onFileChosen = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) void readFile(file);
    event.target.value = ''; // choosing the same file again should reload it
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void readFile(file);
  };

  const tabs: { id: Tab; label: string; icon: ReactNode }[] = [
    { id: 'form', label: 'Enter details', icon: <Keyboard className="h-4 w-4" aria-hidden="true" /> },
    { id: 'file', label: 'Upload JSON', icon: <FileJson className="h-4 w-4" aria-hidden="true" /> },
  ];

  return (
    <BentoCard className={className} hoverable={false} title="Enter an invoice" subtitle="The vendor needs a purchase order on file; checks always use that PO.">
      <div role="tablist" aria-label="How to enter the invoice" className="mb-6 inline-flex self-start rounded-xl bg-slate-100 p-1">
        {tabs.map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cx(
              'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition-all',
              tab === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900',
            )}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {tab === 'form' ? (
        <form onSubmit={submitForm} noValidate className="grid gap-5 sm:grid-cols-2">
          <Field id="invoice_id" label="Invoice ID" error={errors.invoice_id}>
            <input
              id="invoice-invoice_id"
              value={values.invoice_id}
              onChange={update('invoice_id')}
              placeholder="INV-1042"
              autoComplete="off"
              aria-invalid={Boolean(errors.invoice_id)}
              className={inputClass(Boolean(errors.invoice_id))}
            />
          </Field>
          <Field id="vendor" label="Vendor" error={errors.vendor} hint={vendorNames.length ? `${vendorNames.length} vendors on file` : undefined}>
            <input
              id="invoice-vendor"
              value={values.vendor}
              onChange={update('vendor')}
              list="invoice-vendor-options"
              placeholder="ABC Pharma"
              autoComplete="off"
              aria-invalid={Boolean(errors.vendor)}
              className={inputClass(Boolean(errors.vendor))}
            />
            <datalist id="invoice-vendor-options">
              {vendorNames.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </Field>
          <Field id="invoice_price" label="Unit price billed (₹)" error={errors.invoice_price}>
            <input
              id="invoice-invoice_price"
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={values.invoice_price}
              onChange={update('invoice_price')}
              placeholder="550"
              aria-invalid={Boolean(errors.invoice_price)}
              className={inputClass(Boolean(errors.invoice_price))}
            />
          </Field>
          <Field id="quantity" label="Quantity" error={errors.quantity}>
            <input
              id="invoice-quantity"
              type="number"
              inputMode="numeric"
              min="1"
              step="1"
              value={values.quantity}
              onChange={update('quantity')}
              placeholder="100"
              aria-invalid={Boolean(errors.quantity)}
              className={inputClass(Boolean(errors.quantity))}
            />
          </Field>
          <Field id="invoice_date" label="Invoice date" error={errors.invoice_date}>
            <input
              id="invoice-invoice_date"
              type="date"
              value={values.invoice_date}
              onChange={update('invoice_date')}
              aria-invalid={Boolean(errors.invoice_date)}
              className={inputClass(Boolean(errors.invoice_date))}
            />
          </Field>
          <Field id="po_price" label="PO price quoted on the invoice (optional)" error={errors.po_price} hint="For reference only: the PO record on file wins.">
            <input
              id="invoice-po_price"
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={values.po_price}
              onChange={update('po_price')}
              placeholder="500"
              aria-invalid={Boolean(errors.po_price)}
              className={inputClass(Boolean(errors.po_price))}
            />
          </Field>
          <div className="sm:col-span-2">
            <GradientButton
              type="submit"
              size="lg"
              loading={processing}
              loadingText="Checking rules, memory and model…"
              icon={<Play className="h-4 w-4" aria-hidden="true" />}
            >
              Run the agent
            </GradientButton>
          </div>
        </form>
      ) : (
        <div className="space-y-5">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cx(
              'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors',
              dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50/60',
            )}
          >
            <Upload className="h-8 w-8 text-slate-400" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-slate-900">Drop a .json file here</p>
            <p className="mt-1 text-xs text-slate-500">One invoice object, or a list of them, in the same shape as the form</p>
            <input ref={fileInput} type="file" accept=".json,application/json" onChange={onFileChosen} className="sr-only" id="invoice-file" />
            <GradientButton variant="secondary" size="sm" className="mt-4" onClick={() => fileInput.current?.click()}>
              Choose file
            </GradientButton>
          </div>

          <ErrorAlert error={fileError} title={fileName ? `Couldn't read ${fileName}` : "Couldn't read the file"} />

          {fileInvoices.length > 0 && (
            <div>
              <p className="text-sm text-slate-600">
                <span className="font-semibold text-slate-900">{fileInvoices.length}</span> invoice{fileInvoices.length === 1 ? '' : 's'} in{' '}
                {fileName}. Pick one to review.
              </p>
              <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
                {fileInvoices.map((invoice, index) => (
                  <li key={`${invoice.invoice_id}-${index}`} className="flex flex-wrap items-center justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-semibold text-slate-900">{invoice.invoice_id}</p>
                      <p className="tabular text-xs text-slate-500">
                        {invoice.vendor} · {formatNumber(invoice.quantity)} × {formatCurrency(invoice.invoice_price)} ·{' '}
                        {formatDate(invoice.invoice_date)}
                      </p>
                    </div>
                    <GradientButton size="sm" onClick={() => onProcess(invoice)} disabled={processing} icon={<Play className="h-3.5 w-3.5" aria-hidden="true" />}>
                      Review
                    </GradientButton>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </BentoCard>
  );
}
