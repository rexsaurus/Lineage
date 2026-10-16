-- Spec §9: the known upcoming meetings, slug only (Rex to confirm names, venues and times in /admin/qr).
INSERT INTO "events" ("slug") VALUES
  ('smcgs-2026-10-17'),
  ('scchgs-writing-2026-10-20'),
  ('scchgs-meeting-2026-10-20'),
  ('scchgs-consult-2026-10-21'),
  ('nara-oakland-2026-10-21'),
  ('familysearch-sc-2026-10-22'),
  ('cgs-berkeley-2026-10-24')
ON CONFLICT ("slug") DO NOTHING;
