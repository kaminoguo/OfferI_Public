# OfferI Frontend

AI study abroad advisor frontend. Next.js 15 + React 19 + Clerk + Stripe.

## Tech Stack

Framework & UI:
- Next.js 15.5.6 (App Router)
- React 19.2.0
- TypeScript 5
- TailwindCSS 3.4.17

Authentication & Payment:
- Clerk 6.33.7 (user authentication)
- Stripe 8.1.0 (payment processing, $6/consultation)

Libraries:
- axios 1.7.9 (HTTP client)
- framer-motion 11.15.0 (animations)
- lucide-react 0.460.0 (icons)
- react-markdown 9.0.1 (markdown rendering)
- react-syntax-highlighter 15.6.1 (code highlighting)

## Features

User Flow:
1. Sign in/up (Clerk authentication)
2. Pay $6 (Stripe checkout)
3. Fill background form (school, GPA, major, projects, internships, career goals)
4. Wait 10-15 minutes (ChatGPT-style progress bar)
5. Download PDF report

Components:
- Chat interface (message bubbles, markdown rendering)
- Payment modal (Stripe checkout integration)
- Background form modal (unstructured input)
- Progress bar (10%-100% ChatGPT style)
- Sidebar (consultation history, new chat)
- Settings page (API key management)

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with Clerk provider
│   ├── page.tsx            # Main chat page
│   ├── globals.css         # Global styles + Tailwind
│   ├── settings/
│   │   └── page.tsx        # API key management
│   ├── sign-in/
│   │   └── [[...sign-in]]/page.tsx  # Clerk sign-in
│   └── sign-up/
│       └── [[...sign-up]]/page.tsx  # Clerk sign-up
│
├── components/
│   ├── Chat.tsx            # Main chat interface
│   ├── PaymentModal.tsx    # Stripe payment modal
│   ├── FormModal.tsx       # Background form modal
│   ├── ProgressBar.tsx     # Progress indicator
│   └── Sidebar.tsx         # History sidebar
│
├── lib/
│   └── api.ts              # Backend API client
│
├── middleware.ts           # Clerk authentication middleware
├── .env.local.example      # Environment variables template
├── package.json            # Dependencies
├── tailwind.config.ts      # Tailwind configuration
├── tsconfig.json           # TypeScript configuration
└── next.config.js          # Next.js configuration
```

## Quick Start

Prerequisites:
- Node.js 18+
- Backend API running (http://localhost:8000)
- Clerk account (https://clerk.com/)
- Stripe account (https://stripe.com/)

Installation:

1. Install Dependencies
```bash
cd frontend
npm install
```

2. Configure Environment
```bash
cp .env.local.example .env.local
nano .env.local
```

Required environment variables:
```bash
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx

# Stripe Payment
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_xxxxx
```

3. Start Development Server
```bash
npm run dev
# Open http://localhost:3000
```

4. Build for Production
```bash
npm run build
npm start
```

## User Journey

1. Landing Page (/)
- User sees welcome screen
- Click "Start Consultation" button
- Redirected to sign-in if not authenticated

2. Sign In/Up (/sign-in, /sign-up)
- Clerk authentication
- Google/Email login options
- Redirected back to chat after auth

3. Payment Modal
- Displays $6 consultation fee
- "Proceed to Payment" button
- Opens Stripe checkout
- Returns to chat after successful payment

4. Background Form Modal
- Opens after payment verification
- Fields: school, GPA, major, projects, internships, career goal, target countries, budget
- Unstructured text input (flexible format)
- Submit → job_id created

5. Progress Display
- ChatGPT-style progress bar (10%-100%)
- Status updates every 5 seconds
- "Generating report... (40%)"
- Takes 10-15 minutes

6. Results
- "Download PDF" button appears
- Report filename: OfferI_留学规划报告_HKUST_abc12345.pdf
- Consultation saved to history

7. Settings Page (/settings)
- View API keys
- Create new API key (for MCP access)
- Revoke keys
- Shows usage: X/5 consultations this month

## API Integration

Frontend communicates with backend API:

```typescript
// Payment
POST /api/payment/create-session
Response: { checkout_url }

GET /api/payment/verify/:payment_id
Response: { status: "paid" | "pending" }

// Consultation
POST /api/submit
Body: { school, gpa, major, projects, internships, career_goal, target_countries, budget }
Response: { job_id, status, estimated_time }

GET /api/status/:job_id
Response: { status: "queued" | "processing" | "completed" | "failed", progress }

GET /api/results/:job_id/download
Response: PDF file

