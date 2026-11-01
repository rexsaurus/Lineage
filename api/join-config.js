// /join/ offer settings. GET /api/join-config
// The price and the pay button appear only when BOTH are set in the Vercel project's environment:
//   PRICE_DISPLAY            the text shown after "Founding Archivist —" (Rex sets it; there is no default)
//   STRIPE_PAYMENT_LINK_URL  a Stripe Payment Link, https://buy.stripe.com/...
// Otherwise { ready: false }, and the page offers only a free reservation.
module.exports = function handler(req, res) {
  const price = String(process.env.PRICE_DISPLAY || "").trim().slice(0, 40);
  const link = String(process.env.STRIPE_PAYMENT_LINK_URL || "").trim();
  let ok = false;
  try {
    const u = new URL(link);
    ok = u.protocol === "https:" && /(^|\.)stripe\.com$/.test(u.hostname);
  } catch {
    ok = false;
  }
  res.setHeader("Cache-Control", "public, s-maxage=60");
  res.setHeader("X-Robots-Tag", "noindex");
  res.status(200).json(price && ok ? { ready: true, priceDisplay: price, paymentLink: link } : { ready: false });
};
