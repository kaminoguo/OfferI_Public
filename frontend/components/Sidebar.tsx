'use client';

import { X, User, LogOut } from 'lucide-react';
import { useUser, useClerk } from '@clerk/nextjs';
import Link from 'next/link';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();

  if (!isOpen) return null;

  return (
    <div className="w-64 bg-background border-r border-border flex flex-col">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-border">
        <h2 className="font-semibold text-foreground">OfferI</h2>
        <button
          onClick={onToggle}
          className="p-1.5 rounded-md hover-minimal"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5 text-muted-foreground" />
        </button>
      </div>

      {/* Main Content - Placeholder for future features */}
      <div className="flex-1 p-4">
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">
            Your consultation history will appear here
          </p>
        </div>
      </div>

      {/* User Profile */}
      <div className="p-4 border-t border-border">
        {isLoaded && user ? (
          <>
            <Link
              href="/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-md hover-minimal cursor-pointer mb-2"
            >
              {user.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName || 'User'}
                  className="w-8 h-8 rounded-full"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <User className="w-5 h-5 text-muted-foreground" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {user.fullName || user.emailAddresses[0]?.emailAddress || 'User'}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  MCP API • Web $6
                </p>
              </div>
            </Link>
            <button
              onClick={() => signOut()}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 px-3 py-2 rounded-md mb-2">
              <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                <User className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className="text-sm font-medium text-foreground">Guest User</span>
            </div>
            <div className="space-y-2">
              <Link
                href="/sign-in"
                className="block w-full text-center px-3 py-2 text-sm bg-primary text-white rounded-md hover:bg-primary/90 transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                className="block w-full text-center px-3 py-2 text-sm border border-border text-foreground rounded-md hover:bg-secondary transition-colors"
              >
                Sign up
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
