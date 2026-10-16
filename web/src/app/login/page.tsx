import { loginAction } from "../actions";
import { SubmitButton } from "@/components/SubmitButton";
import { safeRedirect } from "@/lib/magic";

export const metadata = { title: "Sign in" };

const MESSAGES: Record<string, string> = {
  email: "Please check your email address and try again.",
  link: "That sign-in link has expired or was already used. Here's a new one: type your email below.",
  session: "We couldn't confirm that payment. Sign in with your email and we'll sort it out.",
};

export default async function Login({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const next = safeRedirect(sp.next) || "";
  if (sp.sent) {
    return (
      <div className="page">
        <h1>Check your email</h1>
        <p>We&apos;ve sent you a sign-in link. It works once, for the next 15 minutes.</p>
        <p className="muted">Nothing there? Check your spam folder, or try again below.</p>
        <form action={loginAction}>
          <input type="hidden" name="next" value={next} />
          <label htmlFor="email">Your email</label>
          <input id="email" name="email" type="email" inputMode="email" autoComplete="email" required />
          <div style={{ marginTop: 20 }}><SubmitButton>Send a new link</SubmitButton></div>
        </form>
      </div>
    );
  }
  return (
    <div className="page">
      <h1>Sign in</h1>
      {sp.paid ? <p className="okmsg">Thank you, your payment is confirmed. Sign in with your email to continue.</p> : null}
      {sp.error && MESSAGES[sp.error] ? <p className="error" role="alert">{MESSAGES[sp.error]}</p> : null}
      <p>We&apos;ll email you a link. No password needed.</p>
      <form action={loginAction}>
        <input type="hidden" name="next" value={next} />
        <label htmlFor="email">Your email</label>
        <input id="email" name="email" type="email" inputMode="email" autoComplete="email" required autoFocus />
        <div style={{ marginTop: 20 }}><SubmitButton>Email me a sign-in link</SubmitButton></div>
      </form>
    </div>
  );
}
