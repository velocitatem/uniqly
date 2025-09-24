"use client";

import { useEffect, useState } from 'react';

interface SuggestionsResponse {
  suggestions: string[];
  count: number;
  context_id: string;
  remaining_in_queue: number;
}

export default function Home() {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        const response = await fetch('/api/suggestions');
        if (!response.ok) {
          throw new Error('Failed to fetch suggestions');
        }
        const data: SuggestionsResponse = await response.json();
        setSuggestions(data.suggestions);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchSuggestions();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="text-center max-w-4xl">
        {loading && <p className="text-lg">Loading suggestions...</p>}

        {error && (
          <p className="text-lg text-red-600">Error: {error}</p>
        )}

        {!loading && !error && suggestions.length > 0 && (
          <div>
            {suggestions.map((suggestion, index) => (
              <p key={index} className="text-lg mb-4">
                {suggestion}
              </p>
            ))}
          </div>
        )}

        {!loading && !error && suggestions.length === 0 && (
          <p className="text-lg">No suggestions available</p>
        )}
      </div>
    </div>
  );
}
