import type { Db } from "@/db";
import { env } from "@/env";
import { sendLogged } from "./mail";

// The words of every email the app sends. Plain text, short, large-print friendly (spec §7).
const firstName = (name: string | null | undefined) => (name || "").trim().split(/\s+/)[0] || "there";
const url = (p: string) => new URL(p, env().APP_URL).toString();

export async function sendMagicLinkEmail(db: Db, to: string, token: string) {
  return sendLogged(db, {
    to,
    kind: "magic-link",
    subject: "Your Lineage sign-in link",
    text: `Here is your link to sign in to Lineage:\n\n${url(`/api/auth/callback?token=${token}`)}\n\nIt works once, for the next 15 minutes. If you didn't ask for it, you can ignore this email.\n\n— Rex at Lineage`,
  });
}

export async function sendInviteEmail(db: Db, a: { to: string; toName: string | null; fromName: string; familyName: string; token: string }) {
  return sendLogged(db, {
    to: a.to,
    kind: "invite",
    subject: `${a.fromName} invited you to the ${a.familyName} page on Lineage`,
    text: `Hi ${firstName(a.toName)},\n\n${a.fromName} has started a family history page for ${a.familyName} on Lineage and would like you to see it, and add any photos or papers you have.\n\nOpen the invitation:\n${url(`/invite/${a.token}`)}\n\n— Rex at Lineage`,
  });
}

export async function sendFollowupEmail(db: Db, a: { to: string; name: string | null; eventName: string | null; familyName: string; familyId: string }) {
  const where = a.eventName ? `at ${a.eventName}` : "";
  return sendLogged(db, {
    to: a.to,
    kind: "followup",
    dedupeKey: `followup:${a.familyId}`,
    subject: `Your ${a.familyName} page is live`,
    text: `Hi ${firstName(a.name)},\n\nIt was great to meet you${where ? " " + where : ""}. Your family page is here: ${url(`/family/${a.familyId}`)}\n\nTwo things to do this week: add a few more photos or documents, and invite one relative who'd love to see them: ${url(`/family/${a.familyId}/invite`)}\n\nJust reply to this email if you have a question. I read every one.\n\n— Rex\n\n(You're getting this because you started a family page on Lineage. Reply "stop" and I won't write again.)`,
  });
}

export async function sendNudgeEmail(db: Db, a: { to: string; name: string | null; userId: string; familyId: string | null }) {
  const next = a.familyId ? `/family/${a.familyId}/upload` : "/family/new";
  return sendLogged(db, {
    to: a.to,
    kind: "nudge",
    dedupeKey: `nudge:${a.userId}`,
    subject: "Your Lineage family page is waiting",
    text: `Hi ${firstName(a.name)},\n\nIt was great to meet you. Your family page is ready for its first photo or document: ${url(next)}\n\nYou can take a photo of an old picture or letter with your phone. Just reply to this email if you have a question.\n\n— Rex\n\n(You're getting this because you started a family page on Lineage. Reply "stop" and I won't write again.)`,
  });
}
