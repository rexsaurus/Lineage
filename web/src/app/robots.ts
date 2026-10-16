import type { MetadataRoute } from "next";

// Only the landing page may be indexed (spec §12).
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", allow: "/$", disallow: "/" }] };
}
