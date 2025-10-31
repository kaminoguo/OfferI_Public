# 🚀 Quick Start - 国际化版本启动指南

## ⚠️ 重要：必须执行的步骤

### 1. 安装依赖
```bash
cd /home/lyrica/Offer_I/frontend
npm install
```

**这一步非常重要！** 我们添加了 `next-intl` 依赖，必须先安装。

### 2. 清理Next.js缓存（重要！）
```bash
rm -rf .next
```

### 3. 启动开发服务器
```bash
npm run dev
```

### 4. 访问应用
浏览器打开: `http://localhost:3000`

## ✅ 你应该看到的内容

### 主页面
- ✅ 欢迎标题："Welcome to OfferI"
- ✅ 副标题："AI-powered personalized study abroad consultant"
- ✅ 开始按钮："Start Consultation ($6)"
- ✅ **5个信息卡片**：
  - ⏱️ Auto-queuing system（自动排队系统）
  - 🔄 Unlimited free retries（无限免费重试）
  - 💬 Need help?（需要帮助？）
  - 🚧 MVP Stage（MVP阶段）
  - 🤝 Interested in collaboration?（合作）

### 侧边栏
- ✅ **语言选择器**（在顶部）
  - 显示当前语言（English, 简体中文, etc.）
  - 点击可切换8种语言
- ✅ Consultation History（咨询历史）
- ✅ 用户信息/登录按钮

### 表单
打开表单后应该看到：
- ✅ 结构化描述（Academic, Experience, Entrepreneurship, Goals, Other）
- ✅ **2个提醒卡片**：
  - 💡 蓝色：For best results: Fill in only ONE target country...
  - ⚡ 黄色：Quality matters: The quality of AI recommendations...

## 🔧 如果还是看不到

### 问题1: 页面是空白的
```bash
# 完全重启
cd /home/lyrica/Offer_I/frontend
rm -rf .next
npm install
npm run dev
```

### 问题2: 还是看到老版本
```bash
# 清除浏览器缓存
# Chrome: Ctrl+Shift+Delete
# 或者使用无痕模式测试
```

### 问题3: Hydration错误
```bash
# 确认老文件已删除
ls app/
# 应该只看到: globals.css, layout.tsx, [locale]/
```

### 问题4: 依赖问题
```bash
# 删除node_modules重新安装
rm -rf node_modules package-lock.json
npm install
```

## 🌐 测试语言切换

1. 打开侧边栏（如果关闭了）
2. 查看顶部的**语言选择器**（有地球图标 🌐）
3. 点击当前语言（例如"English"）
4. 选择其他语言（例如"简体中文"）
5. 页面会刷新，所有文本应该变成中文

**支持的语言：**
- 🇬🇧 English
- 🇨🇳 简体中文 (Simplified Chinese)
- 🇹🇼 繁體中文 (Traditional Chinese)
- 🇯🇵 日本語 (Japanese)
- 🇰🇷 한국어 (Korean)
- 🇪🇸 Español (Spanish)
- 🇫🇷 Français (French)
- 🇩🇪 Deutsch (German)

## 📋 验证清单

运行后检查：

- [ ] 主页显示5个信息卡片
- [ ] 侧边栏顶部有语言选择器
- [ ] 点击语言选择器能看到8种语言
- [ ] 切换语言后页面文本改变
- [ ] 打开表单看到2个提醒卡片
- [ ] 表单有结构化描述（Academic, Experience等）
- [ ] 没有hydration错误

## 🐛 Debug命令

```bash
# 检查翻译文件是否完整
npm run check-translations

# 查看当前路由结构
ls -R app/

# 查看Next.js构建信息
npm run dev 2>&1 | grep -A 5 "Routes:"
```

## 📞 如果还有问题

1. 检查浏览器控制台（F12）有没有错误
2. 检查终端（npm run dev）有没有错误
3. 确认访问的URL是 `http://localhost:3000/` 不是 `http://localhost:3000/en/`
4. 尝试访问 `http://localhost:3000/zh-CN/` 看是否显示中文

---

**最重要的步骤：**
```bash
cd /home/lyrica/Offer_I/frontend
rm -rf .next
npm install
npm run dev
```

然后访问 `http://localhost:3000/`
