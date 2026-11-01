-- All previous SQL resources remain frozen. Community ledger guards are retained.
ALTER FUNCTION public.assert_project_funding(uuid) RENAME TO assert_crowdsourced_funding;
CREATE FUNCTION public.assert_project_funding(target uuid) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; body json; used bigint;
BEGIN
 SELECT * INTO p FROM public.projects WHERE id=target;
 IF NOT FOUND THEN RETURN; END IF;
 SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=p.current_version;
 IF p.current_version>0 AND (body IS NULL OR coalesce(body->>'mode','crowdsourced')<>p.mode)
 THEN RAISE EXCEPTION 'Collection mode mismatch'; END IF;
 IF p.mode='personal' THEN
   IF EXISTS(SELECT 1 FROM public.project_reservations WHERE project_id=p.id) OR
      EXISTS(SELECT 1 FROM public.credit_ledger_entries WHERE project_id=p.id) OR
      EXISTS(SELECT 1 FROM public.submissions WHERE project_id=p.id AND (workflow_version IS DISTINCT FROM 2 OR contributor_id<>p.owner_id))
   THEN RAISE EXCEPTION 'Personal images must never use credits or community submissions'; END IF;
   IF p.current_version<1 OR p.published_version IS DISTINCT FROM p.current_version OR
      body->>'name' IS DISTINCT FROM p.name OR body->>'description' IS DISTINCT FROM p.description OR body->>'category' IS DISTINCT FROM p.category
   THEN RAISE EXCEPTION 'Frozen personal definition required'; END IF;
 ELSE
   PERFORM public.assert_crowdsourced_funding(target);
 END IF;
 SELECT COUNT(*) INTO used FROM public.submissions WHERE project_id=p.id AND
   (workflow_version IS DISTINCT FROM 2 OR hidden_at IS NULL) AND
   (status IN ('pending','approved') OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp()));
 IF EXISTS(SELECT 1 FROM public.submissions WHERE project_id=p.id AND workflow_version=2) AND used>(body->>'image_count')::bigint
 THEN RAISE EXCEPTION 'Owner images cannot displace committed community capacity'; END IF;
END; $$;
CREATE FUNCTION public.guard_project_mode() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.mode<>OLD.mode THEN RAISE EXCEPTION 'Collection mode is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER project_mode_immutable BEFORE UPDATE ON public.projects FOR EACH ROW EXECUTE FUNCTION public.guard_project_mode();
DROP TRIGGER submission_guard ON public.submissions;
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
 WHERE project_id=p.id AND id<>NEW.id AND (workflow_version IS DISTINCT FROM 2 OR hidden_at IS NULL) AND (status IN ('pending','approved') OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp()));
 IF used >= (body->>'image_count')::integer OR own_used>=20 OR (TG_OP='INSERT' AND slots>=5)
 THEN RAISE EXCEPTION 'Collection or contributor capacity reached'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER submission_guard BEFORE INSERT OR UPDATE ON public.submissions
FOR EACH ROW WHEN (NEW.workflow_version IS DISTINCT FROM 2) EXECUTE FUNCTION public.guard_submission();

