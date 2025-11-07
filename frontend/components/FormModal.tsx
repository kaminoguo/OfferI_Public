'use client';

import { useState } from 'react';
import { X, ChevronDown, ChevronUp } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { FormData } from '@/types/form';
import { COUNTRY_GROUPS } from '@/constants/countries';

interface FormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { background: string }) => void;
}

// Initial form state
const initialFormData: FormData = {
  // Required
  school: '',
  schoolTier: '',
  major: '',
  gpa: '',
  targetCountry: '',
  // Optional
  regionPreference: '',
  internships: '',
  research: '',
  projects: '',
  competitions: '',
  careerGoals: '',
  languageScores: '',
  gpaRank: '',
  recommendations: '',
  other1: '',
  other2: '',
  other3: '',
};

export default function FormModal({ isOpen, onClose, onSubmit }: FormModalProps) {
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    target: true,
    experience: false,
    additional: false,
  });
  const t = useTranslations();

  if (!isOpen) return null;

  // Toggle section expansion
  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Validation: Check if all required fields are filled
  const isFormValid = () => {
    const gpaNum = parseFloat(formData.gpa);
    return (
      formData.school.trim().length > 0 &&
      formData.schoolTier.trim().length > 0 &&
      formData.major.trim().length > 0 &&
      formData.gpa.trim().length > 0 &&
      !isNaN(gpaNum) &&
      gpaNum >= 0 &&
      gpaNum <= 4 &&
      formData.targetCountry.length > 0
    );
  };

  // Serialize form data to text for MCP
  const serializeFormData = (data: FormData): string => {
    let text = `【基本学术信息】
出身院校：${data.school}
院校定位：${data.schoolTier}
专业：${data.major}
GPA（4分制）：${data.gpa}

【申请目标】
目标国家/地区：${data.targetCountry}`;

    if (data.regionPreference) {
      text += `\n地区偏好：${data.regionPreference}`;
    }

    // Experience section
    const experiences = [];
    if (data.internships) experiences.push(`实习经历：\n${data.internships}`);
    if (data.research) experiences.push(`科研经历：\n${data.research}`);
    if (data.projects) experiences.push(`项目经历：\n${data.projects}`);
    if (data.competitions) experiences.push(`竞赛获奖：\n${data.competitions}`);
    if (data.careerGoals) experiences.push(`职业规划：\n${data.careerGoals}`);

    if (experiences.length > 0) {
      text += `\n\n【背景经历】\n${experiences.join('\n\n')}`;
    }

    // Additional section
    const additional = [];
    if (data.languageScores) additional.push(`语言成绩：${data.languageScores}`);
    if (data.gpaRank) additional.push(`GPA排名：${data.gpaRank}`);
    if (data.recommendations) additional.push(`推荐信：${data.recommendations}`);
    if (data.other1) additional.push(`其他信息1：${data.other1}`);
    if (data.other2) additional.push(`其他信息2：${data.other2}`);
    if (data.other3) additional.push(`其他信息3：${data.other3}`);

    if (additional.length > 0) {
      text += `\n\n【补充信息】\n${additional.join('\n')}`;
    }

    return text.trim();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!isFormValid()) {
      return;
    }

    const serialized = serializeFormData(formData);
    onSubmit({ background: serialized });
    setFormData(initialFormData); // Clear form
  };

  const handleInputChange = (field: keyof FormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // Section component for collapsible panels
  const Section = ({ id, children }: { id: keyof typeof expandedSections; children: React.ReactNode }) => {
    const isExpanded = expandedSections[id];
    return (
      <div className="border border-border rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => toggleSection(id)}
          className="w-full px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors flex items-center justify-between"
        >
          <span className="font-semibold text-foreground">{t(`form.sections.${id}`)}</span>
          {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>
        {isExpanded && <div className="p-4 space-y-4">{children}</div>}
      </div>
    );
  };

  // Input field component
  const Field = ({
    name,
    required = false,
    type = 'text',
    rows,
  }: {
    name: keyof FormData;
    required?: boolean;
    type?: 'text' | 'number' | 'select' | 'textarea';
    rows?: number;
  }) => {
    const value = formData[name];
    const fieldT = (key: string) => t(`form.fields.${name}.${key}`);

    return (
      <div>
        <label className="block text-sm font-medium mb-1.5 text-foreground">
          {fieldT('label')}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {type === 'select' && name === 'targetCountry' ? (
          <select
            value={value}
            onChange={(e) => handleInputChange(name, e.target.value)}
            className="w-full bg-background border border-input rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            required={required}
          >
            <option value="">{fieldT('placeholder')}</option>
            {COUNTRY_GROUPS.map((group) => (
              <optgroup key={group.label} label={t(`form.countryGroups.${group.label.toLowerCase().replace(' ', '')}`)}>
                {group.countries.map((country) => (
                  <option key={country.value} value={country.value}>
                    {country.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        ) : type === 'textarea' ? (
          <textarea
            value={value}
            onChange={(e) => handleInputChange(name, e.target.value)}
            rows={rows || 3}
            className="w-full bg-background border border-input rounded-md px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            placeholder={fieldT('placeholder')}
            required={required}
          />
        ) : (
          <input
            type={type}
            value={value}
            onChange={(e) => handleInputChange(name, e.target.value)}
            step={type === 'number' ? '0.01' : undefined}
            min={type === 'number' && name === 'gpa' ? '0' : undefined}
            max={type === 'number' && name === 'gpa' ? '4' : undefined}
            className="w-full bg-background border border-input rounded-md px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder={fieldT('placeholder')}
            required={required}
          />
        )}
        {/* GPA validation hint */}
        {name === 'gpa' && value && (parseFloat(value) < 0 || parseFloat(value) > 4) && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{t('form.validation.gpaRange')}</p>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-soft">
        {/* Header */}
        <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-semibold text-foreground">{t('form.title')}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover-minimal"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Basic Academic Information */}
          <Section id="basic">
            <Field name="school" required />
            <Field name="schoolTier" required />
            <Field name="major" required />
            <Field name="gpa" required type="number" />
          </Section>

          {/* Application Goals */}
          <Section id="target">
            <Field name="targetCountry" required type="select" />
            <Field name="regionPreference" type="textarea" rows={2} />
          </Section>

          {/* Background & Experience */}
          <Section id="experience">
            <Field name="internships" type="textarea" />
            <Field name="research" type="textarea" />
            <Field name="projects" type="textarea" />
            <Field name="competitions" type="textarea" />
            <Field name="careerGoals" type="textarea" />
          </Section>

          {/* Additional Information */}
          <Section id="additional">
            <Field name="languageScores" />
            <Field name="gpaRank" />
            <Field name="recommendations" type="textarea" />
            <Field name="other1" type="textarea" />
            <Field name="other2" type="textarea" />
            <Field name="other3" type="textarea" />
          </Section>

          {/* Buttons */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 border border-border rounded-md text-foreground hover-minimal transition-colors"
            >
              {t('form.cancel')}
            </button>
            <button
              type="submit"
              disabled={!isFormValid()}
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
