This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Incident Analysis API client

The Incident Analysis client is isolated in `lib/incident-analysis-api.ts` and
does not modify the existing Talent Pipeline Tracker client or its API base.
Set `NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE` when the FastAPI service is not
running at `http://localhost:8000/api`:

```bash
NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE=http://localhost:8000/api npm run dev
```

It sends CSV files as `multipart/form-data` without setting the `Content-Type`
header manually, and only handles aggregate analysis results or the exported
CSV blob. Sensitive incident fields such as customer emails are not part of the
client types or responses.

## Nexova API client and session

The authenticated Nexova client uses `NEXT_PUBLIC_NEXOVA_API_BASE`, defaulting
to `http://localhost:8000/api` for local development. In Codespaces, set it to
the forwarded API origin (port 8000) plus `/api`; the frontend origin must also
be included in the API's `CORS_ORIGINS` allowlist. This public URL is not a
secret; never put API keys or signing secrets in `NEXT_PUBLIC_*` variables.

Protected Nexova requests opt into Bearer authentication through the shared
client. The existing candidate Tracker and Incident Analysis clients remain
separate and do not receive the session token.

Supplier Directory requests opt into Bearer authentication. A `401` should be
diagnosed by checking that login completed, a token is present, and the request
uses the Nexova API base; successful registration alone does not create a
session. Keep the Nexova and Incident Analysis clients separate from the
4Geeks Tracker client.

The Nexova client binds the native `globalThis.fetch` before storing it as a
method, while preserving injected fetchers used by tests. Keep this binding if
the client is changed. The auth form also renders a stable pre-hydration
placeholder; do not infer the cause of earlier browser DOM mutations from that
mitigation alone. Validate login and registration in a browser in addition to
automated client checks.

Run the shared client tests with `npm test` from this application directory.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
