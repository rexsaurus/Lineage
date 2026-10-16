"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { getDb } from "@/db";
import { events } from "@/db/schema";
import { cleanText, normalizeEmail } from "@/lib/crypto";
import { normalizeSrc, isSlug, SRC_COOKIE } from "@/lib/src";
import { startSignup } from "@/lib/start";
import { createMagicLink, safeRedirect } from "@/lib/magic";
import { sendInviteEmail, sendMagicLinkEmail } from "@/lib/emails";
import { currentUser, requireAdmin, requireUser, signIn, signOut } from "@/lib/auth";
import { createFamily, deleteFamily, familyForViewer, familiesOf } from "@/lib/families";
import { acceptInvite, createInvite } from "@/lib/invites";
import { upsertUser } from "@/lib/users";
import { PAYMENT_LINK_FALLBACK, setSetting } from "@/lib/settings";

async function srcFrom(form: FormData) {
  const f = form.get("src");
  if (isSlug(f)) return f as string;
  return normalizeSrc((await cookies()).get(SRC_COOKIE)?.value);
}

// ---- §3.1 / §3.3 start
export async function startAction(form: FormData) {
  const src = await srcFrom(form);
  const email = normalizeEmail(form.get("email"));
  if (!email) redirect(`/start?error=email&src=${encodeURIComponent(src)}`);
  const db = await getDb();
  const r = await startSignup(db, { email, src });
  if (r.kind === "reserved") {
    // price not set: no payment. A brand-new account is signed in on this device (and gets a link for next time);
    // an existing account must use the emailed link, so nobody can sign in as someone else by typing their email.
    await sendMagicLinkEmail(db, email, await createMagicLink(db, email, "/family/new"));
    if (r.user.lastLoginAt) redirect("/login?sent=1");
    await signIn(r.user.id);
    redirect(await nextStepFor(r.user.id));
  }
  redirect(r.url);
}

async function nextStepFor(userId: string) {
  const fams = await familiesOf(await getDb(), userId);
  return fams.length ? `/family/${fams[0].id}` : "/family/new";
}

// ---- §3.2 login
export async function loginAction(form: FormData) {
  const email = normalizeEmail(form.get("email"));
  const next = safeRedirect(form.get("next")) || null;
  if (!email) redirect(`/login?error=email${next ? `&next=${encodeURIComponent(next)}` : ""}`);
  const db = await getDb();
  await upsertUser(db, { email, src: await srcFrom(form), role: next?.startsWith("/invite/") ? "member" : "archivist" });
  await sendMagicLinkEmail(db, email, await createMagicLink(db, email, next));
  // the same answer whether or not the address was known
  redirect(`/login?sent=1${next ? `&next=${encodeURIComponent(next)}` : ""}`);
}

export async function signOutAction() {
  await signOut();
  redirect("/");
}

// ---- create family
export async function createFamilyAction(form: FormData) {
  const u = await requireUser("/family/new");
  const name = cleanText(form.get("name"), 80);
  const yourName = cleanText(form.get("yourName"), 80);
  if (!name) redirect("/family/new?error=name");
  const db = await getDb();
  if (yourName && !u.name) {
    const { users } = await import("@/db/schema");
    const { eq } = await import("drizzle-orm");
    await db.update(users).set({ name: yourName }).where(eq(users.id, u.id));
  }
  const f = await createFamily(db, { name, userId: u.id, src: u.eventSource || (await srcFrom(form)) });
  redirect(`/family/${f.id}/upload`);
}

// ---- §3.1 invite
export async function inviteAction(form: FormData) {
  const familyId = String(form.get("familyId") || "");
  const u = await requireUser(`/family/${familyId}/invite`);
  const db = await getDb();
  const f = await familyForViewer(db, familyId, u);
  if (!f) redirect("/");
  const email = normalizeEmail(form.get("email"));
  const name = cleanText(form.get("name"), 80) || null;
  if (!email) redirect(`/family/${f.id}/invite?error=email`);
  const inv = await createInvite(db, { familyId: f.id, invitedBy: u.id, email, name, src: f.eventSource });
  await sendInviteEmail(db, { to: email, toName: name, fromName: u.name || u.email, familyName: f.name, token: inv.token });
  redirect(`/family/${f.id}/invite?sent=1&t=${inv.token}`);
}

/** The "Copy invite link" / Share path: a link without an email. */
export async function inviteLinkAction(form: FormData) {
  const familyId = String(form.get("familyId") || "");
  const u = await requireUser(`/family/${familyId}/invite`);
  const db = await getDb();
  const f = await familyForViewer(db, familyId, u);
  if (!f) redirect("/");
  const inv = await createInvite(db, { familyId: f.id, invitedBy: u.id, email: null, name: null, src: f.eventSource });
  redirect(`/family/${f.id}/invite?t=${inv.token}`);
}

// ---- §3.4 accept
export async function acceptInviteAction(form: FormData) {
  const token = String(form.get("token") || "");
  const u = await currentUser();
  if (!u) redirect(`/invite/${encodeURIComponent(token)}`);
  const r = await acceptInvite(await getDb(), token, u.id);
  if (!r.ok) redirect(`/invite/${encodeURIComponent(token)}?error=used`);
  redirect(`/family/${r.familyId}`);
}

// ---- admin (§9, §10, §6 fallback, §12 delete)
export async function adminSaveEvent(form: FormData) {
  await requireAdmin();
  const slug = String(form.get("slug") || "").trim().toLowerCase();
  if (!isSlug(slug)) redirect("/admin/qr?error=slug");
  const startsAt = String(form.get("startsAt") || "");
  const values = {
    slug,
    name: cleanText(form.get("name"), 120) || null,
    venue: cleanText(form.get("venue"), 120) || null,
    startsAt: /^\d{4}-\d{2}-\d{2}/.test(startsAt) ? new Date(startsAt) : null,
  };
  const db = await getDb();
  await db.insert(events).values(values).onConflictDoUpdate({ target: events.slug, set: values });
  revalidatePath("/admin/qr");
  redirect(`/admin/qr?saved=${slug}`);
}

export async function adminDeleteFamily(form: FormData) {
  await requireAdmin();
  const id = String(form.get("familyId") || "");
  if (String(form.get("confirm") || "") !== "DELETE") redirect("/admin?error=confirm");
  await deleteFamily(await getDb(), id);
  redirect("/admin?deleted=1");
}

export async function adminToggleFallback(form: FormData) {
  await requireAdmin();
  await setSetting(await getDb(), PAYMENT_LINK_FALLBACK, form.get("on") === "on" ? "on" : "off");
  redirect("/admin");
}

export async function adminSetDemoSrc(form: FormData) {
  await requireAdmin();
  const slug = String(form.get("slug") || "");
  const jar = await cookies();
  if (isSlug(slug)) jar.set("lineage_demo_src", slug, { maxAge: 30 * 86400, path: "/", sameSite: "lax", httpOnly: true });
  else jar.delete("lineage_demo_src");
  redirect("/admin");
}
