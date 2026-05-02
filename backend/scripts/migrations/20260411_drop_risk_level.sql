-- MySQL/PostgreSQL migration for report risk level cleanup.
-- Execute in maintenance window after verifying backups.
ALTER TABLE t_psych_report DROP COLUMN risk_level;

-- Optional historical cleanup if legacy values persisted in archived table.
-- UPDATE t_psych_report_archive SET risk_level = NULL;
