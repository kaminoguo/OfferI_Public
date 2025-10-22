import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <SignIn
        appearance={{
          elements: {
            formButtonPrimary: 'bg-primary hover:bg-primary/90',
            card: 'shadow-soft border border-border',
            headerTitle: 'text-foreground',
            headerSubtitle: 'hidden',
            socialButtonsBlockButton: 'border-border hover:bg-secondary',
            formFieldLabel: 'text-foreground',
            formFieldInput: 'border-input bg-background text-foreground',
            footerActionLink: 'text-primary hover:text-primary/90',
            // Hide default footer/branding sections
            footer: 'hidden',
            logoBox: 'hidden',
          },
        }}
      />
    </div>
  )
}
