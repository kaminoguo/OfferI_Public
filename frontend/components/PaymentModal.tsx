'use client';

import { useState } from 'react';
import { X, Loader2, DollarSign } from 'lucide-react';
import { useUser } from '@clerk/nextjs';

type PaymentTier = 'basic' | 'update' | 'advanced';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPaymentComplete: (paymentId: string) => void;
  tier?: PaymentTier;  // Default to 'basic'
}

// Tier configuration
const TIER_CONFIG = {
  basic: {
    price: 9,
    name: 'Basic Consultation',
    description: 'AI-powered study abroad consultation with basic recommendations',
    features: [
      'AI-powered personalized analysis of your background',
      'Comprehensive program recommendations (3-5 web searches)',
      'Professional PDF report you can download and share',
      'Free retry if report generation fails'
    ]
  },
  update: {
    price: 39.99,
    name: 'Update to Advanced',
    description: 'Upgrade your basic report to get detailed program research',
    features: [
      'All basic features included',
      'Deep Exa research for 20-30 programs (40+ searches)',
      'Detailed program features and student experience analysis',
      'Suitability analysis for each recommended program',
      'Career outcomes and employment data'
    ]
  },
  advanced: {
    price: 49.99,
    name: 'Advanced Consultation',
    description: 'Comprehensive analysis with extensive program research from the start',
    features: [
      'AI-powered personalized analysis of your background',
      'Deep Exa research for 20-30 programs (40+ searches)',
      'Detailed program features and student experience analysis',
      'Suitability analysis for each recommended program',
      'Career outcomes and employment data',
      'Professional PDF report you can download and share',
      'Free retry if report generation fails'
    ]
  }
};

export default function PaymentModal({ isOpen, onClose, onPaymentComplete, tier = 'basic' }: PaymentModalProps) {
  const { user } = useUser();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const config = TIER_CONFIG[tier];

  if (!isOpen) return null;

  const handlePayment = async () => {
    if (!user) {
      setError('Please sign in to continue');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/payment/create-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user.id,
          tier: tier,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create payment session');
      }

      const data = await response.json();

      // Redirect to Stripe checkout
      window.location.href = data.checkout_url;
    } catch (error) {
      console.error('Payment error:', error);
      setError('Failed to initiate payment. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-lg shadow-soft max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">{config.name}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-md hover-minimal"
            aria-label="Close modal"
            disabled={loading}
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <DollarSign className="w-8 h-8 text-primary" />
            </div>
            <div className="mb-2">
              <span className="text-4xl font-bold text-foreground">${config.price}</span>
            </div>
            <p className="text-sm text-muted-foreground">
              {config.description}
            </p>
          </div>

          <div className="space-y-3 mb-6 text-sm">
            {config.features.map((feature, index) => (
              <div key={index} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0"></div>
                <p className="text-foreground">{feature}</p>
              </div>
            ))}
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <button
            onClick={handlePayment}
            disabled={loading}
            className="w-full py-3 bg-primary text-white rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Redirecting to payment...
              </>
            ) : (
              <>
                <DollarSign className="w-5 h-5" />
                Pay ${config.price} & Continue
              </>
            )}
          </button>

          <p className="text-xs text-center text-muted-foreground mt-4">
            Secure payment powered by Stripe
          </p>
        </div>
      </div>
    </div>
  );
}
