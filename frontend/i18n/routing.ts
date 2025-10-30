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