// Settings (API Keys)
GET /api/settings/keys
Header: Authorization: Bearer clerk_token
Response: [{ key, name, is_super_key, created_at, last_used_at }]

POST /api/settings/keys
Body: { name }
Response: { key, name, is_super_key }

DELETE /api/settings/keys/:key
```

## Components

### Chat.tsx
Main chat interface with message bubbles, input area, and state management.

State:
- messages: Array of user/assistant messages
- jobId: Current consultation job ID
- status: Job status (queued/processing/completed/failed)
- showPayment: Payment modal visibility
- showForm: Background form modal visibility

### PaymentModal.tsx
Stripe checkout integration.

Flow:
1. User clicks "Proceed to Payment"
2. Call POST /api/payment/create-session
3. Redirect to Stripe checkout (checkout_url)
4. Stripe redirects back with payment_id
5. Verify payment: GET /api/payment/verify/:payment_id
6. If paid, show background form modal

### FormModal.tsx
Background information form.

Fields (all text input, unstructured):
- school: "HKUST" or "香港科技大学 (QS44)"
- gpa: "3.5" or "3.5/4.0"
- major: "CS + AI" or "计算机科学与人工智能"
- projects: "推荐系统项目，深度学习"
- internships: "Google 实习 3 个月"
- career_goal: "产品经理"
- target_countries: "美国、香港"
- budget: "无上限" or "50万人民币"

Submit → POST /api/submit → job_id

### ProgressBar.tsx
ChatGPT-style progress indicator.

States:
- 10%: "Analyzing your background..."
- 30%: "Searching 93,716 programs..."
- 50%: "Generating recommendations..."
- 70%: "Validating rankings..."
- 90%: "Finalizing report..."
- 100%: "Report ready!"

### Sidebar.tsx
Consultation history and navigation.

Features:
- "New Consultation" button
- List of past consultations (by date)
- User profile section
- Sign out button

## Styling

TailwindCSS configuration with custom colors:

```css
/* Dark theme */
background: #1a1a1a
foreground: #ffffff
border: #2a2a2a

/* Primary actions */
primary: #10A37F (green, like ChatGPT)
hover: #0d8d6b

/* Cards and surfaces */
card: #242424
```

## Development

Run Development Server:
```bash
npm run dev
```

Type Checking:
```bash
npx tsc --noEmit
```

Linting:
```bash
npm run lint
```

Format Code:
```bash
npx prettier --write .
```

## Environment Variables

Production:
```bash
NEXT_PUBLIC_API_URL=https://api.offeri.org
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx
CLERK_SECRET_KEY=sk_live_xxxxx
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
```

Development:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_xxxxx
```

## Deployment

Vercel (Recommended):
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Configure environment variables in Vercel dashboard
```

Docker:
```bash
# Build
docker build -t offeri-frontend .

# Run
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=https://api.offeri.org \
  -e NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx \
  -e NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx \
  offeri-frontend
```

Self-Hosted:
```bash
# Build
npm run build

# Start with PM2
pm2 start npm --name "offeri-frontend" -- start

# Or with Node.js
node .next/standalone/server.js
```

## Troubleshooting

Backend Connection Failed:
```bash
# Check backend is running
curl http://localhost:8000/health

# Check CORS configuration in backend
# backend/api/server.py should include http://localhost:3000
```

Clerk Authentication Error:
```bash
# Verify Clerk keys
echo $NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

# Check Clerk dashboard for correct keys
# Development: pk_test_*, Production: pk_live_*
```

Stripe Payment Failed:
```bash
# Verify Stripe keys
echo $NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY

# Test mode: pk_test_*, Live mode: pk_live_*
# Ensure webhook is configured in Stripe dashboard
```

Build Errors:
```bash
# Clear cache
rm -rf .next node_modules
npm install
npm run build
```

Type Errors:
```bash
# Regenerate Next.js types
rm -rf .next
npm run dev  # Types regenerate on dev server start
```

## Performance

Metrics:
- First Load JS: ~200KB (gzipped)
- Time to Interactive: <2s
- Lighthouse Score: 95+ (all categories)

Optimizations:
- Server-side rendering (SSR) for initial load
- Automatic code splitting
- Image optimization (Next.js Image component)
- API polling optimization (5s interval, stops when complete)

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile: iOS Safari 14+, Chrome Android latest

## License

Proprietary - OfferI

## Support

- GitHub Issues: https://github.com/kaminoguo/OfferI/issues
- Email: contact@offeri.org
- Documentation: See backend README for API details
