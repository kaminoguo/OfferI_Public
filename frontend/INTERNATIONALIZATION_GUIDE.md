# OfferI 国际化实施指南 (i18n Implementation Guide)

## 📋 目标
支持8种语言，采用next-intl库，确保无遗漏、方便维护。

## 🌍 推荐的8种语言

基于留学市场分析和目标用户分布：

1. **English (en)** - 全球通用语言，美国/英国/澳洲留学市场
2. **简体中文 (zh-CN)** - 中国大陆学生（最大市场）
3. **繁体中文 (zh-TW)** - 台湾、香港学生
4. **日本語 (ja)** - 日本学生赴海外 + 赴日留学市场
5. **한국어 (ko)** - 韩国学生市场
6. **Español (es)** - 西班牙、拉美学生市场
7. **Français (fr)** - 法国、加拿大法语区、非洲法语区
8. **Deutsch (de)** - 德国、奥地利、瑞士学生市场

## 🎯 实施步骤

### Step 1: 安装依赖

```bash
cd frontend
npm install next-intl
```

### Step 2: 创建目录结构

```
frontend/
├── messages/                    # 翻译文件目录
│   ├── en.json                 # 英语
│   ├── zh-CN.json              # 简体中文
│   ├── zh-TW.json              # 繁体中文
│   ├── ja.json                 # 日语
│   ├── ko.json                 # 韩语
│   ├── es.json                 # 西班牙语
│   ├── fr.json                 # 法语
│   └── de.json                 # 德语
├── src/
│   ├── i18n/
│   │   ├── request.ts          # next-intl配置
│   │   └── routing.ts          # 路由配置
│   ├── middleware.ts           # 语言检测中间件
│   └── app/
│       ├── [locale]/           # 动态语言路由
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   └── ...
```

### Step 3: 配置文件

#### 3.1 `i18n/routing.ts`

```typescript
import {defineRouting} from 'next-intl/routing';
import {createNavigation} from 'next-intl/navigation';

export const routing = defineRouting({
  // 支持的语言列表
  locales: ['en', 'zh-CN', 'zh-TW', 'ja', 'ko', 'es', 'fr', 'de'],

  // 默认语言
  defaultLocale: 'en',

  // URL路径前缀策略：'as-needed'表示默认语言不显示前缀
  // en:      /
  // zh-CN:   /zh-CN
  // ja:      /ja
  localePrefix: 'as-needed'
});

// 导出类型安全的导航组件
export const {Link, redirect, usePathname, useRouter, getPathname} =
  createNavigation(routing);
```

#### 3.2 `i18n/request.ts`

```typescript
import {getRequestConfig} from 'next-intl/server';
import {routing} from './routing';

export default getRequestConfig(async ({requestLocale}) => {
  // 通常对应URL中的`[locale]`段
  let locale = await requestLocale;

  // 确保传入的locale有效
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = routing.defaultLocale;
  }

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default
  };
});
```

#### 3.3 `middleware.ts`

```typescript
import createMiddleware from 'next-intl/middleware';
import {routing} from './i18n/routing';

export default createMiddleware(routing);

export const config = {
  // 匹配所有路径除了API、静态文件等
  matcher: [
    // 匹配所有路径
    '/((?!api|_next|_vercel|.*\\..*).*)',
    // 但也包括根路径
    '/'
  ]
};
```

#### 3.4 `next.config.js`

```javascript
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

/** @type {import('next').NextConfig} */
const nextConfig = {
  // 你的现有配置
};

export default withNextIntl(nextConfig);
```

### Step 4: 重构App Router结构

#### 4.1 移动现有页面到 `[locale]` 目录

```bash
mkdir -p app/[locale]
mv app/layout.tsx app/[locale]/
mv app/page.tsx app/[locale]/
mv app/settings app/[locale]/
mv app/sign-in app/[locale]/
mv app/sign-up app/[locale]/
```

#### 4.2 更新 `app/[locale]/layout.tsx`

```tsx
import {NextIntlClientProvider} from 'next-intl';
import {getMessages} from 'next-intl/server';
import {notFound} from 'next/navigation';
import {routing} from '@/i18n/routing';

export function generateStaticParams() {
  return routing.locales.map((locale) => ({locale}));
}

export default async function LocaleLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;

  // 确保传入的locale有效
  if (!routing.locales.includes(locale as any)) {
    notFound();
  }

  // 获取消息（服务端）
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
```

