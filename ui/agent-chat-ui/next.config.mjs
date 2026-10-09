/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.WEB_CHECK_DIST_DIR || ".next",
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;
