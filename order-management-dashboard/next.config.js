/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    API_BASE_URL: process.env.API_BASE_URL || 'http://localhost:8000',
    JWT_SECRET: process.env.JWT_SECRET || 'dev-secret-change-in-production',
  },
}
module.exports = nextConfig
