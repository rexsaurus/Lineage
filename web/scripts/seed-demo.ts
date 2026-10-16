// npm run seed:demo -- <folder> [--name "The St. John Family"]
// Seeds the read-only demo family (spec §10) from a local folder of images/PDFs that Rex chooses. A file's caption is
// its name without the extension ("1952 wedding.jpg" → "1952 wedding"). Without a folder, nothing is seeded and /demo
// shows labelled placeholders. Re-running replaces the previous demo family.
import fs from "node:fs";
import path from "node:path";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { families } from "@/db/schema";
import { checkUpload } from "@/lib/files";
import { addRecord, createFamily, deleteFamily } from "@/lib/families";
import { upsertUser } from "@/lib/users";

async function main() {
  const args = process.argv.slice(2);
  const dir = args.find(a => !a.startsWith("--"));
  const ni = args.indexOf("--name");
  const name = ni >= 0 ? args[ni + 1] : "Demo family";
  if (!dir || !fs.existsSync(dir)) {
    console.error("usage: npm run seed:demo -- <folder of demo images/PDFs> [--name \"Family name\"]");
    process.exit(1);
  }
  const db = await getDb();
  for (const f of await db.select().from(families).where(eq(families.isDemo, true))) await deleteFamily(db, f.id);
  const owner = await upsertUser(db, { email: "demo@lineage.invalid", src: "direct", role: "admin" });
  const fam = await createFamily(db, { name, userId: owner.id, src: null, isDemo: true });
  let n = 0;
  for (const file of fs.readdirSync(dir).sort()) {
    const c = checkUpload(fs.readFileSync(path.join(dir, file)));
    if (!c.ok) {
      console.log(`skipped ${file}: ${c.message}`);
      continue;
    }
    await addRecord(db, { familyId: fam.id, userId: owner.id, body: c.body, sniffed: c.sniffed, caption: path.parse(file).name });
    n++;
  }
  console.log(`demo family "${name}" seeded with ${n} records`);
  process.exit(0);
}
main();
