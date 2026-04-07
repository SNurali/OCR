-- Direct SQL migration for existing PostgreSQL database
-- Run: psql -U ocr_user -d ocr_service -f sql/migrate_production.sql

BEGIN;

-- 1. Add missing columns (IF NOT EXISTS for safety)
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS field_confidence TEXT;
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS engine_used VARCHAR(20);
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS document_type VARCHAR(30);
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS pipeline_stages TEXT;
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS image_hash VARCHAR(64);
ALTER TABLE passport_data ADD COLUMN IF NOT EXISTS duplicate_count INTEGER DEFAULT 1;

-- 2. Add indexes (partial indexes for efficiency)
CREATE INDEX IF NOT EXISTS idx_passport_number ON passport_data(passport_number)
    WHERE passport_number IS NOT NULL AND passport_number != '';

CREATE INDEX IF NOT EXISTS idx_image_hash ON passport_data(image_hash)
    WHERE image_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recognition_status ON passport_data(mrz_valid, passport_number, birth_date);

-- 3. Data cleanup: Convert empty strings to NULL for consistency
UPDATE passport_data SET first_name = NULL WHERE first_name = '';
UPDATE passport_data SET last_name = NULL WHERE last_name = '';
UPDATE passport_data SET middle_name = NULL WHERE middle_name = '';
UPDATE passport_data SET birth_date = NULL WHERE birth_date = '';
UPDATE passport_data SET gender = NULL WHERE gender = '';
UPDATE passport_data SET nationality = NULL WHERE nationality = '';
UPDATE passport_data SET pinfl = NULL WHERE pinfl = '';
UPDATE passport_data SET passport_number = NULL WHERE passport_number = '';
UPDATE passport_data SET passport_series = NULL WHERE passport_series = '';
UPDATE passport_data SET issue_date = NULL WHERE issue_date = '';
UPDATE passport_data SET expiry_date = NULL WHERE expiry_date = '';
UPDATE passport_data SET issued_by = NULL WHERE issued_by = '';
UPDATE passport_data SET mrz_line1 = NULL WHERE mrz_line1 = '';
UPDATE passport_data SET mrz_line2 = NULL WHERE mrz_line2 = '';
UPDATE passport_data SET mrz_line3 = NULL WHERE mrz_line3 = '';

-- 4. Normalize gender values
UPDATE passport_data SET gender = 'M' WHERE UPPER(gender) IN ('MALE', 'МУЖ', 'МУЖЧ', 'ERKAK');
UPDATE passport_data SET gender = 'F' WHERE UPPER(gender) IN ('FEMALE', 'ЖЕН', 'ЖЕНЩ', 'AYOL');

-- 5. Normalize nationality values
UPDATE passport_data SET nationality = 'UZB' WHERE UPPER(nationality) IN ('O''ZBEKISTON', 'UZBEKISTAN', 'O''ZB', 'UZB');
UPDATE passport_data SET nationality = 'RUS' WHERE UPPER(nationality) IN ('РОССИЯ', 'RUSSIA', 'RUS', 'РОССИЙСКАЯ ФЕДЕРАЦИЯ');
UPDATE passport_data SET nationality = 'KAZ' WHERE UPPER(nationality) IN ('KAZAKHSTAN', 'КАЗАХСТАН', 'KAZ');
UPDATE passport_data SET nationality = 'TJK' WHERE UPPER(nationality) IN ('TAJIKISTAN', 'ТАДЖИКИСТАН', 'TJK');

-- 6. Set validation_status based on data quality
UPDATE passport_data SET validation_status = 'valid'
WHERE (
    (passport_number IS NOT NULL AND passport_number != '') AND
    (birth_date IS NOT NULL AND birth_date ~ '^\d{2}\.\d{2}\.\d{4}$')
) OR (
    (passport_number IS NOT NULL AND passport_number != '') AND
    (first_name IS NOT NULL OR last_name IS NOT NULL)
) OR mrz_valid = true;

UPDATE passport_data SET validation_status = 'low_confidence'
WHERE validation_status = 'pending'
AND (
    passport_number IS NOT NULL OR
    birth_date IS NOT NULL OR
    first_name IS NOT NULL OR
    last_name IS NOT NULL OR
    pinfl IS NOT NULL
);

-- 7. Log what was cleaned
DO $$
DECLARE
    nullified_count INTEGER;
    gender_normalized INTEGER;
    nat_normalized INTEGER;
BEGIN
    SELECT COUNT(*) INTO nullified_count FROM passport_data WHERE validation_status = 'low_confidence';
    RAISE NOTICE 'Records marked as low_confidence: %', nullified_count;
END $$;

COMMIT;
