'use client';

import { useState, useEffect } from 'react';
import { useUser } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { Key, TrendingUp, Copy, Plus, Trash2, AlertCircle } from 'lucide-react';

interface APIKey {
  key_preview: string;
  full_key?: string;
  name: string | null;
  is_super_key: boolean;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

interface UserProfile {
  user_id: string;
  api_keys: APIKey[];
  mcp_usage: {
    month: number;
    year: number;
    used: number;
    limit: number;
    remaining: number;
    is_unlimited: boolean;
  };
}

export default function SettingsPage() {
  const { user, isLoaded } = useUser();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);

  useEffect(() => {
    if (isLoaded && !user) {
      router.push('/sign-in');
    } else if (user) {
      fetchProfile();
    }
  }, [isLoaded, user]);

  const fetchProfile = async () => {
    if (!user) return;

    try {
      setLoading(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/user/profile/${user.id}`);

      if (!response.ok) {
        throw new Error('Failed to fetch profile');
      }

      const data = await response.json();
      setProfile(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const createAPIKey = async () => {
    if (!user) return;

    try {
      setIsCreating(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/user/api-keys/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user.id,
          name: newKeyName || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create API key');
      }

      const data = await response.json();
      setNewlyCreatedKey(data.api_key.full_key);
      setNewKeyName('');
      setShowCreateForm(false); // Hide the form after successful creation
      fetchProfile(); // Refresh profile to show new key
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setIsCreating(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  const revokeKey = async (keyId: string) => {
    if (!user) return;
    if (!confirm('Are you sure you want to revoke this API key?')) return;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/user/api-keys/${keyId}?user_id=${user.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to revoke API key');
      }

      fetchProfile(); // Refresh profile
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  if (!isLoaded || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading settings...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-foreground mb-2">Error</h2>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
          <p className="text-muted-foreground">
            Manage your API keys and view usage statistics
          </p>
        </div>

        {/* MCP API Usage */}
        <div className="bg-white border border-border rounded-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <TrendingUp className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">MCP API Usage</h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">This Month</p>
              <p className="text-2xl font-bold text-foreground">{profile.mcp_usage.used}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Limit</p>
              <p className="text-2xl font-bold text-foreground">
                {profile.mcp_usage.is_unlimited ? '∞' : profile.mcp_usage.limit}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Remaining</p>
              <p className="text-2xl font-bold text-foreground">
                {profile.mcp_usage.is_unlimited ? '∞' : profile.mcp_usage.remaining}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Period</p>
              <p className="text-2xl font-bold text-foreground">
                {profile.mcp_usage.month}/{profile.mcp_usage.year}
              </p>
            </div>
          </div>

          {!profile.mcp_usage.is_unlimited && profile.mcp_usage.remaining === 0 && (
            <div className="mt-4 p-3 bg-orange-50 border border-orange-200 rounded-md">
              <p className="text-sm text-orange-800">
                You've used all your free consultations this month. Contact us for unlimited access (Super API key).
              </p>
            </div>
          )}
        </div>

        {/* Newly Created Key Alert */}
        {newlyCreatedKey && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold text-green-900 mb-2">API Key Created!</h3>
            <p className="text-sm text-green-800 mb-3">
              Save this key now. You won't be able to see it again!
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 bg-white border border-green-300 rounded font-mono text-sm">
                {newlyCreatedKey}
              </code>
              <button
                onClick={() => copyToClipboard(newlyCreatedKey)}
                className="p-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                <Copy className="w-5 h-5" />
              </button>
            </div>
            <button
              onClick={() => setNewlyCreatedKey(null)}
              className="mt-3 text-sm text-green-700 hover:text-green-900"
            >
              I've saved it, dismiss
            </button>
          </div>
        )}

        {/* API Keys */}
        <div className="bg-white border border-border rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Key className="w-6 h-6 text-primary" />
              <h2 className="text-xl font-semibold text-foreground">API Keys</h2>
            </div>
            {/* Only show "New Key" button if user has no active keys (1 key per account) */}
            {profile.api_keys.filter(k => k.is_active).length === 0 && (
              <button
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                New Key
              </button>
            )}
          </div>

          {/* Create Key Form */}
          {showCreateForm && (
            <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-md">
              <label className="block text-sm font-medium text-foreground mb-2">
                Key Name (optional)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g., Production API"
                  className="flex-1 px-3 py-2 border border-border rounded-md"
                />
                <button
                  onClick={createAPIKey}
                  disabled={isCreating}
                  className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
                <button
                  onClick={() => setShowCreateForm(false)}
                  disabled={isCreating}
                  className="px-4 py-2 border border-border rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Keys List */}
          <div className="space-y-3">
            {profile.api_keys.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">
                No API keys yet. Create one to get started!
              </p>
            ) : (
              profile.api_keys.map((key) => (
                <div
                  key={key.key_preview}
                  className="flex items-center justify-between p-4 border border-border rounded-md"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="font-mono text-sm">{key.key_preview}</code>
                      {key.is_super_key && (
                        <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
                          Super Key
                        </span>
                      )}
                      {!key.is_active && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          Revoked
                        </span>
                      )}
                    </div>
                    {key.name && (
                      <p className="text-sm text-muted-foreground">{key.name}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Created: {new Date(key.created_at).toLocaleDateString()}
                      {key.last_used_at && ` • Last used: ${new Date(key.last_used_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  {key.is_active && (
                    <button
                      onClick={() => revokeKey(key.key_preview.replace('...', ''))}
                      className="p-2 text-red-600 hover:bg-red-50 rounded"
                      title="Revoke key"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
