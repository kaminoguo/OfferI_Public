#!/usr/bin/env node

/**
 * Translation Completeness Checker
 *
 * This script validates that all translation files have:
 * 1. The same keys as the base language (English)
 * 2. No extra or missing keys
 * 3. No empty translation values
 *
 * Usage: node scripts/check-translations.js
 */

const fs = require('fs');
const path = require('path');

const MESSAGES_DIR = path.join(__dirname, '../messages');
const BASE_LANG = 'en';

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

// Recursively get all keys from an object with dot notation
function getAllKeys(obj, prefix = '') {
  const keys = [];

  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      keys.push(...getAllKeys(value, fullKey));
    } else {
      keys.push(fullKey);
    }
  }

  return keys;
}

// Get a value from nested object using dot notation
function getNestedValue(obj, path) {
  return path.split('.').reduce((current, key) => current?.[key], obj);
}

// Load all translation files
function loadTranslations() {
  const files = fs.readdirSync(MESSAGES_DIR).filter(f => f.endsWith('.json'));
  const translations = {};

  for (const file of files) {
    const lang = file.replace('.json', '');
    const content = fs.readFileSync(path.join(MESSAGES_DIR, file), 'utf-8');
    translations[lang] = JSON.parse(content);
  }

  return translations;
}

// Main validation function
function validateTranslations() {
  console.log(`${colors.cyan}🔍 Checking translation files...${colors.reset}\n`);

  const translations = loadTranslations();
  const languages = Object.keys(translations);

  if (!translations[BASE_LANG]) {
    console.error(`${colors.red}❌ Base language file (${BASE_LANG}.json) not found!${colors.reset}`);
    process.exit(1);
  }

  const baseKeys = getAllKeys(translations[BASE_LANG]);
  console.log(`${colors.blue}📝 Base language (${BASE_LANG}) has ${baseKeys.length} keys${colors.reset}\n`);

  let hasErrors = false;
  const results = [];

  // Check each language
  for (const lang of languages) {
    if (lang === BASE_LANG) continue;

    const langKeys = getAllKeys(translations[lang]);
    const missingKeys = baseKeys.filter(key => !langKeys.includes(key));
    const extraKeys = langKeys.filter(key => !baseKeys.includes(key));

    // Check for empty values
    const emptyKeys = langKeys.filter(key => {
      const value = getNestedValue(translations[lang], key);
      return value === '' || value === null || value === undefined;
    });

    const status = {
      lang,
      total: langKeys.length,
      missing: missingKeys,
      extra: extraKeys,
      empty: emptyKeys,
      complete: missingKeys.length === 0 && extraKeys.length === 0 && emptyKeys.length === 0
    };

    results.push(status);

    if (!status.complete) {
      hasErrors = true;
    }
  }

  // Print results
  for (const result of results) {
    const icon = result.complete ? '✅' : '❌';
    const color = result.complete ? colors.green : colors.red;

    console.log(`${color}${icon} ${result.lang.toUpperCase()} (${result.total} keys)${colors.reset}`);

    if (result.missing.length > 0) {
      console.log(`  ${colors.red}Missing ${result.missing.length} keys:${colors.reset}`);
      result.missing.forEach(key => console.log(`    - ${key}`));
    }

    if (result.extra.length > 0) {
      console.log(`  ${colors.yellow}Extra ${result.extra.length} keys:${colors.reset}`);
      result.extra.forEach(key => console.log(`    - ${key}`));
    }

    if (result.empty.length > 0) {
      console.log(`  ${colors.yellow}Empty ${result.empty.length} values:${colors.reset}`);
      result.empty.forEach(key => console.log(`    - ${key}`));
    }

    if (result.complete) {
      console.log(`  ${colors.green}All keys present and valid!${colors.reset}`);
    }

    console.log('');
  }

  // Summary
  const completeCount = results.filter(r => r.complete).length;
  const totalLangs = results.length;

  console.log(`${colors.cyan}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${colors.reset}`);
  console.log(`${colors.cyan}Summary: ${completeCount}/${totalLangs} languages complete${colors.reset}`);
  console.log(`${colors.cyan}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${colors.reset}\n`);

  if (hasErrors) {
    console.error(`${colors.red}❌ Translation validation failed!${colors.reset}`);
    console.error(`${colors.yellow}💡 Tip: Copy missing keys from ${BASE_LANG}.json and translate them.${colors.reset}\n`);
    process.exit(1);
  } else {
    console.log(`${colors.green}✅ All translations are complete and valid!${colors.reset}\n`);
    process.exit(0);
  }
}

// Run validation
try {
  validateTranslations();
} catch (error) {
  console.error(`${colors.red}❌ Error: ${error.message}${colors.reset}`);
  process.exit(1);
}
