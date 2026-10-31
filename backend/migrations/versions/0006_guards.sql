-- New revision; previous SQL resources remain frozen.
ALTER TABLE public.credit_ledger_entries DROP CONSTRAINT ck_collection_ledger;
ALTER TABLE public.credit_ledger_entries ADD CONSTRAINT ck_collection_ledger CHECK (
 (reason NOT IN ('collection_reservation','collection_release','collection_reward') AND project_id IS NULL) OR
 (reason='collection_reservation' AND project_id IS NOT NULL AND amount<0 AND reversal_of_id IS NULL AND idempotency_key='reservation:v1:'||project_id::text) OR
 (reason='collection_release' AND project_id IS NOT NULL AND amount>0 AND reversal_of_id IS NOT NULL AND idempotency_key='release:v1:'||project_id::text) OR
 (reason='collection_reward' AND project_id IS NOT NULL AND amount>0 AND reversal_of_id IS NULL));

CREATE OR REPLACE FUNCTION public.lock_ledger_wallet() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 -- Positive escrow rewards cannot overdraw a wallet. Lock the escrow project,
 -- avoiding recipient-user / authenticated eligibility lock inversion.
 IF NEW.reason='collection_reward' THEN
   PERFORM 1 FROM public.projects WHERE id=NEW.project_id FOR UPDATE;
 ELSE PERFORM 1 FROM public.users WHERE id=NEW.user_id FOR UPDATE; END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION public.guard_moderation_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE s public.submissions%ROWTYPE; p public.projects%ROWTYPE; r public.project_reservations%ROWTYPE;
 body json; paid bigint; entry public.credit_ledger_entries%ROWTYPE;
BEGIN
 SELECT * INTO s FROM public.submissions WHERE id=NEW.submission_id;
 SELECT * INTO p FROM public.projects WHERE id=s.project_id FOR UPDATE;
 SELECT * INTO s FROM public.submissions WHERE id=NEW.submission_id FOR UPDATE;
 IF s.id IS NULL OR s.workflow_version IS DISTINCT FROM 1 OR s.status<>'pending'
    OR p.status NOT IN ('published','paused') OR s.contributor_id=NEW.reviewer_id
    OR s.contributor_id=p.owner_id
 THEN RAISE EXCEPTION 'Submission is not reviewable'; END IF;
 IF p.owner_id<>NEW.reviewer_id AND NOT EXISTS(SELECT 1 FROM public.project_moderators
    WHERE project_id=p.id AND user_id=NEW.reviewer_id AND revoked_at IS NULL)
 THEN RAISE EXCEPTION 'Reviewer permission required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=NEW.reviewer_id AND email_verified_at IS NOT NULL AND disabled_at IS NULL)
 THEN RAISE EXCEPTION 'Verified reviewer required'; END IF;
 IF NEW.outcome='approved' THEN
   IF s.hidden_at IS NOT NULL OR s.image_deleted_at IS NOT NULL OR EXISTS(
       SELECT 1 FROM public.removal_requests WHERE submission_id=s.id)
   THEN RAISE EXCEPTION 'Image restricted'; END IF;
   SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=s.criteria_version;
   SELECT * INTO r FROM public.project_reservations WHERE project_id=p.id;
   SELECT COALESCE(SUM(d.reward),0) INTO paid FROM public.moderation_decisions d
     JOIN public.submissions x ON x.id=d.submission_id WHERE x.project_id=p.id;
   IF r.id IS NULL OR r.release_entry_id IS NOT NULL OR NEW.reward<>(body->>'reward_per_image')::bigint
       OR paid+NEW.reward>r.amount OR (SELECT COUNT(*) FROM public.submissions WHERE project_id=p.id AND status='approved') >= (body->>'image_count')::integer
   THEN RAISE EXCEPTION 'Insufficient reserved approval capacity'; END IF;
   SELECT * INTO entry FROM public.credit_ledger_entries WHERE id=NEW.reward_entry_id;
   IF entry.id IS NULL OR entry.reason<>'collection_reward' OR entry.amount<>NEW.reward
       OR entry.user_id<>s.contributor_id OR entry.project_id IS DISTINCT FROM p.id
       OR entry.idempotency_key<>'reward:v1:'||s.id::text
   THEN RAISE EXCEPTION 'Reward ledger mismatch'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER moderation_decision_guard BEFORE INSERT ON public.moderation_decisions