### Step 5: 创建翻译文件模板

#### 5.1 识别所有需要翻译的文本

运行以下命令提取所有硬编码文本：

```bash
# 查找所有包含英文文本的组件
grep -r "Welcome to OfferI\|Start Consultation\|Fill in your background" components/ app/ --include="*.tsx" --include="*.ts"
```

#### 5.2 创建 `messages/en.json` (英语基础模板)

```json
{
  "common": {
    "appName": "OfferI",
    "email": "lyrica2333@gmail.com"
  },
  "welcome": {
    "title": "Welcome to OfferI",
    "subtitle": "AI-powered personalized study abroad consultant",
    "startButton": "Start Consultation ($6)",
    "flow": "Fill in your background → Pay $6 → Get your personalized report"
  },
  "info": {
    "title": "Important Information",
    "autoQueue": {
      "icon": "⏱️",
      "title": "Auto-queuing system:",
      "description": "If the queue is full, your request will be automatically queued. You'll receive your PDF report once generation completes—no need to keep the page open."
    },
    "retries": {
      "icon": "🔄",
      "title": "Unlimited free retries:",
      "description": "If generation fails for any reason, you can retry for free without additional charges."
    },
    "support": {
      "icon": "💬",
      "title": "Need help?",
      "description": "If you encounter any issues, please contact us with a screenshot at {email}"
    },
    "mvp": {
      "icon": "🚧",
      "title": "MVP Stage:",
      "description": "This product is still in MVP stage, but we're already achieving good results. Your feedback helps us improve!"
    },
    "collaboration": {
      "icon": "🤝",
      "title": "Interested in collaboration?",
      "description": "If you'd like to partner with us or provide support, please reach out at {email}"
    }
  },
  "form": {
    "title": "Tell us about your background",
    "label": "Your background *",
    "description": "Please describe your background in detail. Include information such as:",
    "academic": "Academic:",
    "academicDesc": "Current university/major, GPA, language test scores (TOEFL/IELTS/GRE)",
    "experience": "Experience:",
    "experienceDesc": "Research projects, internships, competitions, awards, publications",
    "entrepreneurship": "Entrepreneurship:",
    "entrepreneurshipDesc": "Startups founded, products launched, business ventures",
    "goals": "Goals:",
    "goalsDesc": "Target country/region, career plans, development goals",
    "other": "Other:",
    "otherDesc": "Anything else you think is relevant or worth highlighting",
    "reminderBestResults": {
      "icon": "💡",
      "title": "For best results:",
      "description": "Fill in only ONE target country/region at a time. This allows us to provide more focused and accurate recommendations."
    },
    "reminderQuality": {
      "icon": "⚡",
      "title": "Quality matters:",
      "description": "The quality of AI recommendations depends on the details you provide. If there's something special about your background that deserves attention, make sure to mention it!"
    },
    "placeholder": "Write freely in your own words...",
    "cancel": "Cancel",
    "continue": "Continue to Payment"
  },
  "progress": {
    "title": "Generating your report...",
    "subtitle": "This may take 10-15 minutes"
  },
  "result": {
    "title": "Your report is ready!",
    "subtitle": "Click the button below to download your personalized study abroad recommendation report",
    "download": "Download PDF Report",
    "newConsultation": "Start a new consultation"
  },
  "error": {
    "title": "Something went wrong",
    "retryFree": "✓ You can retry for free (no additional charge)",
    "retryButton": "Retry for Free",
    "tryAgain": "Try Again"
  }
}
```

### Step 6: 在组件中使用翻译

#### 6.1 更新 `components/Chat.tsx`

