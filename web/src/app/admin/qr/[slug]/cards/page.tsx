import { notFound } from "next/navigation";
import { requireAdmin } from "@/lib/auth";
import { isSlug } from "@/lib/src";
import { eventUrl, qrSvg } from "@/lib/qr";

export const metadata = { title: "Printable cards" };

// Spec §9: a printable sheet of 8 business-card-size cards (3.5 × 2 in): QR, a line of text, and the URL for people
// who can't scan. Print from the browser at 100%.
export default async function Cards({ params }: { params: Promise<{ slug: string }> }) {
  await requireAdmin();
  const { slug } = await params;
  if (!isSlug(slug)) notFound();
  const url = eventUrl(slug);
  const svg = await qrSvg(url);
  return (
    <div className="sheet">
      <style>{`
        @page { size: letter; margin: 0.5in 0.75in; }
        header.top { display: none; }
        body { background: #fff; color: #000; }
        .sheet { display: grid; grid-template-columns: repeat(2, 3.5in); grid-auto-rows: 2in; gap: 0.1in; justify-content: center; padding: 0.25in 0; }
        .cardp { box-sizing: border-box; border: 1px dashed #999; padding: 0.15in; display: flex; gap: 0.15in; align-items: center; }
        .cardp .q { width: 1.6in; flex: none; }
        .cardp b { display: block; font-size: 15pt; line-height: 1.15; margin-bottom: 6pt; }
        .cardp span { font-size: 8.5pt; word-break: break-all; }
      `}</style>
      {Array.from({ length: 8 }, (_, i) => (
        <div className="cardp" key={i}>
          <div className="q" dangerouslySetInnerHTML={{ __html: svg }} />
          <div><b>Scan to start your family&apos;s history</b><span>{url}</span></div>
        </div>
      ))}
    </div>
  );
}
