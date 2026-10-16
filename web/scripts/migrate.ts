// npm run db:migrate — apply drizzle/ migrations to DATABASE_URL (Postgres). PGlite migrates itself on first use.
import { migratePostgres } from "@/db";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("DATABASE_URL is not set (PGlite needs no migration step).");
  process.exit(1);
}
migratePostgres(url)
  .then(() => console.log("migrations applied"))
  .catch(err => {
    console.error("migration failed:", err instanceof Error ? err.message : err);
    process.exit(1);
  });
