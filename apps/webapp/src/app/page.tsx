"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface ContextResponse {
  slug: string;
  context: string;
  url: string;
  created_at: number;
  active: boolean;
}

export default function Home() {
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!context.trim()) {
      setError('Please enter a context');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/contexts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          context: context.trim(),
          generation_interval: 60
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create context');
      }

      const data: ContextResponse = await response.json();

      // Redirect to the new context page
      router.push(`/${data.slug}`);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-8">
          <p className="text-xl text-gray-600">
            Create personalized agentic stream. Enter any context and subscribe.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <input
              type="text"
              id="context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. lactose-free snack ideas, creative writing prompts for sci-fi stories"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            />
          </div>


          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !context.trim()}
            className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Creating Your Stream...' : 'Create Suggestion Stream'}
          </button>
        </form>

      </div>
    </div>
  );
}
