import { describe, expect, it } from "vitest";
import { users } from "@/db/schema";
import { checkUpload, sniff, stripJpeg, stripPng, MAX_UPLOAD_BYTES } from "@/lib/files";
import { createFamily, familyForViewer, familyNumber, listRecords, deleteFamily } from "@/lib/families";
import { createInvite, acceptInvite } from "@/lib/invites";
import { acceptUpload } from "@/lib/upload";
import { computeKpis, kpiCsv, kpisByEvent, kpiByEventCsv } from "@/lib/kpi";
import { runNudges } from "@/lib/followup";
import { ctx, sent, blobs } from "./setup";
import type { Viewer } from "@/lib/auth";

// a tiny JPEG: SOI, APP1 Exif carrying a GPS marker, APP0 JFIF, then SOS + data + EOI
function jpegWithGps() {
  const app1Body = Buffer.concat([Buffer.from("Exif\0\0"), Buffer.from("GPSLatitude=37.77;GPSLongitude=-122.41")]);
  const app1 = Buffer.concat([Buffer.from([0xff, 0xe1]), u16(app1Body.length + 2), app1Body]);
  const app0Body = Buffer.from("JFIF\0\x01\x01\0\0\x01\0\x01\0\0", "latin1");
  const app0 = Buffer.concat([Buffer.from([0xff, 0xe0]), u16(app0Body.length + 2), app0Body]);
  const sos = Buffer.from([0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0x12, 0x34, 0xff, 0xd9]);
  return Buffer.concat([Buffer.from([0xff, 0xd8]), app1, app0, sos]);
}
function u16(n: number) { const b = Buffer.alloc(2); b.writeUInt16BE(n); return b; }
function pngWithExif() {
  const chunk = (type: string, data: Buffer) => { const l = Buffer.alloc(4); l.writeUInt32BE(data.length); return Buffer.concat([l, Buffer.from(type), data, Buffer.alloc(4)]); };
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", Buffer.alloc(13)), chunk("eXIf", Buffer.from("GPS here")), chunk("tEXt", Buffer.from("Comment")), chunk("IDAT", Buffer.alloc(4)), chunk("IEND", Buffer.alloc(0))]);
}

async function viewer(email: string, role = "archivist"): Promise<Viewer> {
  const [u] = await ctx.db.insert(users).values({ email, role }).returning();
  return { ...u, isAdmin: email === "rex@example.org" };
}

describe("uploads", () => {
  it("accepts JPEG, PNG, HEIC and PDF by their bytes; rejects others and anything over 25 MB", () => {
    expect(sniff(jpegWithGps())?.mime).toBe("image/jpeg");
    expect(sniff(pngWithExif())?.mime).toBe("image/png");
    expect(sniff(Buffer.concat([Buffer.from([0, 0, 0, 0x18]), Buffer.from("ftypheic"), Buffer.alloc(8)]))?.mime).toBe("image/heic");
    expect(sniff(Buffer.from("%PDF-1.7\n..."))?.mime).toBe("application/pdf");
    expect(checkUpload(Buffer.from("MZ executable")).ok).toBe(false);
    const big = Buffer.alloc(MAX_UPLOAD_BYTES + 1);
    big.write("%PDF-");
    const r = checkUpload(big);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.message).toMatch(/25 MB/);
  });

  it("strips GPS/EXIF from JPEG and PNG, keeping the image", () => {
    const j = stripJpeg(jpegWithGps());
    expect(j.includes(Buffer.from("GPSLatitude"))).toBe(false);
    expect(j.includes(Buffer.from("JFIF"))).toBe(true);
    expect(j.subarray(-2)).toEqual(Buffer.from([0xff, 0xd9]));
    const p = stripPng(pngWithExif());
    expect(p.includes(Buffer.from("GPS here"))).toBe(false);
    expect(p.includes(Buffer.from("IDAT"))).toBe(true);
  });

  it("stores the stripped file, records it, and sends the follow-up once", async () => {
    const v = await viewer("arch@example.org");
    const f = await createFamily(ctx.db, { name: "The Calders", userId: v.id, src: "e1" });
    const r = await acceptUpload(ctx.db, { viewer: v, familyId: f.id, bytes: jpegWithGps(), caption: "Grandma Rose, 1952" });
    expect(r.ok).toBe(true);
    const stored = [...blobs.values()][0];
    expect(stored.includes(Buffer.from("GPSLatitude"))).toBe(false);
    expect(sent.filter(m => m.kind === "followup")).toHaveLength(1);
    expect(sent[0].subject).toBe("Your The Calders page is live");
    await acceptUpload(ctx.db, { viewer: v, familyId: f.id, bytes: pngWithExif(), caption: "" });
    expect(sent.filter(m => m.kind === "followup")).toHaveLength(1); // never twice
    expect(await listRecords(ctx.db, f.id)).toHaveLength(2);
  });

  it("non-members can't see or upload to a family", async () => {
    const owner = await viewer("o@example.org");
    const stranger = await viewer("s@example.org");
    const admin = await viewer("rex@example.org", "admin");
    const f = await createFamily(ctx.db, { name: "Private", userId: owner.id, src: null });
    expect(await familyForViewer(ctx.db, f.id, stranger)).toBeNull();
    expect(await familyForViewer(ctx.db, f.id, null)).toBeNull();
    expect(await familyForViewer(ctx.db, f.id, owner)).not.toBeNull();
    expect(await familyForViewer(ctx.db, f.id, admin)).not.toBeNull();
    const r = await acceptUpload(ctx.db, { viewer: stranger, familyId: f.id, bytes: jpegWithGps(), caption: "" });
    expect(r).toMatchObject({ ok: false, status: 404 });
  });

  it("admin delete removes the family, its records and their files", async () => {
    const v = await viewer("del@example.org");
    const f = await createFamily(ctx.db, { name: "Gone", userId: v.id, src: null });
    await acceptUpload(ctx.db, { viewer: v, familyId: f.id, bytes: jpegWithGps(), caption: "" });
    expect(blobs.size).toBe(1);
    await deleteFamily(ctx.db, f.id);
    expect(blobs.size).toBe(0);
    expect(await listRecords(ctx.db, f.id)).toHaveLength(0);
  });
});

