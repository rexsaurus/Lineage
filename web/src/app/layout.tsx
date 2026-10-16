import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Lineage", template: "%s · Lineage" },
  description: "Turn your family's records into a family history your relatives will read.",
  // nothing but the landing page is indexed (spec §12); the landing page overrides this
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <Link className="brand" href="/">Lineage</Link>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
