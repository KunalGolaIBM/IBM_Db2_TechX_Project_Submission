'use client';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { api, ApiError } from '@/lib/api-client';

export interface QRDisplayProps {
  groupId: string;
  onPaymentSuccess?: () => void;
}

const PRESET_AMOUNTS = [
  { label: '₹100', minor: 10000 },
  { label: '₹500', minor: 50000 },
  { label: '₹1,000', minor: 100000 },
  { label: '₹2,000', minor: 200000 },
];

export function QRDisplay({ groupId, onPaymentSuccess }: QRDisplayProps) {
  const [selectedMinor, setSelectedMinor] = React.useState<number>(50000);
  const [customAmount, setCustomAmount] = React.useState<string>('');
  const [isSimulating, setIsSimulating] = React.useState<boolean>(false);
  const [statusMessage, setStatusMessage] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [imgError, setImgError] = React.useState<boolean>(false);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const qrEndpoint = `${apiBase}/api/v1/groups/${groupId}/payments/qr`;

  const handleSimulatePayment = async () => {
    setStatusMessage(null);
    let amountToPay = selectedMinor;

    if (customAmount) {
      const parsed = parseFloat(customAmount);
      if (isNaN(parsed) || parsed <= 0) {
        setStatusMessage({ type: 'error', text: 'Please enter a valid payment amount.' });
        return;
      }
      amountToPay = Math.round(parsed * 100);
    }

    setIsSimulating(true);
    try {
      await api.post(`/api/v1/groups/${groupId}/payments/demo`, {
        amount_minor: amountToPay,
        currency: 'INR',
        provider: 'UPI_SIMULATOR',
      });

      setStatusMessage({
        type: 'success',
        text: `Simulated payment of ₹${(amountToPay / 100).toLocaleString('en-IN')} processed successfully!`,
      });
      setCustomAmount('');
      if (onPaymentSuccess) {
        onPaymentSuccess();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setStatusMessage({ type: 'error', text: err.message || 'Payment simulation failed' });
      } else if (err instanceof Error) {
        setStatusMessage({ type: 'error', text: err.message });
      } else {
        setStatusMessage({ type: 'error', text: 'Payment simulation failed. Please try again.' });
      }
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* High-Visibility Banner */}
      <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-4 text-amber-900 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-amber-200 p-1.5 text-amber-800 shrink-0 mt-0.5">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 className="font-bold text-sm tracking-wide uppercase text-amber-950">
              DEMO PAYMENT ENTRY POINT — Simulated transactions for testing & demonstration
            </h4>
            <p className="mt-1 text-xs text-amber-800 leading-relaxed">
              No real funds will be deducted. All QR scans and simulated payments emit idempotent events directly into the IBM Db2 transaction ledger for group reconciliation.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* QR Code Card */}
        <Card className="md:col-span-5 flex flex-col items-center justify-center p-6 text-center border-slate-200">
          <CardHeader className="p-0 mb-4 text-center">
            <CardTitle className="text-base font-bold text-slate-900">
              Scan UPI QR Code
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">
              Supports Google Pay, PhonePe, Paytm, BHIM
            </p>
          </CardHeader>

          <div className="relative flex items-center justify-center w-52 h-52 rounded-xl border border-slate-200 bg-white p-3 shadow-inner">
            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={qrEndpoint}
                alt="Group UPI Payment QR Code"
                className="w-full h-full object-contain"
                onError={() => setImgError(true)}
              />
            ) : (
              // Fallback simulated QR graphic
              <div className="flex flex-col items-center justify-center text-center p-4">
                <svg className="w-24 h-24 text-slate-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                </svg>
                <span className="text-[11px] font-mono text-slate-500 mt-2">QR: {groupId.slice(0, 8)}</span>
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-col items-center space-y-1">
            <span className="text-xs font-semibold text-slate-700">Demo UPI ID</span>
            <div className="flex items-center gap-1.5 bg-slate-100 px-3 py-1 rounded-md text-xs font-mono font-medium text-slate-800 border border-slate-200">
              <span>splitsync-demo@upi</span>
            </div>
          </div>
        </Card>

        {/* Simulation Sandbox Card */}
        <Card className="md:col-span-7 border-slate-200">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-bold text-slate-900">
                Simulate UPI Payment
              </CardTitle>
              <Badge variant="warning" className="uppercase text-[10px]">
                Demo Sandbox
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Select an amount preset or specify custom rupees to trigger a webhook-verified payment event.
            </p>
          </CardHeader>

          <CardContent className="space-y-5">
            {statusMessage && (
              <div
                className={`rounded-md p-3 text-xs font-medium border ${
                  statusMessage.type === 'success'
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-rose-50 text-rose-800 border-rose-200'
                }`}
              >
                {statusMessage.text}
              </div>
            )}

            {/* Amount Presets */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Preset Amounts
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {PRESET_AMOUNTS.map((preset) => {
                  const isSelected = selectedMinor === preset.minor && !customAmount;
                  return (
                    <button
                      key={preset.minor}
                      type="button"
                      onClick={() => {
                        setSelectedMinor(preset.minor);
                        setCustomAmount('');
                      }}
                      className={`py-2 px-3 rounded-md text-sm font-semibold border transition-all ${
                        isSelected
                          ? 'bg-primary-600 text-white border-primary-600 shadow-sm'
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Custom Amount */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
                Or Custom Amount (₹)
              </label>
              <div className="relative rounded-md shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <span className="text-slate-500 sm:text-sm font-bold">₹</span>
                </div>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={customAmount}
                  onChange={(e) => setCustomAmount(e.target.value)}
                  placeholder="Enter custom amount in ₹"
                  className="block w-full rounded-md border border-slate-300 pl-8 pr-12 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                  <span className="text-xs text-slate-400">INR</span>
                </div>
              </div>
            </div>

            {/* Action Button */}
            <div className="pt-2">
              <Button
                type="button"
                variant="primary"
                className="w-full h-11 text-sm font-semibold"
                isLoading={isSimulating}
                onClick={handleSimulatePayment}
              >
                <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Simulate Payment Event
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
