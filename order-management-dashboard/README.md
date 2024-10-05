# order-management-dashboard

![CI](https://github.com/JainMayankA/order-management-dashboard/actions/workflows/ci.yml/badge.svg)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue)

Full-stack order management dashboard built on top of the [event-sourcing-cqrs](../event-sourcing-cqrs) backend. Next.js 14 App Router frontend with JWT authentication, real-time order management, status timeline, and revenue analytics.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Charts | Recharts (area chart, donut chart) |
| Auth | JWT via `jose`, httpOnly cookies, middleware-based route protection |
| Backend | event-sourcing-cqrs (FastAPI + PostgreSQL + CQRS) |
| Deployment | Docker Compose |

## Features

- JWT authentication with role-based access (admin / manager / viewer)
- Dashboard with revenue trend chart, orders-by-status donut, key metrics
- Orders table with status filter, search, and pagination
- Order detail page with visual status timeline and inline actions (confirm, ship, deliver, cancel)
- New order form with product selection and live total calculation
- Customers list with order stats
- Works in demo mode (offline fallback data) when backend is not running

## Architecture

```
Browser
  │
  ├── /login          → POST /api/auth/login → sets httpOnly JWT cookie
  │
  ├── middleware.ts   → verifies JWT on every request, redirects to /login if invalid
  │
  ├── /dashboard      → Server Component → fetches from CQRS backend via /api/* proxies
  ├── /orders         → Client Component → fetches via /api/orders (proxied)
  └── /orders/[id]    → Client Component → order detail + action buttons
                              │
                        /api/orders/[id]/[action]  → proxies to FastAPI backend
```

All API calls from the browser go through Next.js route handlers (`/api/*`), which verify the JWT and proxy to the FastAPI backend. The browser never calls the backend directly — CORS is not needed.

## Auth flow

1. User submits email + password to `POST /api/auth/login`
2. Route handler verifies credentials, signs a JWT with `jose`
3. JWT stored as `httpOnly; SameSite=lax` cookie — not accessible to JavaScript
4. `middleware.ts` runs on every request, verifies the JWT, redirects to `/login` on failure
5. Role check in proxy routes: `viewer` cannot mutate orders

## Quickstart

```bash
# Option 1: Frontend only (uses demo data)
npm install
npm run dev
# Open http://localhost:3000
# Login: admin@demo.com / admin123

# Option 2: Full stack with real backend
docker-compose up
# Open http://localhost:3000
```

## Demo credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@demo.com | admin123 |
| Manager | manager@demo.com | manager123 |
| Viewer | viewer@demo.com | viewer123 |

## Project structure

```
order-management-dashboard/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth/login/        # JWT login route
│   │   │   ├── auth/logout/       # Logout route
│   │   │   └── orders/            # Backend proxy routes
│   │   ├── dashboard/             # Dashboard with metrics + charts
│   │   ├── orders/                # Orders list, detail, new order form
│   │   └── customers/             # Customer list
│   ├── components/
│   │   ├── ui/                    # Sidebar, StatusBadge
│   │   └── charts/                # RevenueChart, StatusPieChart
│   ├── lib/
│   │   ├── auth.ts                # JWT sign/verify, session management
│   │   └── api.ts                 # Typed API client
│   ├── types/index.ts             # TypeScript types
│   └── middleware.ts              # Route protection
├── docker-compose.yml
└── Dockerfile
```