CREATE FUNCTION public.guard_owner_image() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; body json; used bigint;
BEGIN
 -- Use the same project lock as community slot allocation, approval and closure.
 SELECT * INTO p FROM public.projects WHERE id=NEW.project_id FOR UPDATE;
 IF p.owner_id IS DISTINCT FROM NEW.contributor_id THEN RAISE EXCEPTION 'Only owners supply owner images'; END IF;
 SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=NEW.criteria_version;
 IF NEW.criteria_version IS DISTINCT FROM p.published_version OR body IS NULL THEN RAISE EXCEPTION 'Frozen criteria required'; END IF;
 IF TG_OP='INSERT' THEN
   IF NEW.status<>'uploading' OR NEW.hidden_at IS NOT NULL OR NEW.image_deleted_at IS NOT NULL OR NEW.abandoned_at IS NOT NULL OR NEW.content_hash IS NOT NULL OR NEW.annotation_version<>0
   THEN RAISE EXCEPTION 'Owner images begin uploading'; END IF;
 ELSE
   IF OLD.workflow_version IS DISTINCT FROM 2 OR
     (to_jsonb(NEW)-ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at','image_deleted_at','metadata_values','label_key','annotation_version']) IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at','image_deleted_at','metadata_values','label_key','annotation_version'])
   THEN RAISE EXCEPTION 'Owner image provenance immutable'; END IF;
   IF OLD.hidden_at IS NOT NULL AND NEW.hidden_at IS DISTINCT FROM OLD.hidden_at THEN RAISE EXCEPTION 'Suppression is permanent'; END IF;
   IF NEW.image_deleted_at IS DISTINCT FROM OLD.image_deleted_at AND (OLD.image_deleted_at IS NOT NULL OR NEW.image_deleted_at IS NULL OR OLD.hidden_at IS NULL)
   THEN RAISE EXCEPTION 'Only suppressed owner images may be purged'; END IF;
   IF OLD.status<>'uploading' OR OLD.abandoned_at IS NOT NULL THEN
     IF (to_jsonb(NEW)-ARRAY['hidden_at','image_deleted_at','metadata_values','label_key','annotation_version']) IS DISTINCT FROM
        (to_jsonb(OLD)-ARRAY['hidden_at','image_deleted_at','metadata_values','label_key','annotation_version'])
     THEN RAISE EXCEPTION 'Owner image pixels and status immutable'; END IF;
   ELSIF NEW.status<>OLD.status AND NEW.status<>'approved' THEN RAISE EXCEPTION 'Owner images cannot enter community review'; END IF;
   IF (NEW.label_key,NEW.metadata_values::jsonb,NEW.annotation_version) IS DISTINCT FROM (OLD.label_key,OLD.metadata_values::jsonb,OLD.annotation_version) THEN
     IF EXISTS(SELECT 1 FROM public.dataset_consents WHERE submission_id=OLD.id AND authorised_at IS NOT NULL AND withdrawn_at IS NULL) OR p.mode<>'personal' OR OLD.status<>'approved' OR OLD.hidden_at IS NOT NULL OR NEW.annotation_version<>OLD.annotation_version+1 OR NOT EXISTS(
       SELECT 1 FROM public.image_annotations a WHERE a.submission_id=OLD.id AND a.actor_id=p.owner_id AND a.version=NEW.annotation_version
       AND a.previous::jsonb=jsonb_build_object('label',OLD.label_key,'answers',OLD.metadata_values::jsonb)
       AND a.replacement::jsonb=jsonb_build_object('label',NEW.label_key,'answers',NEW.metadata_values::jsonb))
     THEN RAISE EXCEPTION 'Personal label edit requires immutable audit revision'; END IF;
   END IF;
   IF OLD.status<>'uploading' OR NEW.abandoned_at IS NOT NULL OR NEW.status=OLD.status THEN RETURN NEW; END IF;
 END IF;
 IF p.status NOT IN ('published','paused') OR NEW.upload_expires_at<=clock_timestamp() OR NEW.hidden_at IS NOT NULL OR NEW.abandoned_at IS NOT NULL
 THEN RAISE EXCEPTION 'Collection cannot accept owner images'; END IF;
 IF p.mode='crowdsourced' AND NOT EXISTS(SELECT 1 FROM public.project_reservations WHERE project_id=p.id AND release_entry_id IS NULL)
 THEN RAISE EXCEPTION 'Collection funding unavailable'; END IF;
 IF (body->>'closing_date')::date < (clock_timestamp() AT TIME ZONE 'UTC')::date THEN RAISE EXCEPTION 'Closing date passed'; END IF;
 IF NOT EXISTS(SELECT 1 FROM json_array_elements(body->'labels') l WHERE l->>'key'=NEW.label_key)
 THEN RAISE EXCEPTION 'Unknown label'; END IF;
 SELECT COUNT(*) INTO used FROM public.submissions WHERE project_id=p.id AND id<>NEW.id AND
  (workflow_version IS DISTINCT FROM 2 OR hidden_at IS NULL) AND
  (status IN ('pending','approved') OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp()));
 IF used >= (body->>'image_count')::bigint THEN RAISE EXCEPTION 'Collection capacity reached'; END IF;
 IF TG_OP='INSERT' AND (SELECT COUNT(*) FROM public.submissions WHERE project_id=p.id AND contributor_id=NEW.contributor_id AND status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp())>=5
 THEN RAISE EXCEPTION 'Finish active owner uploads first'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER owner_image_guard BEFORE INSERT OR UPDATE ON public.submissions
