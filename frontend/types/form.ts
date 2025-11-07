/**
 * Form data structure for study abroad consultation
 */
export interface FormData {
  // ===== Required Fields =====
  school: string;                    // 出身院校
  schoolTier: string;                // 出身院校定位 (e.g., 华五/港三/美Top 30/英G5/Russell Group)
  major: string;                     // 专业
  gpa: string;                       // GPA (4分制，0-4)
  targetCountry: string;             // 目标国家/地区

  // ===== Optional Fields =====
  regionPreference: string;          // 详细目标地区信息 (e.g., 只考虑湾区)
  internships: string;               // 实习经历
  research: string;                  // 科研经历（含论文）
  projects: string;                  // 项目经历
  competitions: string;              // 竞赛经历
  careerGoals: string;               // 职业规划/发展规划
  languageScores: string;            // 语言成绩 (TOEFL/IELTS/GRE/GMAT)
  gpaRank: string;                   // GPA排名 (e.g., 前5%)
  recommendations: string;           // 推荐信情况
  other1: string;                    // 其他信息1
  other2: string;                    // 其他信息2
  other3: string;                    // 其他信息3
}

/**
 * Validation rules for form fields
 */
export interface ValidationRules {
  [key: string]: {
    required?: boolean;
    minLength?: number;
    min?: number;
    max?: number;
    pattern?: RegExp;
  };
}

/**
 * Country option for dropdown
 */
export interface CountryOption {
  value: string;
  label: string;
  count?: number;  // Number of programs
}

/**
 * Form section configuration
 */
export interface FormSection {
  id: string;
  titleKey: string;
  fields: string[];
}
