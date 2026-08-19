-- Razorpay Payment System v2 — SQL Migration for MySQL Production
-- Run this script ONCE on your MySQL/production database.
-- Safe to run on existing databases: uses IF NOT EXISTS / IGNORE patterns.
-- Date: 2026

-- ============================================================
-- 1. Add new columns to payments table
-- ============================================================

ALTER TABLE payments
  ADD COLUMN IF NOT EXISTS failure_reason TEXT,
  ADD COLUMN IF NOT EXISTS webhook_verified TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS verified_at DATETIME,
  ADD COLUMN IF NOT EXISTS refund_status VARCHAR(30),
  ADD COLUMN IF NOT EXISTS refund_id VARCHAR(100),
  ADD COLUMN IF NOT EXISTS refund_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00;

-- Index for webhook_verified queries (reconciliation)
CREATE INDEX IF NOT EXISTS idx_payments_webhook_verified
  ON payments(webhook_verified, status);

-- Index for refund queries
CREATE INDEX IF NOT EXISTS idx_payments_refund_status
  ON payments(refund_status);

-- ============================================================
-- 2. Create refund_requests table
-- ============================================================

CREATE TABLE IF NOT EXISTS refund_requests (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  payment_id          INT NOT NULL,
  society_id          INT NOT NULL,
  resident_id         INT,
  requested_amount    DECIMAL(12,2) NOT NULL,
  reason              TEXT NOT NULL,
  status              VARCHAR(30) NOT NULL DEFAULT 'pending',
  admin_notes         TEXT,
  processed_by        INT,
  razorpay_refund_id  VARCHAR(100),
  refunded_amount     DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  processed_at        DATETIME,

  CONSTRAINT fk_rr_payment    FOREIGN KEY (payment_id)   REFERENCES payments(id),
  CONSTRAINT fk_rr_society    FOREIGN KEY (society_id)   REFERENCES societies(id),
  CONSTRAINT fk_rr_resident   FOREIGN KEY (resident_id)  REFERENCES residents(id),
  CONSTRAINT fk_rr_admin      FOREIGN KEY (processed_by) REFERENCES users(id),

  INDEX idx_rr_payment_id   (payment_id),
  INDEX idx_rr_society_id   (society_id),
  INDEX idx_rr_resident_id  (resident_id),
  INDEX idx_rr_status       (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. Ensure webhook_logs.signature_verified column exists
-- ============================================================

ALTER TABLE webhook_logs
  ADD COLUMN IF NOT EXISTS signature_verified TINYINT(1) NOT NULL DEFAULT 0;

-- ============================================================
-- 4. Verification query — run after migration
-- ============================================================
-- SELECT COLUMN_NAME, DATA_TYPE
-- FROM information_schema.COLUMNS
-- WHERE TABLE_SCHEMA = DATABASE()
-- AND TABLE_NAME IN ('payments', 'refund_requests', 'webhook_logs')
-- ORDER BY TABLE_NAME, ORDINAL_POSITION;
