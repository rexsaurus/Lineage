// Event attribution (spec §3.1, §5): ?src=<slug> from a QR code, kept in a first-party cookie for 30 days.
export const SRC_COOKIE = "lineage_src";
export const SRC_MAX_AGE = 30 * 24 * 60 * 60;
const SLUG = /^[a-z0-9-]{1,64}$/;

export function isSlug(v: unknown): v is string {
  return typeof v === "string" && SLUG.test(v);
}

/** A valid slug, or 'direct' for missing or invalid values. */
export function normalizeSrc(v: unknown): string {
  const s = typeof v === "string" ? v.trim().toLowerCase() : "";
  return isSlug(s) ? s : "direct";
}
