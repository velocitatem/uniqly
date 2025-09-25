import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:9812';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string; count: string }> }
) {
  try {
    const { slug, count } = await params;

    const response = await fetch(`${BACKEND_URL}/contexts/${slug}/next/${count}`);

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.detail || 'Failed to fetch suggestions' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching suggestions:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}