describe("invites", () => {
  it("a token is accepted once; the invitee becomes a member", async () => {
    const owner = await viewer("own@example.org");
    const f = await createFamily(ctx.db, { name: "Fam", userId: owner.id, src: "e1" });
    const inv = await createInvite(ctx.db, { familyId: f.id, invitedBy: owner.id, email: "cousin@example.org", name: "Cousin", src: "e1" });
    const cousin = await viewer("cousin@example.org", "member");
    const other = await viewer("other@example.org", "member");
    expect(await acceptInvite(ctx.db, inv.token, cousin.id)).toEqual({ ok: true, familyId: f.id });
    expect(await familyForViewer(ctx.db, f.id, cousin)).not.toBeNull();
    expect((await acceptInvite(ctx.db, inv.token, other.id)).ok).toBe(false);
    expect(await familyForViewer(ctx.db, f.id, other)).toBeNull();
    expect((await acceptInvite(ctx.db, inv.token, cousin.id)).ok).toBe(true); // the same person again is fine
  });
});

describe("KPIs", () => {
  it("count only real families with an archivist and a record; demo and admin excluded", async () => {
    const a = await viewer("a1@example.org");
    const b = await viewer("b1@example.org");
    const admin = await viewer("rex@example.org", "admin");
    const indexed = await createFamily(ctx.db, { name: "Indexed", userId: a.id, src: "e1" });
    await acceptUpload(ctx.db, { viewer: a, familyId: indexed.id, bytes: jpegWithGps(), caption: "" });
    await createFamily(ctx.db, { name: "No records yet", userId: b.id, src: "e2" });
    const demo = await createFamily(ctx.db, { name: "Demo", userId: a.id, src: "e1", isDemo: true });
    await acceptUpload(ctx.db, { viewer: a, familyId: demo.id, bytes: jpegWithGps(), caption: "" });
    const adminFam = await createFamily(ctx.db, { name: "Rex's own", userId: admin.id, src: "e1" });
    await acceptUpload(ctx.db, { viewer: admin, familyId: adminFam.id, bytes: jpegWithGps(), caption: "" });
    const inv = await createInvite(ctx.db, { familyId: indexed.id, invitedBy: a.id, email: "x@example.org", name: null, src: "e1" });
    const x = await viewer("x@example.org", "member");
    await acceptInvite(ctx.db, inv.token, x.id);

    const k = await computeKpis(ctx.db);
    expect(k).toEqual({ families_indexed: 1, archivists_added: 2, records_uploaded: 1, invites_sent: 1, invites_accepted: 1, paid_signups: 0 });
    expect(kpiCsv(k, "2026-10-20")).toBe("date,families,archivists\n2026-10-20,1,2\n");
    const byEvent = await kpisByEvent(ctx.db);
    expect(byEvent.find(r => r.event_source === "e1")).toMatchObject({ families_indexed: 1, archivists_added: 1, records_uploaded: 1 });
    expect(byEvent.find(r => r.event_source === "e2")).toMatchObject({ families_indexed: 0, archivists_added: 1, records_uploaded: 0 });
    expect(kpiByEventCsv(byEvent, "2026-10-20").split("\n")[0]).toBe("date,event_source,families,archivists,records,paid");
    expect(await familyNumber(ctx.db, indexed)).toBe(1);
    expect(await familyNumber(ctx.db, demo)).toBeNull();
  });
});

describe("follow-up cron", () => {
  it("nudges archivists with no records after an hour, once", async () => {
    const v = await viewer("late@example.org");
    await createFamily(ctx.db, { name: "Waiting", userId: v.id, src: null });
    expect(await runNudges(ctx.db, new Date())).toBe(0); // too soon
    const later = new Date(Date.now() + 61 * 60_000);
    expect(await runNudges(ctx.db, later)).toBe(1);
    expect(await runNudges(ctx.db, later)).toBe(0); // never twice
    expect(sent.at(-1)?.kind).toBe("nudge");
  });
});
