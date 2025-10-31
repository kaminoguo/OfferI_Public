'use client';

import { useState, useEffect } from 'react';
import { X, User, LogOut, FileText, Download, Clock } from 'lucide-react';
import { useUser, useClerk } from '@clerk/nextjs';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/routing';
import LanguageSwitcher from './LanguageSwitcher';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

interface Consultation {
  payment_id: string;
  amount: number;
  status: string;
  job_id: string;
  created_at: string;
}

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const t = useTranslations();
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch consultation history when user is loaded
  useEffect(() => {
    if (isLoaded && user) {
      fetchConsultations();
    } else if (isLoaded && !user) {
      setLoading(false);
    }
  }, [isLoaded, user]);

  const fetchConsultations = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/payment/history/${user!.id}`);
      if (!response.ok) throw new Error('Failed to fetch consultations');
      const data = await response.json();
      setConsultations(data.consultations || []);
    } catch (error) {
      console.error('Error fetching consultations:', error);
      setConsultations([]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="w-64 bg-background border-r border-border flex flex-col">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-border">
        <h2 className="font-semibold text-foreground">{t('common.appName')}</h2>
        <button
          onClick={onToggle}
          className="p-1.5 rounded-md hover-minimal"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5 text-muted-foreground" />
        </button>
      </div>

      {/* Language Switcher */}
      <div className="px-4 pt-4 pb-2 border-b border-border">
        <LanguageSwitcher />
      </div>

      {/* Consultation History */}
      <div className="flex-1 p-4 overflow-y-auto">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-3">
          {t('sidebar.history')}
        </h3>

        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent"></div>
            <p className="text-xs text-muted-foreground mt-2">{t('sidebar.loading')}</p>
          </div>
        ) : !user ? (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">
              {t('sidebar.signInPrompt')}
            </p>
          </div>
        ) : consultations.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
            <p className="text-sm text-muted-foreground">
              {t('sidebar.noConsultations')}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t('sidebar.pdfsAppear')}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {consultations.map((consultation) => (
              <div
                key={consultation.job_id}
                className="group p-3 border border-border rounded-md hover:bg-secondary transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <FileText className="w-4 h-4 text-primary flex-shrink-0" />
                      <span className="text-sm font-medium text-foreground truncate">
                        {t('sidebar.consultation')}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">
                        {new Date(consultation.created_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </span>
                    </div>
                    <div className="mt-1">
                      <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                        consultation.status === 'PAID'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : consultation.status === 'PENDING_RETRY'
                          ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                          : 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400'
                      }`}>
                        {consultation.status}
                      </span>
                    </div>
                  </div>
                  <a
                    href={`${process.env.NEXT_PUBLIC_API_URL}/api/results/${consultation.job_id}/download`}
                    download
                    className="p-2 rounded-md hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors flex-shrink-0"
                    title="Download PDF"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* User Profile */}
      <div className="p-4 border-t border-border">
        {isLoaded && user ? (
          <>
            <Link
              href="/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-md hover-minimal cursor-pointer mb-2"
            >
              {user.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName || 'User'}
                  className="w-8 h-8 rounded-full"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <User className="w-5 h-5 text-muted-foreground" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {user.fullName || user.emailAddresses[0]?.emailAddress || 'User'}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {t('sidebar.pricing')}
                </p>
              </div>
            </Link>
            <button
              onClick={() => signOut()}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              {t('sidebar.signOut')}
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 px-3 py-2 rounded-md mb-2">
              <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                <User className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className="text-sm font-medium text-foreground">{t('sidebar.guestUser')}</span>
            </div>
            <div className="space-y-2">
              <Link
                href="/sign-in"
                className="block w-full text-center px-3 py-2 text-sm bg-primary text-white rounded-md hover:bg-primary/90 transition-colors"
              >
                {t('sidebar.signIn')}
              </Link>
              <Link
                href="/sign-up"
                className="block w-full text-center px-3 py-2 text-sm border border-border text-foreground rounded-md hover:bg-secondary transition-colors"
              >
                {t('sidebar.signUp')}
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