FOR EACH ROW EXECUTE FUNCTION public.guard_moderation_decision();
CREATE TRIGGER moderation_immutable BEFORE UPDATE OR DELETE ON public.moderation_decisions
FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER moderation_no_truncate BEFORE TRUNCATE ON public.moderation_decisions
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE FUNCTION public.guard_project_moderator() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE owner_id uuid;
BEGIN
 SELECT p.owner_id INTO owner_id FROM public.projects p WHERE p.id=NEW.project_id FOR UPDATE;
 IF NEW.granted_by IS DISTINCT FROM owner_id OR NEW.user_id=owner_id
 THEN RAISE EXCEPTION 'Only owners designate other reviewers'; END IF;
 IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'revoked_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at')
 THEN RAISE EXCEPTION 'Moderator identity immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER moderator_guard BEFORE INSERT OR UPDATE ON public.project_moderators
FOR EACH ROW EXECUTE FUNCTION public.guard_project_moderator();
CREATE TRIGGER moderator_no_delete BEFORE DELETE ON public.project_moderators
FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER moderator_no_truncate BEFORE TRUNCATE ON public.project_moderators
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE OR REPLACE FUNCTION public.assert_project_funding(target uuid) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; r public.project_reservations%ROWTYPE;
 d public.credit_ledger_entries%ROWTYPE; c public.credit_ledger_entries%ROWTYPE;
 body json; budget bigint; spent bigint; events integer; rewards integer;
BEGIN
 SELECT * INTO p FROM public.projects WHERE id=target;
 IF NOT FOUND THEN RETURN; END IF;
 IF p.current_version>0 THEN
   SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=p.current_version;
   IF NOT FOUND OR body->>'name' IS DISTINCT FROM p.name OR body->>'description' IS DISTINCT FROM p.description
      OR body->>'category' IS DISTINCT FROM p.category THEN RAISE EXCEPTION 'Project snapshot mismatch'; END IF;
 END IF;
 IF p.status IN ('published','paused') AND (p.published_version IS NULL OR p.published_version<>p.current_version OR p.current_version<1)
 THEN RAISE EXCEPTION 'Published snapshot required'; END IF;
 SELECT * INTO r FROM public.project_reservations WHERE project_id=p.id;
 SELECT COUNT(*) INTO events FROM public.credit_ledger_entries WHERE project_id=p.id;
 IF r.id IS NULL THEN
   IF p.status IN ('published','paused') OR p.published_version IS NOT NULL OR events<>0 THEN RAISE EXCEPTION 'Funded reservation required'; END IF;
   RETURN;
 END IF;
 IF p.published_version IS NULL OR p.published_version<>p.current_version OR p.status='draft'
 THEN RAISE EXCEPTION 'Reservation requires published snapshot'; END IF;
 budget:=(body->>'image_count')::bigint*(body->>'reward_per_image')::bigint;
 IF budget IS NULL OR budget<=0 OR r.amount<>budget THEN RAISE EXCEPTION 'Reservation budget mismatch'; END IF;
 SELECT * INTO d FROM public.credit_ledger_entries WHERE id=r.debit_entry_id;
 IF d.id IS NULL OR d.user_id<>p.owner_id OR d.project_id IS DISTINCT FROM p.id OR d.amount<>-r.amount OR d.reason<>'collection_reservation'
 THEN RAISE EXCEPTION 'Reservation debit mismatch'; END IF;
 -- Every terminal workflow-1 submission has exactly one immutable decision, and
 -- every reward is attached to its exact approved decision/recipient/project.
 IF EXISTS(SELECT 1 FROM public.submissions s LEFT JOIN public.moderation_decisions m ON m.submission_id=s.id
     WHERE s.project_id=p.id AND s.workflow_version=1 AND
      ((s.status IN ('approved','rejected') AND (m.id IS NULL OR m.outcome<>s.status))
       OR (m.id IS NOT NULL AND m.outcome<>s.status)))
 THEN RAISE EXCEPTION 'Submission decision mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM public.credit_ledger_entries e LEFT JOIN public.moderation_decisions m ON m.reward_entry_id=e.id
     LEFT JOIN public.submissions s ON s.id=m.submission_id WHERE e.project_id=p.id AND e.reason='collection_reward'
       AND (m.id IS NULL OR m.outcome<>'approved' OR s.project_id<>p.id OR s.contributor_id<>e.user_id
          OR e.amount<>m.reward OR e.idempotency_key<>'reward:v1:'||s.id::text))
 THEN RAISE EXCEPTION 'Orphan or mismatched reward'; END IF;
 SELECT COALESCE(SUM(amount),0),COUNT(*) INTO spent,rewards FROM public.credit_ledger_entries
 WHERE project_id=p.id AND reason='collection_reward';
 IF spent>r.amount OR rewards>(body->>'image_count')::integer THEN RAISE EXCEPTION 'Escrow overspend'; END IF;
 IF p.status IN ('published','paused') THEN
   IF r.release_entry_id IS NOT NULL OR events<>1+rewards THEN RAISE EXCEPTION 'Held funding mismatch'; END IF;
 ELSIF p.status='closed' THEN
   IF EXISTS(SELECT 1 FROM public.submissions WHERE project_id=p.id AND
     (status='pending' OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp())))
   THEN RAISE EXCEPTION 'Outstanding submissions retain funding'; END IF;
   IF spent=r.amount THEN
     IF r.release_entry_id IS NOT NULL OR events<>1+rewards THEN RAISE EXCEPTION 'Exhausted escrow mismatch'; END IF;
   ELSE
     SELECT * INTO c FROM public.credit_ledger_entries WHERE id=r.release_entry_id;
     IF c.id IS NULL OR c.user_id<>p.owner_id OR c.project_id IS DISTINCT FROM p.id OR c.amount<>r.amount-spent
       OR c.reason<>'collection_release' OR c.reversal_of_id IS DISTINCT FROM d.id OR events<>2+rewards
     THEN RAISE EXCEPTION 'Remaining escrow release mismatch'; END IF;
   END IF;
 ELSE RAISE EXCEPTION 'Invalid funded state'; END IF;