FOR EACH ROW WHEN (NEW.workflow_version=2) EXECUTE FUNCTION public.guard_owner_image();
CREATE TRIGGER annotations_immutable BEFORE UPDATE OR DELETE ON public.image_annotations FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER annotations_no_truncate BEFORE TRUNCATE ON public.image_annotations FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE OR REPLACE FUNCTION public.guard_moderation_decision() RETURNS trigger
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
       OR paid+NEW.reward>r.amount OR (SELECT COUNT(*) FROM public.submissions WHERE project_id=p.id AND status='approved' AND (workflow_version IS DISTINCT FROM 2 OR hidden_at IS NULL)) >= (body->>'image_count')::integer
   THEN RAISE EXCEPTION 'Insufficient reserved approval capacity'; END IF;
   SELECT * INTO entry FROM public.credit_ledger_entries WHERE id=NEW.reward_entry_id;
   IF entry.id IS NULL OR entry.reason<>'collection_reward' OR entry.amount<>NEW.reward
       OR entry.user_id<>s.contributor_id OR entry.project_id IS DISTINCT FROM p.id
       OR entry.idempotency_key<>'reward:v1:'||s.id::text
   THEN RAISE EXCEPTION 'Reward ledger mismatch'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION public.guard_dataset_consent() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.dataset_publications%ROWTYPE; s public.submissions%ROWTYPE; owner uuid; body json;
BEGIN
 IF TG_OP='UPDATE' THEN
   IF (to_jsonb(NEW)-ARRAY['authorised_by','authorised_at','withdrawn_at']) IS DISTINCT FROM
      (to_jsonb(OLD)-ARRAY['authorised_by','authorised_at','withdrawn_at'])
      OR (OLD.authorised_at IS NOT NULL AND (NEW.authorised_by,NEW.authorised_at) IS DISTINCT FROM (OLD.authorised_by,OLD.authorised_at))
      OR (OLD.withdrawn_at IS NOT NULL AND NEW IS DISTINCT FROM OLD)
   THEN RAISE EXCEPTION 'Consent history is immutable'; END IF;
 END IF;
 SELECT * INTO s FROM public.submissions WHERE id=NEW.submission_id;
 SELECT * INTO p FROM public.dataset_publications WHERE id=NEW.publication_id;
 SELECT owner_id INTO owner FROM public.projects WHERE id=p.project_id;
 IF TG_OP='INSERT' OR (TG_OP='UPDATE' AND NEW.authorised_at IS DISTINCT FROM OLD.authorised_at) THEN
   SELECT definition INTO body FROM public.project_versions WHERE project_id=p.project_id AND version=p.criteria_version;
   IF s.project_id IS DISTINCT FROM p.project_id OR s.criteria_version IS DISTINCT FROM p.criteria_version
      OR s.contributor_id<>NEW.contributor_id OR s.workflow_version IS NULL OR s.workflow_version NOT IN (1,2)
      OR s.status NOT IN ('pending','approved') OR s.hidden_at IS NOT NULL OR s.image_deleted_at IS NOT NULL
      OR p.withdrawn_at IS NOT NULL OR NEW.policy_digest<>p.policy_digest
      OR s.consent_record->>'ownership_or_permission' IS DISTINCT FROM 'true'
      OR s.consent_record->>'licence' IS DISTINCT FROM body->>'licence'
      OR s.consent_record->>'reuse_terms' IS DISTINCT FROM body->>'reuse_terms'
      OR EXISTS(SELECT 1 FROM public.removal_requests WHERE submission_id=s.id)
   THEN RAISE EXCEPTION 'Recorded export consent required'; END IF;
   IF TG_OP='INSERT' AND (NEW.authorised_at IS NOT NULL OR NEW.withdrawn_at IS NOT NULL)
   THEN RAISE EXCEPTION 'Contributor opt-in must precede owner authorisation'; END IF;
   IF NEW.authorised_at IS NOT NULL AND (NEW.authorised_by IS DISTINCT FROM owner OR s.status<>'approved')
   THEN RAISE EXCEPTION 'Owner must authorise an approved image'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE FUNCTION public.check_image_annotation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE s public.submissions%ROWTYPE; p public.projects%ROWTYPE;
BEGIN
 SELECT * INTO s FROM public.submissions WHERE id=NEW.submission_id;
 SELECT * INTO p FROM public.projects WHERE id=s.project_id;
 IF p.mode<>'personal' OR p.owner_id IS DISTINCT FROM NEW.actor_id OR s.workflow_version IS DISTINCT FROM 2 OR s.status<>'approved'
    OR s.annotation_version<>NEW.version OR NEW.replacement::jsonb IS DISTINCT FROM jsonb_build_object('label',s.label_key,'answers',s.metadata_values::jsonb)
 THEN RAISE EXCEPTION 'Annotation audit must match its personal image update'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER annotation_complete AFTER INSERT ON public.image_annotations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_image_annotation();
