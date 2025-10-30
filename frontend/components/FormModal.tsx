'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { useTranslations } from 'next-intl';

interface FormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { background: string }) => void;
}

export default function FormModal({ isOpen, onClose, onSubmit }: FormModalProps) {
  const [background, setBackground] = useState('');
  const t = useTranslations();

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ background });
    setBackground(''); // Clear after submit
  };

  return (
    /* Modal Overlay */
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      {/* Modal Card - Clean White */}
      <div className="bg-background border border-border rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-soft">
        {/* Header */}
        <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">
            {t('form.title')}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover-minimal"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2 text-foreground">
              {t('form.label')}
            </label>
            <p className="text-sm text-muted-foreground mb-3">
              {t('form.description.intro')}
              <br />
              <span className="font-medium">{t('form.description.academic')}:</span> {t('form.description.academicDetails')}
              <br />
              <span className="font-medium">{t('form.description.experience')}:</span> {t('form.description.experienceDetails')}
              <br />
              <span className="font-medium">{t('form.description.entrepreneurship')}:</span> {t('form.description.entrepreneurshipDetails')}
              <br />
              <span className="font-medium">{t('form.description.goals')}:</span> {t('form.description.goalsDetails')}
              <br />
              <span className="font-medium">{t('form.description.other')}:</span> {t('form.description.otherDetails')}
            </p>

            {/* Important Reminders */}
            <div className="mb-3 space-y-2">
              <div className="flex gap-2 items-start bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md px-3 py-2">
                <span className="text-blue-600 dark:text-blue-400 font-semibold shrink-0">💡</span>
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  <span className="font-semibold">{t('form.reminder.focus.title')}</span> {t('form.reminder.focus.description')}
                </p>
              </div>

              <div className="flex gap-2 items-start bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
                <span className="text-amber-600 dark:text-amber-400 font-semibold shrink-0">⚡</span>
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  <span className="font-semibold">{t('form.reminder.quality.title')}</span> {t('form.reminder.quality.description')}
                </p>
              </div>
            </div>

            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={12}
              className="w-full bg-background border border-input rounded-md px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              placeholder={t('form.placeholder')}
              required
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 border border-border rounded-md text-foreground hover-minimal transition-colors"
            >
              {t('form.cancel')}
            </button>
            <button
              type="submit"
              disabled={!background.trim()}
              className="flex-1 px-6 py-3 bg-primary text-white rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('form.submit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
