# Frontend - AI Documentation

Next.js 15 + React 19 frontend with Clerk authentication and Stripe payments.

## Architecture

```
Next.js 15 (App Router)
    ├── app/ - Pages and layouts
    ├── components/ - React components
    └── lib/ - Utility functions

Authentication: Clerk
Payments: Stripe
Styling: TailwindCSS 3.4.17
```

## Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with ClerkProvider
│   ├── page.tsx                # Main consultation interface (authenticated)
│   ├── sign-in/[[...sign-in]]/page.tsx    # Clerk sign-in
│   ├── sign-up/[[...sign-up]]/page.tsx    # Clerk sign-up
│   └── settings/page.tsx       # User settings (API keys, usage)
│
├── components/
│   ├── Chat.tsx                # Main chat interface with job polling
│   ├── FormModal.tsx           # Background input modal
│   ├── PaymentModal.tsx        # Stripe checkout modal
│   ├── ProgressBar.tsx         # Job progress indicator
│   └── Sidebar.tsx             # Navigation sidebar
│
├── lib/
│   └── api.ts                  # Backend API client (fetch wrappers)
│
├── public/                     # Static assets
├── middleware.ts               # Clerk authentication middleware
├── tailwind.config.ts          # TailwindCSS configuration
├── tsconfig.json               # TypeScript configuration
├── package.json                # Dependencies
├── .env.local.example          # Environment variables template
└── Dockerfile                  # Production build image
```

## Key Components

**app/page.tsx - Main Interface:**
```typescript
export default function Home() {
  const { user } = useUser();  // Clerk auth
  const [jobStatus, setJobStatus] = useState(null);

  // Submit consultation
  const handleSubmit = async (background: string, tier: string) => {
    const response = await fetch('/api/submit', {
      method: 'POST',
      body: JSON.stringify({ user_id: user.id, tier, background })
    });
    const { job_id } = await response.json();
    pollJobStatus(job_id);
  };

  // Poll job status every 2 seconds
  const pollJobStatus = (jobId: string) => {
    const interval = setInterval(async () => {
      const status = await fetch(`/api/status/${jobId}`);
      const data = await status.json();
      setJobStatus(data);
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);
  };

  return <Chat onSubmit={handleSubmit} jobStatus={jobStatus} />;
}
```

**components/Chat.tsx - Chat Interface:**
```typescript
interface ChatProps {
  onSubmit: (background: string, tier: string) => void;
  jobStatus: JobStatus | null;
}

export default function Chat({ onSubmit, jobStatus }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [showModal, setShowModal] = useState(false);

  const handleNewConsultation = () => {
    // Check quota
    checkQuota().then(hasQuota => {
      if (hasQuota) {
        setShowModal(true);  // Show background input modal
      } else {
        setShowPaymentModal(true);  // Show payment modal
      }
    });
  };

  return (
    <div className="chat-container">
      {messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}
      {jobStatus && <ProgressBar status={jobStatus} />}
      <button onClick={handleNewConsultation}>New Consultation</button>
      {showModal && <FormModal onSubmit={onSubmit} />}
    </div>
  );
}
```

**components/FormModal.tsx - Background Input:**
```typescript
interface FormModalProps {
  onSubmit: (background: string, tier: string) => void;
  onClose: () => void;
}

export default function FormModal({ onSubmit, onClose }: FormModalProps) {
  const [background, setBackground] = useState('');
  const [tier, setTier] = useState<'basic' | 'advanced'>('basic');

  const handleSubmit = () => {
    if (background.trim()) {
      onSubmit(background, tier);
      onClose();
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Tell us about yourself</h2>
        <textarea
          value={background}
          onChange={e => setBackground(e.target.value)}
          placeholder="GPA, major, work experience, target programs..."
          rows={10}
        />
        <div className="tier-selection">
          <label>
            <input type="radio" value="basic" checked={tier === 'basic'} onChange={e => setTier(e.target.value)} />
            Basic ($9)
          </label>
          <label>
            <input type="radio" value="advanced" checked={tier === 'advanced'} onChange={e => setTier(e.target.value)} />
            Advanced ($49.99)
          </label>
        </div>
        <button onClick={handleSubmit}>Submit</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
```

**components/PaymentModal.tsx - Stripe Checkout:**
```typescript
interface PaymentModalProps {
  onSuccess: () => void;
  onClose: () => void;
}

export default function PaymentModal({ onSuccess, onClose }: PaymentModalProps) {
  const { user } = useUser();

  const handlePayment = async () => {
    // Create Stripe checkout session
    const response = await fetch('/api/create-checkout-session', {
      method: 'POST',
      body: JSON.stringify({
        user_id: user.id,
        amount: 6.00,
        tier: 'basic'  // Or selected tier
      })
    });
    const { url } = await response.json();

    // Redirect to Stripe checkout
    window.location.href = url;
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Payment Required</h2>
        <p>You have used 5 free consultations this month.</p>
        <p>Additional consultations: $6 each</p>
        <button onClick={handlePayment}>Pay with Stripe</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
```

**components/ProgressBar.tsx - Job Progress:**
```typescript
interface ProgressBarProps {
  status: JobStatus;
}

export default function ProgressBar({ status }: ProgressBarProps) {
  const progress = status.progress || 0;  // 0-100

  return (
    <div className="progress-container">
      <div className="progress-bar" style={{ width: `${progress}%` }} />
      <p className="progress-text">
        {status.status === 'queued' && 'Waiting in queue...'}
        {status.status === 'processing' && `Generating report... ${progress}%`}
        {status.status === 'completed' && 'Report ready!'}
        {status.status === 'failed' && 'Generation failed. Please retry.'}
      </p>
      {status.message && <p className="status-message">{status.message}</p>}
    </div>
  );
}
```

**components/Sidebar.tsx - Navigation:**
```typescript
export default function Sidebar() {
  const { user } = useUser();
  const [consultations, setConsultations] = useState<Consultation[]>([]);

  useEffect(() => {
    // Load consultation history
    fetch(`/api/user/${user.id}/consultations`)
      .then(res => res.json())
      .then(data => setConsultations(data.consultations));
  }, [user.id]);

  return (
    <aside className="sidebar">
      <div className="user-info">
        <img src={user.imageUrl} alt={user.fullName} />
        <span>{user.fullName}</span>
      </div>
      <nav>
        <Link href="/">New Consultation</Link>
        <Link href="/settings">Settings</Link>
      </nav>
      <div className="consultation-history">
        <h3>History</h3>
        {consultations.map(c => (
          <div key={c.id} className="history-item">
            <span>{c.created_at}</span>
            <a href={c.pdf_url} download>Download PDF</a>
          </div>
        ))}
      </div>
    </aside>
  );
}
```

**app/settings/page.tsx - Settings:**
```typescript
export default function Settings() {
  const { user } = useUser();
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);

  const generateAPIKey = async () => {
    const response = await fetch('/api/mcp/keys', {
      method: 'POST',
      body: JSON.stringify({ user_id: user.id, tier: 'basic' })
    });
    const { key } = await response.json();
    setApiKeys([...apiKeys, key]);
  };

  const revokeAPIKey = async (keyId: string) => {
    await fetch(`/api/mcp/keys/${keyId}`, { method: 'DELETE' });
    setApiKeys(apiKeys.filter(k => k.id !== keyId));
  };

  return (
    <div className="settings-page">
      <h1>Settings</h1>

      <section className="usage-section">
        <h2>Monthly Usage</h2>
        <p>Consultations used: {usage?.count || 0} / 5 free</p>
      </section>

      <section className="api-keys-section">
        <h2>MCP API Keys</h2>
        <button onClick={generateAPIKey}>Generate New Key</button>
        <ul>
          {apiKeys.map(key => (
            <li key={key.id}>
              <code>{key.id}</code>
              <span>Tier: {key.tier}</span>
              <button onClick={() => revokeAPIKey(key.id)}>Revoke</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

## API Client (lib/api.ts)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function submitConsultation(data: {
  user_id: string;
  tier: 'basic' | 'advanced' | 'upgrade';
  background: string;
}): Promise<{ job_id: string }> {
  const response = await fetch(`${API_URL}/api/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('Submission failed');
  return response.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_URL}/api/status/${jobId}`);
  if (!response.ok) throw new Error('Status check failed');
  return response.json();
}

export async function createCheckoutSession(data: {
  user_id: string;
  amount: number;
  tier: string;
}): Promise<{ url: string }> {
  const response = await fetch(`${API_URL}/api/create-checkout-session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('Checkout creation failed');
  return response.json();
}

export async function getUserConsultations(userId: string): Promise<Consultation[]> {
  const response = await fetch(`${API_URL}/api/user/${userId}/consultations`);
  if (!response.ok) throw new Error('Failed to load consultations');
  const data = await response.json();
  return data.consultations;
}

export async function getUserUsage(userId: string): Promise<Usage> {
  const response = await fetch(`${API_URL}/api/user/${userId}/usage`);
  if (!response.ok) throw new Error('Failed to load usage');
  return response.json();
}

export async function generateAPIKey(userId: string, tier: string): Promise<APIKey> {
  const response = await fetch(`${API_URL}/api/mcp/keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, tier })
  });
  if (!response.ok) throw new Error('Key generation failed');
  return response.json();
}

export async function revokeAPIKey(keyId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/mcp/keys/${keyId}`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error('Key revocation failed');
}
```

## Authentication (Clerk)

**middleware.ts:**
```typescript
import { authMiddleware } from '@clerk/nextjs';

export default authMiddleware({
  publicRoutes: ['/sign-in', '/sign-up', '/api/webhook']
});

export const config = {
  matcher: ['/((?!.+\\.[\\w]+$|_next).*)', '/', '/(api|trpc)(.*)']
};
```

**app/layout.tsx:**
```typescript
import { ClerkProvider } from '@clerk/nextjs';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
```

## Environment Variables (.env.local)

```bash
# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxx
CLERK_SECRET_KEY=sk_live_xxx

# Stripe Payment
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxx

# Backend API
NEXT_PUBLIC_API_URL=https://api.offeri.org

# Development
NODE_ENV=production
```

## Styling (TailwindCSS)

**tailwind.config.ts:**
```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}'
  ],
  theme: {
    extend: {
      colors: {
        primary: '#007bff',
        secondary: '#6c757d',
        success: '#28a745',
        danger: '#dc3545'
      }
    }
  },
  plugins: []
};

export default config;
```

## Build & Deploy

**Development:**
```bash
cd frontend
npm install
npm run dev  # Starts on port 3000
```

**Production (Docker):**
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Dockerfile:**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
```

## User Flow

```
1. User lands on homepage
2. Sign in with Clerk (Google/GitHub/Email)
3. Click "New Consultation"
4. Check quota (5 free per month)
5a. If quota available:
    → Show FormModal (background input)
    → Submit job
    → Poll status every 2s
    → Download PDF when ready
5b. If quota exceeded:
    → Show PaymentModal
    → Redirect to Stripe checkout
    → Complete payment
    → Return to site
    → Continue with step 5a
6. View consultation history in Sidebar
7. Manage API keys in Settings
```

## TypeScript Types

**types.ts:**
```typescript
export interface JobStatus {
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress?: number;  // 0-100
  message?: string;
  result?: {
    markdown: string;
    pdf_url: string;
  };
  error?: string;
}

export interface Consultation {
  id: string;
  user_id: string;
  tier: 'basic' | 'advanced' | 'upgrade';
  background: string;
  status: string;
  pdf_url?: string;
  created_at: string;
  updated_at: string;
}

export interface Usage {
  user_id: string;
  year: number;
  month: number;
  count: number;
}

export interface APIKey {
  id: string;
  user_id: string;
  tier: 'basic' | 'advanced' | 'upgrade';
  allowed_tools: string[];
  is_active: boolean;
  created_at: string;
}
```

## Testing

**Manual Testing:**
```bash
# Start dev server
npm run dev

# Test authentication
# → Sign in with test account
# → Check user.id in console

# Test job submission
# → Fill background form
# → Submit consultation
# → Check job_id in network tab

# Test polling
# → Watch console for status updates
# → Verify progress bar updates

# Test payment
# → Use Stripe test card: 4242 4242 4242 4242
# → Verify payment webhook received
# → Check job starts after payment
```

## Common Issues

**Clerk authentication fails:**
```bash
# Check environment variables
echo $NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
echo $CLERK_SECRET_KEY

# Check middleware configuration
cat middleware.ts

# Verify Clerk dashboard settings
# → Allowed domains: offeri.org
# → OAuth providers enabled
```

**Job polling not working:**
```typescript
// Add error handling
const pollJobStatus = (jobId: string) => {
  const interval = setInterval(async () => {
    try {
      const status = await getJobStatus(jobId);
      setJobStatus(status);
      if (status.status === 'completed' || status.status === 'failed') {
        clearInterval(interval);
      }
    } catch (error) {
      console.error('Polling error:', error);
      // Continue polling on error
    }
  }, 2000);
};
```

**Stripe redirect fails:**
```typescript
// Ensure success_url and cancel_url are set
const checkoutData = {
  user_id: user.id,
  amount: 6.00,
  tier: 'basic',
  success_url: `${window.location.origin}/payment-success`,
  cancel_url: `${window.location.origin}/payment-cancel`
};
```

## Dependencies (package.json)

```json
{
  "dependencies": {
    "next": "15.5.6",
    "react": "19.2.0",
    "react-dom": "19.2.0",
    "@clerk/nextjs": "6.33.7",
    "@stripe/stripe-js": "8.1.0",
    "tailwindcss": "3.4.17",
    "typescript": "5"
  }
}
```

## References

- [AI_PROJECT_README.md](../AI_PROJECT_README.md) - Overall architecture
- [app/](app/) - Next.js pages
- [components/](components/) - React components
- [lib/api.ts](lib/api.ts) - Backend API client
