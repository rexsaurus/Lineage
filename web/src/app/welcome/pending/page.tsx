import Link from "next/link";

export const metadata = { title: "Payment pending" };

export default function Pending() {
  return (
    <div className="page">
      <h1>Your payment is still going through</h1>
      <p>This can take a minute. We&apos;ll email you a sign-in link as soon as it&apos;s done.</p>
      <Link className="btn secondary" href="/login">Sign in with email</Link>
    </div>
  );
}
