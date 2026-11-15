-- Atomically transition a mission and its focus session.
-- PostgreSQL executes this function in one transaction: either both updates commit or neither.
CREATE OR REPLACE FUNCTION public.transition_mission_timer(
  p_mission_id UUID,
  p_session_id UUID,
  p_action TEXT
)
RETURNS public.missions
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_mission public.missions%ROWTYPE;
  v_session public.focus_sessions%ROWTYPE;
  v_now TIMESTAMPTZ := clock_timestamp();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Authentication required';
  END IF;

  IF p_action NOT IN ('pause', 'complete') THEN
    RAISE EXCEPTION 'Unsupported timer action: %', p_action;
  END IF;

  -- Lock mission first to serialize concurrent timer actions.
  SELECT * INTO v_mission
  FROM public.missions
  WHERE id = p_mission_id AND user_id = v_user_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Mission not found';
  END IF;

  IF p_session_id IS NOT NULL THEN
    SELECT * INTO v_session
    FROM public.focus_sessions
    WHERE id = p_session_id
      AND mission_id = p_mission_id
      AND user_id = v_user_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Focus session not found for mission';
    END IF;

    IF v_session.ended_at IS NOT NULL THEN
      RAISE EXCEPTION 'Focus session is already closed';
    END IF;

    UPDATE public.focus_sessions
    SET ended_at = v_now,
        duration_minutes = GREATEST(0, ROUND(EXTRACT(EPOCH FROM (v_now - started_at)) / 60)::INTEGER),
        completed = (p_action = 'complete')
    WHERE id = p_session_id;
  END IF;

  UPDATE public.missions
  SET status = CASE WHEN p_action = 'pause' THEN 'paused' ELSE 'completed' END,
      completed_at = CASE WHEN p_action = 'complete' THEN v_now ELSE completed_at END
  WHERE id = p_mission_id
  RETURNING * INTO v_mission;

  RETURN v_mission;
END;
$$;

REVOKE ALL ON FUNCTION public.transition_mission_timer(UUID, UUID, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.transition_mission_timer(UUID, UUID, TEXT) TO authenticated;
