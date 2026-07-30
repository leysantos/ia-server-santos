/** @type {import('next').NextConfig} */
const nextConfig = {
  // LAN (172.22.x) e Quick Tunnel (*.trycloudflare.com) no `next dev`
  allowedDevOrigins: [
    "172.22.3.234",
    "192.168.143.111",
    "*.trycloudflare.com",
  ],
  // Laudos PDF grandes (dezenas de fotos) podem levar >30s via /api-backend
  experimental: {
    proxyTimeout: 300_000,
  },
  async rewrites() {
    const apiOrigin = process.env.API_BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api-backend/:path*",
        destination: `${apiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
