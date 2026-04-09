# RetailCRM Orders Dashboard

Next.js dashboard that reads order data from Supabase and renders:
- KPIs
- orders per day chart
- revenue chart
- recent orders table

## Environment variables

Create `.env.local` with:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=YOUR_SECRET_KEY
```

## Local run

```bash
npm install
npm run dev
```

## Vercel

Add the same environment variables in Project Settings -> Environment Variables and redeploy.
