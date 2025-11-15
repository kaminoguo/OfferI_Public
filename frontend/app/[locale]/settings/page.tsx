'use client';

import { useState, useEffect } from 'react';
import { useUser } from '@clerk/nextjs';
import { useRouter } from '@/i18n/routing';
import { useTranslations } from 'next-intl';
import { Key, Copy, Plus, Trash2, AlertCircle, Mail, Github, Youtube } from 'lucide-react';

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
  const t = useTranslations();
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
    alert(t('settings.copiedToClipboard'));
  };

  const revokeKey = async (keyId: string) => {
    if (!user) return;
    if (!confirm(t('settings.confirmRevoke'))) return;

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
          <p className="text-muted-foreground">{t('settings.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-foreground mb-2">{t('error.title')}</h2>
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
          <h1 className="text-3xl font-bold text-foreground mb-2">{t('settings.title')}</h1>
          <p className="text-muted-foreground">
            {t('settings.subtitle')}
          </p>
        </div>

        {/* Newly Created Key Alert */}
        {newlyCreatedKey && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold text-green-900 mb-2">{t('settings.keyCreated')}</h3>
            <p className="text-sm text-green-800 mb-3">
              {t('settings.saveKeyWarning')}
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
              {t('settings.dismissKey')}
            </button>
          </div>
        )}

        {/* API Keys */}
        <div className="bg-white border border-border rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Key className="w-6 h-6 text-primary" />
              <h2 className="text-xl font-semibold text-foreground">{t('settings.apiKeys')}</h2>
            </div>
            {/* Only show "New Key" button if user has no active keys (1 key per account) */}
            {profile.api_keys.filter(k => k.is_active).length === 0 && (
              <button
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                {t('settings.newKey')}
              </button>
            )}
          </div>

          {/* Create Key Form */}
          {showCreateForm && (
            <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-md">
              <label className="block text-sm font-medium text-foreground mb-2">
                {t('settings.keyName')}
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder={t('settings.keyNamePlaceholder')}
                  className="flex-1 px-3 py-2 border border-border rounded-md"
                />
                <button
                  onClick={createAPIKey}
                  disabled={isCreating}
                  className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {isCreating ? t('settings.creating') : t('settings.create')}
                </button>
                <button
                  onClick={() => setShowCreateForm(false)}
                  disabled={isCreating}
                  className="px-4 py-2 border border-border rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  {t('form.cancel')}
                </button>
              </div>
            </div>
          )}

          {/* Keys List */}
          <div className="space-y-3">
            {profile.api_keys.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">
                {t('settings.noKeys')}
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
                          {t('settings.superKey')}
                        </span>
                      )}
                      {!key.is_active && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          {t('settings.revoked')}
                        </span>
                      )}
                    </div>
                    {key.name && (
                      <p className="text-sm text-muted-foreground">{key.name}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {t('settings.created')}: {new Date(key.created_at).toLocaleDateString()}
                      {key.last_used_at && ` • ${t('settings.lastUsed')}: ${new Date(key.last_used_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  {key.is_active && (
                    <button
                      onClick={() => revokeKey(key.key_preview.replace('...', ''))}
                      className="p-2 text-red-600 hover:bg-red-50 rounded"
                      title={t('settings.revokeKey')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* MCP API Notice */}
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mb-6">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Key className="w-6 h-6 text-purple-700" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-purple-900 mb-2">
                {t('settings.mcpNotice.title')}
              </h3>
              <p className="text-sm text-purple-800 mb-3">
                {t('settings.mcpNotice.description')}
              </p>
              <div className="space-y-2 text-sm text-purple-800">
                <p className="font-medium">{t('settings.mcpNotice.benefits')}</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>{t('settings.mcpNotice.unlimitedConsultations')}</li>
                  <li>{t('settings.mcpNotice.priorityProcessing')}</li>
                  <li>{t('settings.mcpNotice.dedicatedSupport')}</li>
                </ul>
              </div>
              <div className="mt-4 p-3 bg-white border border-purple-200 rounded-md">
                <p className="text-sm font-medium text-purple-900 mb-1">{t('settings.mcpNotice.contactTitle')}</p>
                <p className="text-sm text-purple-800">
                  {t('settings.mcpNotice.contactEmail', { email: t('common.email') })}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Contact & Links */}
        <div className="bg-white border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Mail className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">{t('settings.contactLinks')}</h2>
          </div>

          <div className="space-y-4">
            {/* Contact Email */}
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-md">
              <Mail className="w-5 h-5 text-gray-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">{t('settings.contactMe')}</p>
                <a
                  href={`mailto:${t('common.email')}`}
                  className="text-sm text-primary hover:underline"
                >
                  {t('common.email')}
                </a>
              </div>
            </div>

            {/* GitHub */}
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-md">
              <Github className="w-5 h-5 text-gray-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">{t('settings.githubRepo')}</p>
                <a
                  href="https://github.com/kaminoguo/OfferI_Public"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  github.com/kaminoguo/OfferI_Public
                </a>
              </div>
            </div>

            {/* Bilibili - Placeholder */}
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-md opacity-50">
              <svg
                className="w-5 h-5 text-gray-600"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M17.813 4.653h.854c1.51.054 2.769.578 3.773 1.574 1.004.995 1.524 2.249 1.56 3.76v7.36c-.036 1.51-.556 2.769-1.56 3.773s-2.262 1.524-3.773 1.56H5.333c-1.51-.036-2.769-.556-3.773-1.56S.036 18.858 0 17.347v-7.36c.036-1.511.556-2.765 1.56-3.76 1.004-.996 2.262-1.52 3.773-1.574h.774l-1.174-1.12a1.234 1.234 0 0 1-.373-.906c0-.356.124-.658.373-.907l.027-.027c.267-.249.573-.373.92-.373.347 0 .653.124.92.373L9.653 4.44c.071.071.134.142.187.213h4.267a.836.836 0 0 1 .16-.213l2.853-2.747c.267-.249.573-.373.92-.373.347 0 .662.151.929.4.267.249.391.551.391.907 0 .355-.124.657-.373.906zM5.333 7.24c-.746.018-1.373.276-1.88.773-.506.498-.769 1.13-.786 1.894v7.52c.017.764.28 1.395.786 1.893.507.498 1.134.756 1.88.773h13.334c.746-.017 1.373-.275 1.88-.773.506-.498.769-1.129.786-1.893v-7.52c-.017-.765-.28-1.396-.786-1.894-.507-.497-1.134-.755-1.88-.773zM8 11.107c.373 0 .684.124.933.373.25.249.383.569.4.96v1.173c-.017.391-.15.711-.4.96-.249.25-.56.374-.933.374s-.684-.125-.933-.374c-.25-.249-.383-.569-.4-.96V12.44c0-.373.129-.689.386-.947.258-.257.574-.386.947-.386zm8 0c.373 0 .684.124.933.373.25.249.383.569.4.96v1.173c-.017.391-.15.711-.4.96-.249.25-.56.374-.933.374s-.684-.125-.933-.374c-.25-.249-.383-.569-.4-.96V12.44c.017-.391.15-.711.4-.96.249-.249.56-.373.933-.373Z"/>
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">Bilibili</p>
                <p className="text-sm text-muted-foreground">{t('settings.comingSoon')}</p>
              </div>
            </div>

            {/* YouTube - Placeholder */}
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-md opacity-50">
              <Youtube className="w-5 h-5 text-gray-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">YouTube</p>
                <p className="text-sm text-muted-foreground">{t('settings.comingSoon')}</p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
