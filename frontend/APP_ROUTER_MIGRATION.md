# App Router 重构指南

由于国际化需要修改目录结构，请按照以下步骤进行迁移。

## 当前结构
```
app/
├── globals.css
├── layout.tsx
├── page.tsx
├── settings/
│   └── page.tsx
├── sign-in/
│   └── [[...sign-in]]/
│       └── page.tsx
└── sign-up/
    └── [[...sign-up]]/
        └── page.tsx
```

## 目标结构
```
app/
├── [locale]/
│   ├── layout.tsx          # 新建 - 包含NextIntlClientProvider
│   ├── page.tsx            # 移动自 app/page.tsx
│   ├── settings/
│   │   └── page.tsx        # 移动自 app/settings/page.tsx
│   ├── sign-in/
│   │   └── [[...sign-in]]/
│   │       └── page.tsx    # 移动自 app/sign-in/[[...sign-in]]/page.tsx
│   └── sign-up/
│       └── [[...sign-up]]/
│           └── page.tsx    # 移动自 app/sign-up/[[...sign-up]]/page.tsx
├── globals.css             # 保持不变
└── layout.tsx              # 更新为root layout
```

## 执行步骤

### 步骤1: 备份
```bash
cd /home/lyrica/Offer_I/frontend
cp -r app app_backup
```

### 步骤2: 创建[locale]目录
```bash
mkdir -p app/[locale]/settings
mkdir -p app/[locale]/sign-in/[[...sign-in]]
mkdir -p app/[locale]/sign-up/[[...sign-up]]
```

### 步骤3: 移动文件
```bash
# 移动主页面
mv app/page.tsx app/[locale]/

# 移动settings
mv app/settings/page.tsx app/[locale]/settings/

# 移动sign-in
mv app/sign-in/[[...sign-in]]/page.tsx app/[locale]/sign-in/[[...sign-in]]/

# 移动sign-up
mv app/sign-up/[[...sign-up]]/page.tsx app/[locale]/sign-up/[[...sign-up]]/
```

### 步骤4: 删除旧目录
```bash
# 删除旧的空目录
rm -rf app/settings
rm -rf app/sign-in
rm -rf app/sign-up
```

### 步骤5: 创建locale layout
创建 `app/[locale]/layout.tsx` 文件（内容见下方）

### 步骤6: 更新root layout
更新 `app/layout.tsx` 文件（内容见下方）

---

## 所需文件内容

### app/[locale]/layout.tsx (新建)
```typescript
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
    <NextIntlClientProvider messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
```

### app/layout.tsx (更新)
保留现有的ClerkProvider和全局样式，但移除不必要的内容：

```typescript
import type { Metadata } from 'next';
import { ClerkProvider } from '@clerk/nextjs';
import './globals.css';

export const metadata: Metadata = {
  title: 'OfferI - AI Study Abroad Consultant',
  description: 'Get personalized study abroad recommendations powered by AI',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html suppressHydrationWarning>
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
```

注意: `<html>` 标签的 `lang` 属性将由 `[locale]/layout.tsx` 动态设置。

---

## 完成后验证

1. 检查文件结构是否正确
```bash
tree app -L 4
```

2. 检查是否有遗漏的文件
```bash
find app -name "*.tsx" -not -path "app/[locale]/*" -not -name "layout.tsx"
```

3. 尝试启动dev server
```bash
npm run dev
```

## 常见问题

**Q: 报错找不到@/i18n/routing**
A: 确保 `i18n/routing.ts` 文件已创建

**Q: 报错 Cannot find module '../messages/en.json'**
A: 确保 `messages/` 目录和所有语言JSON文件已创建

**Q: 页面空白或报错**
A: 检查 `app/layout.tsx` 是否正确配置了ClerkProvider

---

⚠️ **重要**: 执行完迁移后，需要更新所有组件使用翻译。详见后续步骤。
