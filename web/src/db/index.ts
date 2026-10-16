import path from "node:path";
import fs from "node:fs";
import { drizzle as drizzlePg, type NodePgDatabase } from "drizzle-orm/node-postgres";
import { migrate as migratePg } from "drizzle-orm/node-postgres/migrator";
import { drizzle as drizzlePglite } from "drizzle-orm/pglite";
import { migrate as migratePglite } from "drizzle-orm/pglite/migrator";
import { PGlite } from "@electric-sql/pglite";
import { Pool } from "pg";
import * as schema from "./schema";
import { env } from "@/env";

// One query API for both drivers (the PGlite driver has the same surface).
export type Db = NodePgDatabase<typeof schema>;

const MIGRATIONS = path.join(process.cwd(), "drizzle");

type Holder = { db?: Promise<Db> };
const g = globalThis as unknown as { __lineageDb?: Holder };
const holder: Holder = (g.__lineageDb ??= {});

/** The app's database. Postgres when DATABASE_URL is set (migrations run separately: npm run db:migrate);
 * otherwise an embedded PGlite in PGLITE_DIR, migrated on first use. */
export function getDb(): Promise<Db> {
  if (!holder.db) holder.db = open();
  return holder.db;
}

async function open(): Promise<Db> {
  const e = env();
  if (e.DATABASE_URL) {
    const pool = new Pool({ connectionString: e.DATABASE_URL, max: 5 });
    return drizzlePg(pool, { schema });
  }
  return createPgliteDb(e.PGLITE_DIR);
}

/** An embedded database, migrated. dir "memory://" gives a throwaway in-memory one (tests). */
export async function createPgliteDb(dir: string): Promise<Db> {
  if (!dir.startsWith("memory://")) fs.mkdirSync(dir, { recursive: true });
  const client = new PGlite(dir);
  const db = drizzlePglite(client, { schema });
  await migratePglite(db, { migrationsFolder: MIGRATIONS });
  return db as unknown as Db;
}

export async function migratePostgres(url: string) {
  const pool = new Pool({ connectionString: url, max: 1 });
  try {
    await migratePg(drizzlePg(pool, { schema }), { migrationsFolder: MIGRATIONS });
  } finally {
    await pool.end();
  }
}

/** tests: use this database instead */
export function setDb(db: Db) {
  holder.db = Promise.resolve(db);
}

export { schema };
