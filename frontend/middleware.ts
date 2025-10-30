import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import createIntlMiddleware from 'next-intl/middleware';
import {routing} from './i18n/routing';

// Create next-intl middleware
const intlMiddleware = createIntlMiddleware(routing);

// Define public routes that don't require authentication
// Include locale prefixes for all public routes
const isPublicRoute = createRouteMatcher([
  '/',
  '/:locale',
  '/:locale/sign-in(.*)',
  '/:locale/sign-up(.*)',
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/api/webhooks(.*)',
])

export default clerkMiddleware(async (auth, request) => {
  // Run intl middleware first
  const intlResponse = intlMiddleware(request);

  // Then check auth if needed
  if (!isPublicRoute(request)) {
    await auth.protect()
  }

  return intlResponse;
})

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    '/((?!_next|_vercel|.*\\..*).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