```tsx
'use client';

import {useTranslations} from 'next-intl';

export default function Chat({ isSidebarOpen, onToggleSidebar }: ChatProps) {
  const t = useTranslations('welcome');
  const tInfo = useTranslations('info');
  const tCommon = useTranslations('common');

  return (
    <div className="flex-1 flex flex-col bg-background">
      {/* ... */}

      {!isLoading && !reportReady && !error && (
        <div className="text-center max-w-3xl px-8">
          <h2 className="text-3xl font-semibold mb-4 text-foreground">
            {t('title')}
          </h2>
          <p className="text-muted-foreground mb-8 text-lg">
            {t('subtitle')}
          </p>
          <button
            onClick={handleStartConsultation}
            className="px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
          >
            {t('startButton')}
          </button>
          <p className="text-sm text-muted-foreground mt-4">
            {t('flow')}
          </p>

          {/* Important Information Section */}
          <div className="mt-12 space-y-4 text-left bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              {tInfo('title')}
            </h3>

            <div className="space-y-3 text-sm text-muted-foreground">
              <div className="flex gap-3">
                <span className="text-primary font-semibold shrink-0">
                  {tInfo('autoQueue.icon')}
                </span>
                <p>
                  <span className="font-medium text-foreground">
                    {tInfo('autoQueue.title')}
                  </span>{' '}
                  {tInfo('autoQueue.description')}
                </p>
              </div>

              {/* 重复其他信息卡片... */}

              <div className="flex gap-3">
                <span className="text-primary font-semibold shrink-0">💬</span>
                <p>
                  <span className="font-medium text-foreground">
                    {tInfo('support.title')}
                  </span>{' '}
                  {tInfo('support.description', {
                    email: (
                      <a href={`mailto:${tCommon('email')}`} className="text-primary hover:underline">
                        {tCommon('email')}
                      </a>
                    )
                  })}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

#### 6.2 更新 `components/FormModal.tsx`

```tsx
'use client';

import {useTranslations} from 'next-intl';

