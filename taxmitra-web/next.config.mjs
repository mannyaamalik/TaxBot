/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output produces a self-contained server bundle for Docker
  output: "standalone",

  // Forward /api/* to the FastAPI backend at build time (Vercel rewrites)
  // For Docker the NEXT_PUBLIC_API_URL env var is used directly by the client.
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/chat",
        destination: `${apiUrl}/chat`,
      },
      {
        source: "/api/health",
        destination: `${apiUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
