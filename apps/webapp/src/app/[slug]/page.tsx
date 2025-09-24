"use client";

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

interface SuggestionsResponse {
  suggestions: string[];
  count: number;
  context_id: string;
  context: string;
  remaining_in_queue: number;
  total_available?: number;
}

interface ContextStatus {
  context_id: string;
  context: string;
  description?: string;
  created_at: number;
  active: boolean;
  queue_size: number;
  total_unique_suggestions: number;
  total_generated: number;
  last_generation_timestamp: number;
  healthy: boolean;
}

export default function ContextPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [status, setStatus] = useState<ContextStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`/api/contexts/${slug}/status`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Context not found');
        }
        throw new Error('Failed to fetch context status');
      }
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  const fetchSuggestions = async (count: number = 5) => {
    setSuggestionsLoading(true);
    try {
      const response = await fetch(`/api/contexts/${slug}/next/${count}`);
      if (!response.ok) {
        throw new Error('Failed to fetch suggestions');
      }
      const data: SuggestionsResponse = await response.json();
      setSuggestions(prevSuggestions => [...prevSuggestions, ...data.suggestions]);

      // Refresh status after getting suggestions
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load suggestions');
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const triggerGeneration = async () => {
    try {
      const response = await fetch(`/api/contexts/${slug}/generate`, { method: 'POST' });
      if (!response.ok) {
        throw new Error('Failed to trigger generation');
      }
      // Refresh status after triggering generation
      setTimeout(fetchStatus, 2000); // Wait a bit for generation to start
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger generation');
    }
  };

  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      await fetchStatus();
      await fetchSuggestions(3); // Load initial suggestions
      setLoading(false);
    };

    if (slug) {
      loadInitialData();
    }
  }, [slug]);

  const copyUrl = () => {
    navigator.clipboard.writeText(window.location.href);
    // Could add a toast notification here
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-lg">Loading your suggestion stream...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-2xl font-bold mb-4">Error</div>
          <h1 className="text-2xl font-bold mb-2">Oops!</h1>
          <p className="text-gray-600 mb-4">{error}</p>
          <a href="/" className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
            Create New Stream
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="border-b border-gray-100 p-8">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-light text-gray-800">{status?.context}</h1>
            <button
              onClick={copyUrl}
              className="text-gray-400 hover:text-gray-600 text-sm font-light"
            >
              Copy URL to Share
            </button>
          </div>
          <div className="text-xs text-gray-400 font-light">
            {status?.healthy ? 'Active' : 'Offline'}
          </div>
        </div>

        {/* Main Content */}
        <div className="p-8">
          {suggestions.length === 0 && !suggestionsLoading ? (
            <div className="text-center py-20">
              <p className="text-gray-400 font-light mb-8">No suggestions available yet.</p>
              <button
                onClick={triggerGeneration}
                className="text-gray-600 hover:text-gray-800 font-light border-b border-gray-200 hover:border-gray-400 pb-1"
              >
                Generate
              </button>
            </div>
          ) : (
            <div className="text-center py-20">
              <div className="mb-12">
                <p className="text-2xl font-light text-gray-700 leading-relaxed">
                  {suggestions[0] || "Loading..."}
                </p>
              </div>

              <div className="flex justify-center space-x-8">
                <button
                  onClick={() => {
                    if (suggestions.length > 1) {
                      setSuggestions(prev => prev.slice(1));
                    } else {
                      fetchSuggestions(1);
                    }
                  }}
                  disabled={suggestionsLoading}
                  className="text-gray-600 hover:text-gray-800 font-light border-b border-gray-200 hover:border-gray-400 pb-1 disabled:opacity-50"
                >
                  {suggestionsLoading ? 'Loading...' : 'Next'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