export default function FormModal({ isOpen, onClose, onSubmit }: FormModalProps) {
  const t = useTranslations('form');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-soft">
        <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">
            {t('title')}
          </h2>
          {/* ... */}
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2 text-foreground">
              {t('label')}
            </label>
            <p className="text-sm text-muted-foreground mb-3">
              {t('description')}
              <br />
              <span className="font-medium">{t('academic')}</span> {t('academicDesc')}
              <br />
              <span className="font-medium">{t('experience')}</span> {t('experienceDesc')}
              {/* ... */}
            </p>

            {/* Reminders */}
            <div className="mb-3 space-y-2">
              <div className="flex gap-2 items-start bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md px-3 py-2">
                <span className="text-blue-600 dark:text-blue-400 font-semibold shrink-0">
                  {t('reminderBestResults.icon')}
                </span>
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  <span className="font-semibold">{t('reminderBestResults.title')}</span>{' '}
                  {t('reminderBestResults.description')}
                </p>
              </div>
              {/* ... */}
            </div>

            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={12}
              className="w-full bg-background border border-input rounded-md px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              placeholder={t('placeholder')}
              required
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-6 py-3 border border-border rounded-md text-foreground hover-minimal transition-colors">
              {t('cancel')}
            </button>
            <button type="submit" disabled={!background.trim()} className="flex-1 px-6 py-3 bg-primary text-white rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              {t('continue')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

### Step 7: 添加语言切换器组件

创建 `components/LanguageSwitcher.tsx`:

```tsx
'use client';

import {useLocale} from 'next-intl';
import {useRouter, usePathname} from '@/i18n/routing';
import {routing} from '@/i18n/routing';

const languageNames: Record<string, string> = {
  'en': 'English',
  'zh-CN': '简体中文',
  'zh-TW': '繁體中文',
  'ja': '日本語',
  'ko': '한국어',
  'es': 'Español',
  'fr': 'Français',
  'de': 'Deutsch'
};

export default function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function onSelectChange(newLocale: string) {
    router.replace(pathname, {locale: newLocale});
  }

  return (
    <select
      value={locale}
      onChange={(e) => onSelectChange(e.target.value)}
      className="px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
      aria-label="Select language"
    >
      {routing.locales.map((loc) => (
        <option key={loc} value={loc}>
          {languageNames[loc]}
        </option>
      ))}
    </select>
  );
}
```

在 `components/Sidebar.tsx` 或 Header 中使用：

```tsx
import LanguageSwitcher from './LanguageSwitcher';

// 在适当位置添加
<LanguageSwitcher />
```

### Step 8: 翻译工作流（防止遗漏）

#### 8.1 创建翻译检查脚本

创建 `scripts/check-translations.ts`:

```typescript
import fs from 'fs';
import path from 'path';

const messagesDir = path.join(process.cwd(), 'messages');
const locales = ['en', 'zh-CN', 'zh-TW', 'ja', 'ko', 'es', 'fr', 'de'];

// 读取基础语言(英语)
const enPath = path.join(messagesDir, 'en.json');
const enMessages = JSON.parse(fs.readFileSync(enPath, 'utf-8'));

// 获取所有key的扁平列表
function flattenKeys(obj: any, prefix = ''): string[] {
  return Object.keys(obj).reduce((acc: string[], key) => {
    const newKey = prefix ? `${prefix}.${key}` : key;
    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      return acc.concat(flattenKeys(obj[key], newKey));
    }
    return acc.concat(newKey);
  }, []);
}

const enKeys = flattenKeys(enMessages);

console.log(`📝 Total translation keys: ${enKeys.length}`);
console.log('');

// 检查每种语言
let hasMissing = false;

for (const locale of locales) {
  if (locale === 'en') continue;

  const localePath = path.join(messagesDir, `${locale}.json`);

  if (!fs.existsSync(localePath)) {
    console.log(`❌ ${locale}.json is missing!`);
    hasMissing = true;
    continue;
  }

  const localeMessages = JSON.parse(fs.readFileSync(localePath, 'utf-8'));
  const localeKeys = flattenKeys(localeMessages);

  const missingKeys = enKeys.filter(key => !localeKeys.includes(key));
  const extraKeys = localeKeys.filter(key => !enKeys.includes(key));

  if (missingKeys.length > 0 || extraKeys.length > 0) {
    console.log(`⚠️  ${locale}:`);
    if (missingKeys.length > 0) {
      console.log(`   Missing ${missingKeys.length} keys:`);
      missingKeys.forEach(key => console.log(`     - ${key}`));
    }
    if (extraKeys.length > 0) {
      console.log(`   Extra ${extraKeys.length} keys:`);
      extraKeys.forEach(key => console.log(`     - ${key}`));
    }
    console.log('');
    hasMissing = true;
  } else {
    console.log(`✅ ${locale}: All keys present`);
  }
}

if (!hasMissing) {
  console.log('');
  console.log('🎉 All translations are complete!');
  process.exit(0);
} else {
  console.log('');
  console.log('❌ Some translations are incomplete. Please fix the issues above.');
  process.exit(1);
}
```

添加到 `package.json`:

```json
{
  "scripts": {
    "check-translations": "tsx scripts/check-translations.ts",
    "build": "npm run check-translations && next build"
  }
}
```

#### 8.2 使用AI工具批量翻译

创建提示词模板保存为 `scripts/translation-prompt.txt`:

```
我需要你帮我翻译以下JSON格式的UI文本。

源语言: English
目标语言: {TARGET_LANGUAGE}

要求:
1. 保持JSON结构不变
2. 只翻译值(value)，不要翻译键(key)
3. 保持占位符不变，如 {email}
4. 保持HTML标签不变
5. 使用地道、自然的表达
6. 注意上下文，保持专业语气

源文本:
```json
{SOURCE_JSON}
```

请直接返回翻译后的完整JSON，不要有其他解释。
```

#### 8.3 翻译工作流程

1. **完成英语版本** (`messages/en.json`) - 这是主模板
2. **复制到其他语言**:
   ```bash
   for locale in zh-CN zh-TW ja ko es fr de; do
     cp messages/en.json messages/$locale.json
   done
   ```
3. **使用AI翻译**:
   - 将 `en.json` 内容和 `translation-prompt.txt` 给ChatGPT/Claude
   - 逐个语言翻译并保存
4. **运行检查**:
   ```bash
   npm run check-translations
   ```
5. **人工审核** 关键部分（尤其是CTA按钮、法律声明等）

### Step 9: SEO优化

#### 9.1 更新 `app/[locale]/layout.tsx` 添加元数据

```tsx
import {Metadata} from 'next';

export async function generateMetadata({
  params
}: {
  params: Promise<{locale: string}>;
}): Promise<Metadata> {
  const {locale} = await params;

  const titles: Record<string, string> = {
    'en': 'OfferI - AI-Powered Study Abroad Consultant',
    'zh-CN': 'OfferI - AI留学咨询顾问',
    'zh-TW': 'OfferI - AI留學諮詢顧問',
    'ja': 'OfferI - AI留学コンサルタント',
    'ko': 'OfferI - AI 유학 컨설턴트',
    'es': 'OfferI - Consultor de Estudios en el Extranjero con IA',
    'fr': 'OfferI - Consultant d\'Études à l\'Étranger IA',
    'de': 'OfferI - KI-Studienberater im Ausland'
  };

  const descriptions: Record<string, string> = {
    'en': 'Get personalized study abroad recommendations powered by AI. $6 per consultation.',
    'zh-CN': '获取AI驱动的个性化留学推荐。每次咨询仅需$6。',
    // ... 其他语言
  };

  return {
    title: titles[locale] || titles.en,
    description: descriptions[locale] || descriptions.en,
    alternates: {
      canonical: `/${locale}`,
      languages: Object.fromEntries(
        routing.locales.map(loc => [loc, `/${loc}`])
      )
    }
  };
}
```

### Step 10: 测试检查清单

创建 `docs/i18n-testing-checklist.md`:

```markdown
# 国际化测试清单

## 基本功能测试
- [ ] 所有8种语言都能正常访问
- [ ] 语言切换器工作正常
- [ ] URL路由正确（如 /ja, /zh-CN）
- [ ] 默认语言检测正确（基于浏览器设置）
- [ ] 刷新页面后语言保持

## 内容测试
- [ ] 欢迎页面所有文本已翻译
- [ ] 表单Modal所有文本已翻译
- [ ] 进度条所有文本已翻译
- [ ] 错误消息所有文本已翻译
- [ ] 成功页面所有文本已翻译
- [ ] 邮件地址显示正确

## 布局测试
- [ ] 长文本语言（德语、法语）不会破坏布局
- [ ] CJK语言（中日韩）字体显示正常
- [ ] 按钮宽度自适应文本长度
- [ ] Modal滚动正常

## RTL支持（未来）
- [ ] 如果添加阿拉伯语，准备RTL布局

## SEO测试
- [ ] 每个语言版本有正确的 <html lang="">
- [ ] hreflang标签正确
- [ ] 元数据已翻译

## 性能测试
- [ ] 首屏加载时间 <2秒
- [ ] 语言切换流畅（无闪烁）
```

## 🎨 维护策略

### 添加新文本时的工作流：

1. **在 `messages/en.json` 中添加新key**
2. **在组件中使用** `t('newKey')`
3. **运行检查**: `npm run check-translations`
4. **翻译其他语言**（使用AI辅助）
5. **提交代码**

### 定期审核：

- 每月运行一次 `check-translations`
- 收集用户反馈（翻译质量问题）
- 定期更新过时的表达

## 🚀 迁移现有代码的步骤

1. ✅ **安装依赖** - 完成
2. 📁 **创建目录结构** - 创建 messages/ 和 i18n/
3. ⚙️ **配置文件** - 添加所有配置
4. 📄 **创建英语模板** - 基于现有硬编码文本
5. 🔄 **重构组件** - 逐个替换硬编码文本
6. 🌍 **翻译其他语言** - 使用AI辅助
7. 🧪 **测试** - 按照检查清单
8. 🚀 **部署**

## 📊 预估工作量

- **配置setup**: 2小时
- **创建英语模板**: 3小时
- **重构5个主要组件**: 5小时
- **AI辅助翻译7种语言**: 2小时
- **测试和修复**: 3小时
- **总计**: ~15小时

## 💡 最佳实践

1. **始终从英语开始** - 它是基准
2. **使用命名空间** - 避免key冲突（welcome.title vs form.title）
3. **占位符统一命名** - {email}, {count}, {name}
4. **不要在翻译中放HTML** - 使用Rich Text功能
5. **定期运行检查脚本** - 防止遗漏
6. **记录翻译决策** - 特殊术语的翻译标准

---

**问题反馈**: lyrica2333@gmail.com
