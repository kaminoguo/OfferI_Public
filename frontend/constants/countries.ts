/**
 * Country/Region list based on database (after cleaning)
 * All 103 countries with program counts
 */

export interface CountryOption {
  value: string;
  label: string;
  count: number;
}

export interface CountryGroup {
  label: string;
  countries: CountryOption[];
}

// Top 20 popular countries (500+ programs)
export const POPULAR_COUNTRIES: CountryOption[] = [
  { value: 'USA', label: 'United States (USA)', count: 14597 },
  { value: 'UK', label: 'United Kingdom (UK)', count: 8225 },
  { value: 'Australia', label: 'Australia', count: 6105 },
  { value: 'Canada', label: 'Canada', count: 1991 },
  { value: 'Netherlands', label: 'Netherlands', count: 1030 },
  { value: 'New Zealand', label: 'New Zealand', count: 1015 },
  { value: 'Germany', label: 'Germany', count: 880 },
  { value: 'Ireland', label: 'Ireland', count: 804 },
  { value: 'Italy', label: 'Italy', count: 607 },
  { value: 'China', label: 'China', count: 571 },
  { value: 'France', label: 'France', count: 545 },
  { value: 'South Africa', label: 'South Africa', count: 533 },
  { value: 'Japan', label: 'Japan', count: 490 },
  { value: 'India', label: 'India', count: 473 },
  { value: 'Sweden', label: 'Sweden', count: 438 },
  { value: 'Hong Kong (SAR)', label: 'Hong Kong (SAR)', count: 428 },
  { value: 'Pakistan', label: 'Pakistan', count: 300 },
  { value: 'Spain', label: 'Spain', count: 299 },
  { value: 'Switzerland', label: 'Switzerland', count: 242 },
  { value: 'South Korea', label: 'South Korea', count: 234 },
];

