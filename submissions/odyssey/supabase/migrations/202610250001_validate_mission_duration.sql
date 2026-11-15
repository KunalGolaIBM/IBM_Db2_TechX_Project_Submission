-- Bring legacy invalid targets to the 25-minute fallback shown by the timer.
UPDATE public.missions
SET planned_minutes = 25
WHERE planned_minutes IS NULL OR planned_minutes NOT BETWEEN 1 AND 240;

ALTER TABLE public.missions
  ALTER COLUMN planned_minutes SET DEFAULT 25,
  ALTER COLUMN planned_minutes SET NOT NULL,
  ADD CONSTRAINT missions_planned_minutes_range CHECK (planned_minutes BETWEEN 1 AND 240);
