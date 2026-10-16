import { createFamilyAction } from "../../actions";
import { SubmitButton } from "@/components/SubmitButton";
import { requireUser } from "@/lib/auth";

export const metadata = { title: "Create your family page" };

export default async function NewFamily({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const u = await requireUser("/family/new");
  const sp = await searchParams;
  return (
    <div className="page">
      <p className="steps">Step 2 of 4</p>
      <h1>Name your family page</h1>
      <form action={createFamilyAction}>
        <label htmlFor="name">Family name</label>
        <input id="name" name="name" required maxLength={80} placeholder="e.g. The Moser Family" autoComplete="off" autoFocus aria-describedby="name-err" />
        {sp.error === "name" ? <p id="name-err" className="error" role="alert">Please type a family name.</p> : null}
        {u.name ? null : (
          <>
            <label htmlFor="yourName">Your name <span className="muted small">(optional)</span></label>
            <input id="yourName" name="yourName" maxLength={80} autoComplete="name" />
          </>
        )}
        <div style={{ marginTop: 20 }}><SubmitButton>Create my family page</SubmitButton></div>
      </form>
    </div>
  );
}
