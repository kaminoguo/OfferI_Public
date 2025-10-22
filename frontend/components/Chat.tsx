'use client';

import { useState, useEffect } from 'react';
import { Menu, Download, Loader2 } from 'lucide-react';
import { useUser } from '@clerk/nextjs';
import { useSearchParams } from 'next/navigation';
import FormModal from './FormModal';
import PaymentModal from './PaymentModal';
import ProgressBar from './ProgressBar';
import { submitJob, getJobStatus, downloadPDF, verifyPayment, UserBackground } from '@/lib/api';

interface ChatProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function Chat({ isSidebarOpen, onToggleSidebar }: ChatProps) {
  const { user } = useUser();
  const searchParams = useSearchParams();
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [paymentId, setPaymentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [reportReady, setReportReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [canRetry, setCanRetry] = useState(false);
  const [lastBackground, setLastBackground] = useState<UserBackground | null>(null);

  // Check for payment_id in URL (returned from Stripe)
  useEffect(() => {
    const paymentIdFromUrl = searchParams?.get('payment_id');
    if (paymentIdFromUrl) {
      setPaymentId(paymentIdFromUrl);
      setIsFormModalOpen(true);
      // Clean up URL
      window.history.replaceState({}, '', '/');
    }
  }, [searchParams]);

  // Poll job status
  useEffect(() => {
    if (!jobId || reportReady || error) return;

    const pollStatus = async () => {
      try {
        const status = await getJobStatus(jobId);

        // Update progress if available
        if (status.progress !== undefined && status.progress !== null) {
          setProgress(status.progress);
        }

        if (status.status === 'completed') {
          setProgress(100);
          setIsLoading(false);
          setReportReady(true);
        } else if (status.status === 'failed') {
          setIsLoading(false);
          setError(status.error || '生成报告失败，请重试');

          // Check if payment allows retry
          if (paymentId) {
            checkRetryEligibility(paymentId);
          }
        }
      } catch (err) {
        console.error('Error polling status:', err);
      }
    };

    const interval = setInterval(pollStatus, 3000); // Poll every 3 seconds
    pollStatus(); // Initial poll

    return () => clearInterval(interval);
  }, [jobId, reportReady, error]);

  const checkRetryEligibility = async (paymentIdToCheck: string) => {
    try {
      const paymentStatus = await verifyPayment(paymentIdToCheck);

      // If payment is PENDING_RETRY, user can retry for free
      if (paymentStatus.valid && paymentStatus.status === 'pending_retry') {
        setCanRetry(true);
      } else {
        setCanRetry(false);
      }
    } catch (err) {
      console.error('Error checking retry eligibility:', err);
      setCanRetry(false);
    }
  };

  const handleStartConsultation = () => {
    if (!user) {
      setError('Please sign in to use this service');
      return;
    }
    // NEW FLOW: Open form first (not payment)
    setIsFormModalOpen(true);
  };

  const handlePaymentComplete = (paymentIdFromStripe: string) => {
    setPaymentId(paymentIdFromStripe);
    setIsPaymentModalOpen(false);
    // After payment, auto-submit the saved background
    if (lastBackground) {
      submitJobWithPayment(lastBackground, paymentIdFromStripe);
    }
  };

  const submitJobWithPayment = async (data: UserBackground, pId: string) => {
    try {
      setError(null);
      setCanRetry(false);
      setIsLoading(true);

      const response = await submitJob(data, pId);
      setJobId(response.job_id);
    } catch (error: any) {
      setIsLoading(false);

      if (error.status === 402) {
        setError('Payment not found or already used. Please make a new payment.');
        setIsPaymentModalOpen(true);
      } else if (error.status === 403) {
        setError('Payment verification failed. Please try again.');
        setIsPaymentModalOpen(true);
      } else {
        setError(error.message || '提交失败，请稍后重试');
      }
    }
  };

  const handleSubmit = async (data: UserBackground) => {
    if (!user) {
      setError('Please sign in to use this service');
      return;
    }

    // NEW FLOW: Save background first, then request payment
    const dataWithUser = {
      ...data,
      user_id: user.id,
    };
    setLastBackground(dataWithUser);
    setIsFormModalOpen(false);
    setIsPaymentModalOpen(true);
  };

  const handleDownload = async () => {
    if (!jobId) return;

    try {
      const blob = await downloadPDF(jobId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `offeri_report_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      setError('下载失败，请重试');
    }
  };

  const handleRetry = async () => {
    if (!lastBackground || !paymentId) {
      setError('No previous submission found');
      return;
    }

    try {
      setError(null);
      setCanRetry(false);
      setIsLoading(true);
      setProgress(0);

      // Resubmit with saved background data
      const response = await submitJob(lastBackground, paymentId);
      setJobId(response.job_id);
    } catch (error: any) {
      setIsLoading(false);

      // Handle payment errors
      if (error.status === 402) {
        setError('Payment not found or already used. Please make a new payment.');
        setCanRetry(false);
        setIsPaymentModalOpen(true);
      } else if (error.status === 403) {
        setError('Payment verification failed. Please try again.');
        setCanRetry(false);
        setIsPaymentModalOpen(true);
      } else {
        setError(error.message || '提交失败，请稍后重试');
        // Re-check retry eligibility after error
        if (paymentId) {
          checkRetryEligibility(paymentId);
        }
      }
    }
  };

  const handleReset = () => {
    setJobId(null);
    setPaymentId(null);
    setReportReady(false);
    setError(null);
    setIsLoading(false);
    setProgress(0);
    setCanRetry(false);
    setLastBackground(null);
  };

  return (
    <div className="flex-1 flex flex-col bg-background">
      {/* Header - Minimal ChatGPT style */}
      <div className="h-14 border-b border-border flex items-center px-4 gap-3 bg-background">
        {!isSidebarOpen && (
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-md hover-minimal"
            aria-label="Toggle sidebar"
          >
            <Menu className="w-5 h-5 text-foreground" />
          </button>
        )}
        <h1 className="text-lg font-semibold text-foreground">OfferI</h1>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex items-center justify-center overflow-y-auto">
        {!isLoading && !reportReady && !error && (
          /* Welcome State */
          <div className="text-center max-w-2xl px-8">
            <h2 className="text-3xl font-semibold mb-4 text-foreground">
              Welcome to OfferI
            </h2>
            <p className="text-muted-foreground mb-8 text-lg">
              AI-powered personalized study abroad consultant
            </p>
            <button
              onClick={handleStartConsultation}
              className="px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
            >
              Start Consultation ($6)
            </button>
            <p className="text-sm text-muted-foreground mt-4">
              Fill in your background → Pay $6 → Get your personalized report
            </p>
          </div>
        )}

        {isLoading && (
          /* Loading State - ChatGPT-style progress bar */
          <div className="text-center max-w-md px-8 w-full">
            <ProgressBar progress={progress} />
            <p className="text-sm text-muted-foreground mt-4">
              This may take 10-15 minutes
            </p>
          </div>
        )}

        {reportReady && jobId && (
          /* PDF Ready State */
          <div className="text-center max-w-md px-8">
            <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <Download className="w-10 h-10 text-primary" />
            </div>
            <h3 className="text-2xl font-semibold mb-3 text-foreground">
              Your report is ready!
            </h3>
            <p className="text-muted-foreground mb-6">
              Click the button below to download your personalized study abroad recommendation report
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleDownload}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
              >
                <Download className="w-5 h-5" />
                Download PDF Report
              </button>
              <button
                onClick={handleReset}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Start a new consultation
              </button>
            </div>
          </div>
        )}

        {error && (
          /* Error State */
          <div className="text-center max-w-md px-8">
            <div className="w-20 h-20 bg-red-50 dark:bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-red-500 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-2xl font-semibold mb-3 text-foreground">
              Something went wrong
            </h3>
            <p className="text-muted-foreground mb-6">
              {error}
            </p>

            {canRetry ? (
              /* User can retry for free */
              <div className="flex flex-col gap-3">
                <div className="px-4 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg mb-2">
                  <p className="text-sm text-green-700 dark:text-green-400 font-medium">
                    ✓ You can retry for free (no additional charge)
                  </p>
                </div>
                <button
                  onClick={handleRetry}
                  className="w-full px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
                >
                  Retry for Free
                </button>
                <button
                  onClick={handleReset}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Start a new consultation
                </button>
              </div>
            ) : (
              /* Normal reset button */
              <button
                onClick={handleReset}
                className="px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
              >
                Try Again
              </button>
            )}
          </div>
        )}
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        onPaymentComplete={handlePaymentComplete}
      />

      {/* Form Modal */}
      <FormModal
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
