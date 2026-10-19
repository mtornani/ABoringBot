export interface Env {
  DB: D1Database;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'GET' && url.pathname === '/api/v1/feed') {
      const apiKey = request.headers.get('x-api-key');

      if (!apiKey) {
        return new Response(JSON.stringify({ error: 'Missing API key' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      const row = await env.DB.prepare(
        'SELECT key_string FROM api_keys WHERE key_string = ? AND is_active = 1'
      )
        .bind(apiKey)
        .first();

      if (!row) {
        return new Response(JSON.stringify({ error: 'Invalid or inactive API key' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      return new Response(JSON.stringify({ anomalies: [], market_intel: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ error: 'Not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  },
};