// Other countries (alphabetically sorted)
export const OTHER_COUNTRIES: CountryOption[] = [
  { value: 'Albania', label: 'Albania', count: 1 },
  { value: 'Armenia', label: 'Armenia', count: 4 },
  { value: 'Aruba', label: 'Aruba', count: 3 },
  { value: 'Austria', label: 'Austria', count: 96 },
  { value: 'Azerbaijan', label: 'Azerbaijan', count: 6 },
  { value: 'Bahrain', label: 'Bahrain', count: 10 },
  { value: 'Bangladesh', label: 'Bangladesh', count: 21 },
  { value: 'Belarus', label: 'Belarus', count: 10 },
  { value: 'Belgium', label: 'Belgium', count: 151 },
  { value: 'Bosnia and Herzegovina', label: 'Bosnia and Herzegovina', count: 3 },
  { value: 'Botswana', label: 'Botswana', count: 1 },
  { value: 'Brazil', label: 'Brazil', count: 2 },
  { value: 'Brunei', label: 'Brunei', count: 53 },
  { value: 'Bulgaria', label: 'Bulgaria', count: 37 },
  { value: 'Cayman Islands', label: 'Cayman Islands', count: 2 },
  { value: 'Croatia', label: 'Croatia', count: 27 },
  { value: 'Cyprus', label: 'Cyprus', count: 99 },
  { value: 'Czech Republic', label: 'Czech Republic', count: 87 },
  { value: 'Denmark', label: 'Denmark', count: 215 },
  { value: 'Egypt', label: 'Egypt', count: 52 },
  { value: 'Estonia', label: 'Estonia', count: 40 },
  { value: 'Ethiopia', label: 'Ethiopia', count: 1 },
  { value: 'Finland', label: 'Finland', count: 195 },
  { value: 'Ghana', label: 'Ghana', count: 34 },
  { value: 'Gibraltar', label: 'Gibraltar', count: 1 },
  { value: 'Greece', label: 'Greece', count: 24 },
  { value: 'Grenada', label: 'Grenada', count: 5 },
  { value: 'Guam', label: 'Guam', count: 11 },
  { value: 'Hungary', label: 'Hungary', count: 111 },
  { value: 'Iceland', label: 'Iceland', count: 52 },
  { value: 'Indonesia', label: 'Indonesia', count: 57 },
  { value: 'Iran', label: 'Iran', count: 167 },
  { value: 'Israel', label: 'Israel', count: 124 },
  { value: 'Jamaica', label: 'Jamaica', count: 141 },
  { value: 'Jordan', label: 'Jordan', count: 47 },
  { value: 'Kazakhstan', label: 'Kazakhstan', count: 102 },
  { value: 'Kenya', label: 'Kenya', count: 69 },
  { value: 'Kyrgyzstan', label: 'Kyrgyzstan', count: 1 },
  { value: 'Latvia', label: 'Latvia', count: 60 },
  { value: 'Lebanon', label: 'Lebanon', count: 44 },
  { value: 'Liechtenstein', label: 'Liechtenstein', count: 3 },
  { value: 'Lithuania', label: 'Lithuania', count: 114 },
  { value: 'Luxembourg', label: 'Luxembourg', count: 13 },
  { value: 'Macao (SAR)', label: 'Macao (SAR)', count: 50 },
  { value: 'Macedonia (FYROM)', label: 'Macedonia (FYROM)', count: 8 },
  { value: 'Malawi', label: 'Malawi', count: 6 },
  { value: 'Malaysia', label: 'Malaysia', count: 133 },
  { value: 'Malta', label: 'Malta', count: 117 },
  { value: 'Mauritius', label: 'Mauritius', count: 1 },
  { value: 'Mexico', label: 'Mexico', count: 6 },
  { value: 'Morocco', label: 'Morocco', count: 21 },
  { value: 'Namibia', label: 'Namibia', count: 29 },
  { value: 'Nepal', label: 'Nepal', count: 18 },
  { value: 'Nigeria', label: 'Nigeria', count: 64 },
  { value: 'Northern Cyprus', label: 'Northern Cyprus', count: 63 },
  { value: 'Norway', label: 'Norway', count: 108 },
  { value: 'Oman', label: 'Oman', count: 23 },
  { value: 'Palestinian Territory', label: 'Palestinian Territory', count: 62 },
  { value: 'Philippines', label: 'Philippines', count: 83 },
  { value: 'Poland', label: 'Poland', count: 72 },
  { value: 'Portugal', label: 'Portugal', count: 45 },
  { value: 'Puerto Rico', label: 'Puerto Rico', count: 8 },
  { value: 'Qatar', label: 'Qatar', count: 26 },
  { value: 'Romania', label: 'Romania', count: 68 },
  { value: 'Russia', label: 'Russia', count: 29 },
  { value: 'Rwanda', label: 'Rwanda', count: 1 },
  { value: 'Saudi Arabia', label: 'Saudi Arabia', count: 75 },
  { value: 'Senegal', label: 'Senegal', count: 3 },
  { value: 'Serbia', label: 'Serbia', count: 6 },
  { value: 'Singapore', label: 'Singapore', count: 173 },
  { value: 'Slovakia', label: 'Slovakia', count: 59 },
  { value: 'Slovenia', label: 'Slovenia', count: 30 },
  { value: 'Sri Lanka', label: 'Sri Lanka', count: 86 },
  { value: 'Syria', label: 'Syria', count: 46 },
  { value: 'Taiwan', label: 'Taiwan', count: 119 },
  { value: 'Thailand', label: 'Thailand', count: 190 },
  { value: 'Trinidad and Tobago', label: 'Trinidad and Tobago', count: 3 },
  { value: 'Turkey', label: 'Turkey', count: 216 },
  { value: 'Uganda', label: 'Uganda', count: 52 },
  { value: 'Ukraine', label: 'Ukraine', count: 51 },
  { value: 'United Arab Emirates', label: 'United Arab Emirates', count: 62 },
  { value: 'United States Virgin Islands', label: 'United States Virgin Islands', count: 7 },
  { value: 'Uzbekistan', label: 'Uzbekistan', count: 13 },
  { value: 'Vietnam', label: 'Vietnam', count: 25 },
  { value: 'Zambia', label: 'Zambia', count: 99 },
];

// Grouped structure for UI
export const COUNTRY_GROUPS: CountryGroup[] = [
  {
    label: 'Popular Countries',
    countries: POPULAR_COUNTRIES,
  },
  {
    label: 'Other Countries',
    countries: OTHER_COUNTRIES,
  },
];

// For backward compatibility
export const COUNTRIES = [...POPULAR_COUNTRIES, ...OTHER_COUNTRIES];
