import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page">
      <h1>Page not found</h1>
      <p>This page doesn&apos;t exist, or you need to sign in to see it.</p>
      <Link className="btn" href="/login">Sign in</Link>
      <Link className="btn secondary" href="/">Go to the start</Link>
    </div>
  );
}
