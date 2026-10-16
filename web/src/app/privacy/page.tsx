export const metadata = { title: "Privacy" };

export default function Privacy() {
  return (
    <div className="page">
      <p className="badge">DRAFT — pending legal review</p>
      <h1>Your privacy</h1>
      <h2>What we collect</h2>
      <p>Your email address and name, the family name you choose, the photos and documents you add, and whether you have paid. Stripe handles payments: your card details never reach Lineage.</p>
      <h2>Who can see it</h2>
      <p>Your family page is private. Only you, the relatives you invite, and Rex (who runs Lineage) can see it. Family pages are never public and never appear in search engines. We remove location details from photos when they are uploaded.</p>
      <h2>What we never do</h2>
      <p>We never sell or rent your information. We don&apos;t use your records to train any AI model. Records about living people are not shared.</p>
      <h2>Emails</h2>
      <p>We email you only about your family page. Reply &ldquo;stop&rdquo; at any time.</p>
      <h2>Deleting your information</h2>
      <p>Email Rex and ask. We will delete your family page, its records and their files.</p>
      <p className="muted small">Storage limits and how long records are kept will be set out here before launch.</p>
    </div>
  );
}
