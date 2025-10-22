'use client';

import { useState } from 'react';
import { X } from 'lucide-react';

interface FormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { background: string }) => void;
}

export default function FormModal({ isOpen, onClose, onSubmit }: FormModalProps) {
  const [background, setBackground] = useState('');

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
            Tell us about your background
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
              Your background *
            </label>
            <p className="text-sm text-muted-foreground mb-3">
              Include: university, GPA, major, projects, internships, papers/competitions,
              recommendations, career goals, target countries/regions, budget, etc.
            </p>
            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={12}
              className="w-full bg-background border border-input rounded-md px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              placeholder="Example: I'm studying ELEC+AI at HKUST with GPA 3.0, had 3-month Google TPM internship, 9-month OpenAI TPM internship, graduated 1 year early, have 4 GitHub projects with 100+ stars each (maintained for 1+ year), 3 major hackathon awards, weak recommendation from AI expert, strong recommendation from OpenAI. Aiming for Product Manager / AI CPO, considering Hong Kong, Japan, USA schools, unlimited budget"
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
              Cancel
            </button>
            <button
              type="submit"
              disabled={!background.trim()}
              className="flex-1 px-6 py-3 bg-primary text-white rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Continue to Payment
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
