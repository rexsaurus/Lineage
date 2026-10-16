# The /join/ page (in-person sign-ups)

`/join/` is the page a QR code at a genealogy meeting opens. It is not in the site's navigation and is not indexed.

| Path | What it is |
|---|---|
| `/join/` | Offer, pay button (only when configured), and the "Reserve your spot" / "Get updates" form |
| `/join/demo/` | Placeholder showcase: five slots labelled "Demo content — Rex to add" |
| `/join/privacy/` | Plain-language privacy summary, marked DRAFT |
| `/?src=<slug>` | Redirects to `/join/?src=<slug>` (only when `src` matches `[a-z0-9-]{1,64}`); `/` without `src` is unchanged |
| `/api/join-config` | `{ ready, priceDisplay, paymentLink }`, from the environment |
| `/api/lead` | POST from the form; stores a lead (name, email, family name, src) |
| `/api/lead-admin?key=…` | The sign-ups as a table; add `&format=csv` to download |

Sources: `site/join.html`, `site/join-demo.html`, `site/join-privacy.html` (built by `make site`), `api/join-config.js`,
`api/lead.js`, `api/lead-admin.js`, `api/_leads.js`, and the redirect and `X-Robots-Tag` header in `vercel.json`.

## Attribution

Each QR code points at `https://lineage.rexstjohn.com/?src=<event-slug>`, e.g. `smcgs-2026-10-17`. The page keeps the
slug in a `lineage_src` cookie for 30 days, sends it with the form, and passes it to Stripe as `client_reference_id`, so
each payment in the Stripe dashboard shows which meeting it came from. Missing or invalid slugs become `direct`.

## Settings (Vercel project environment)

Nothing is shown or charged until these are set. With neither price nor link, the page shows no price and no pay
button, only the free reservation form. **No price is written anywhere in the code.**

```bash
vercel env add PRICE_DISPLAY production            # the text after "Founding Archivist —", exactly as it should appear
vercel env add STRIPE_PAYMENT_LINK_URL production  # https://buy.stripe.com/...  (a Stripe Payment Link)
vercel env add ADMIN_KEY production                # 16+ random characters: openssl rand -hex 16
```

In the Payment Link's settings in Stripe, set the confirmation page to redirect to `https://lineage.rexstjohn.com/join/`
(or show Stripe's own confirmation). The link must allow `client_reference_id` (all Payment Links do).

## The lead store

The site has no build step for npm packages, so leads go to **Upstash Redis over its REST API** (plain `fetch`). Until a
store is connected, `/api/lead` fails closed: the visitor sees "Please write your email on Rex's sheet" and nothing is
kept. To connect one:

1. Vercel dashboard → the `lineage` project → **Storage** → **Create Database** → **Upstash for Redis** (the free plan
   is enough) → connect it to the project for Production and Preview.
2. That adds `KV_REST_API_URL` and `KV_REST_API_TOKEN` to the project (the `UPSTASH_REDIS_REST_URL` /
   `UPSTASH_REDIS_REST_TOKEN` names also work). Check with `vercel env ls`.
3. Redeploy (`vercel deploy --prod --yes`) so the functions see the new variables.
4. Test: submit the form once, then open `/api/lead-admin?key=<ADMIN_KEY>`.

Leads are kept as one Redis list, `join:leads`. Nothing a visitor types is logged.

## Local testing

`vercel dev` serves the pages and functions but ignores `has` conditions, so the `?src` redirect can only be checked on a
deployment (`curl -sI "https://lineage.rexstjohn.com/?src=test-1"` should show `307` and `location: /join/?src=test-1`).
A local `vercel build` shows the compiled route in `.vercel/output/config.json`.
