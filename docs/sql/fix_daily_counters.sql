-- Fix daily_counters table to use updated_at instead of last_updated

-- Drop the incorrect table
DROP TABLE IF EXISTS daily_counters;

-- Recreate with correct column names
CREATE TABLE IF NOT EXISTS daily_counters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_counters_user_date ON daily_counters(username, date);

-- Apply the trigger
DROP TRIGGER IF EXISTS update_daily_counters_updated_at ON daily_counters;
CREATE TRIGGER update_daily_counters_updated_at 
    BEFORE UPDATE ON daily_counters 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
