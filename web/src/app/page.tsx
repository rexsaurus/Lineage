import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import { priceDisplay } from "@/env";
import { isSlug, normalizeSrc, SRC_COOKIE } from "@/lib/src";

export const metadata: Metadata = { robots: { index: true, follow: true } };

export default async function Landing({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const src = isSlug(sp.src?.toLowerCase()) ? sp.src!.toLowerCase() : normalizeSrc((await cookies()).get(SRC_COOKIE)?.value);
  const price = priceDisplay();
  const startHref = `/start?src=${encodeURIComponent(src)}`;
  return (
    <div className="page">
      <h1>You keep your family&apos;s records. Lineage turns them into a family history your relatives will read.</h1>
      <p>Photographs, letters, recordings and papers become a family page your relatives can open on their phones, and in time a book.</p>
      <p className="muted">I turned my dad&apos;s 3.5-hour interview into a 170-page book. — Rex</p>

      <section className="card" aria-labelledby="offer">
        <h2 id="offer" style={{ marginTop: 0 }}>
          Founding Archivist{price ? ` — ${price}` : ""}
        </h2>
        <p>For the person in the family who keeps the records.</p>
        {price ? null : <p>Price announced soon. Reserve your spot free.</p>}
        <Link className="btn" href={startHref}>
          {price ? "Start my family" : "Reserve my spot"}
        </Link>
      </section>

      <p className="small">
        Already started? <Link href="/login">Sign in</Link>. · <Link href="/privacy">Privacy</Link>
      </p>
    </div>
  );
}