END; $$;
CREATE FUNCTION public.check_moderation_funding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE target uuid;
BEGIN
 SELECT project_id INTO target FROM public.submissions WHERE id=NEW.submission_id;
 PERFORM public.assert_project_funding(target);
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER decision_funding_complete AFTER INSERT ON public.moderation_decisions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_moderation_funding();
CREATE CONSTRAINT TRIGGER submission_funding_complete AFTER INSERT OR UPDATE ON public.submissions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_project_funding();
CREATE OR REPLACE FUNCTION public.guard_submission() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; body json; used integer; own_used integer; slots integer;
BEGIN
 IF TG_OP='UPDATE' THEN
   IF OLD.workflow_version IS NULL THEN RAISE EXCEPTION 'Legacy submissions require separate review'; END IF;
   IF (to_jsonb(NEW) - ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at','image_deleted_at']) IS DISTINCT FROM
      (to_jsonb(OLD) - ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at','image_deleted_at'])
   THEN RAISE EXCEPTION 'Submission provenance is immutable'; END IF;
   IF NEW.image_deleted_at IS DISTINCT FROM OLD.image_deleted_at AND
      (OLD.image_deleted_at IS NOT NULL OR NEW.image_deleted_at IS NULL OR NOT
       (OLD.hidden_at IS NOT NULL OR (OLD.status='rejected' AND EXISTS(
         SELECT 1 FROM public.moderation_decisions WHERE submission_id=OLD.id
         AND created_at < clock_timestamp()-interval '30 days'))))
   THEN RAISE EXCEPTION 'Invalid image retention deletion'; END IF;
   IF OLD.status='pending' AND NEW.status IN ('approved','rejected') THEN
     IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status')
        OR NOT EXISTS(SELECT 1 FROM public.moderation_decisions WHERE submission_id=OLD.id AND outcome=NEW.status)
     THEN RAISE EXCEPTION 'Audited decision required'; END IF;
     RETURN NEW;
   END IF;
   IF OLD.status <> 'uploading'  OR OLD.abandoned_at IS NOT NULL THEN
     IF (to_jsonb(NEW) - ARRAY['hidden_at','image_deleted_at']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['hidden_at','image_deleted_at'])
     THEN RAISE EXCEPTION 'Completed/expired submission is immutable'; END IF;
   END IF;
   IF OLD.hidden_at IS NOT NULL AND NEW.hidden_at IS DISTINCT FROM OLD.hidden_at
   THEN RAISE EXCEPTION 'Privacy suppression is permanent until reviewed'; END IF;
   IF NEW.status <> OLD.status AND NOT (OLD.status='uploading' AND NEW.status='pending')
   THEN RAISE EXCEPTION 'Moderation is not enabled'; END IF;
   IF NEW.status=OLD.status THEN RETURN NEW; END IF;
 ELSE
   IF NEW.workflow_version IS DISTINCT FROM 1 OR NEW.status <> 'uploading' OR NEW.abandoned_at IS NOT NULL OR NEW.hidden_at IS NOT NULL OR NEW.image_deleted_at IS NOT NULL OR NEW.content_hash IS NOT NULL
   THEN RAISE EXCEPTION 'New submissions must begin uploading'; END IF;
 END IF;
 SELECT * INTO p FROM public.projects WHERE id=NEW.project_id FOR UPDATE;
 IF p.id IS NULL OR p.status <> 'published' OR p.owner_id=NEW.contributor_id OR p.published_version IS DISTINCT FROM NEW.criteria_version
 THEN RAISE EXCEPTION 'Collection cannot accept this submission'; END IF;
 IF NEW.upload_expires_at <= clock_timestamp() OR NEW.abandoned_at IS NOT NULL OR NEW.hidden_at IS NOT NULL
 THEN RAISE EXCEPTION 'Upload expired or suppressed'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.project_reservations WHERE project_id=p.id AND release_entry_id IS NULL)
 THEN RAISE EXCEPTION 'Collection funding unavailable'; END IF;
 SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=NEW.criteria_version;
 IF (body->>'closing_date')::date < (clock_timestamp() AT TIME ZONE 'UTC')::date
 THEN RAISE EXCEPTION 'Collection has closed'; END IF;
 IF NOT EXISTS(SELECT 1 FROM json_array_elements(body->'labels') AS label WHERE label->>'key'=NEW.label_key)
 THEN RAISE EXCEPTION 'Unknown label'; END IF;
 SELECT COUNT(*),COUNT(*) FILTER (WHERE contributor_id=NEW.contributor_id),
        COUNT(*) FILTER (WHERE contributor_id=NEW.contributor_id AND status='uploading')
 INTO used,own_used,slots FROM public.submissions
 WHERE project_id=p.id AND id<>NEW.id AND (status IN ('pending','approved') OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp()));
 IF used >= (body->>'image_count')::integer OR own_used>=20 OR (TG_OP='INSERT' AND slots>=5)
 THEN RAISE EXCEPTION 'Collection or contributor capacity reached'; END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION public.guard_collection_close_with_submissions() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.status='closed' AND OLD.status<>'closed' AND EXISTS(
   SELECT 1 FROM public.submissions WHERE project_id=NEW.id AND
   (status='pending' OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp())))
 THEN RAISE EXCEPTION 'Outstanding submissions retain collection funding'; END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION public.guard_notification_update() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF (to_jsonb(NEW)-ARRAY['sent_at','attempts','next_attempt_at']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['sent_at','attempts','next_attempt_at'])
    OR NEW.attempts<OLD.attempts OR (OLD.sent_at IS NOT NULL AND NEW IS DISTINCT FROM OLD)
 THEN RAISE EXCEPTION 'Notification history is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER notification_update_guard BEFORE UPDATE ON public.notification_outbox
FOR EACH ROW EXECUTE FUNCTION public.guard_notification_update();
CREATE TRIGGER notification_no_delete BEFORE DELETE ON public.notification_outbox
FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER notification_no_truncate BEFORE TRUNCATE ON public.notification_outbox
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();
