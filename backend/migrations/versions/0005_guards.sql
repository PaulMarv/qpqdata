ALTER TABLE public.submissions DROP CONSTRAINT submissions_status_check;
ALTER TABLE public.submissions ADD CONSTRAINT ck_submission_status CHECK (status IN ('uploading','pending','approved','rejected'));
ALTER TABLE public.submissions ADD CONSTRAINT ck_submission_provenance CHECK (workflow_version IS NULL OR (workflow_version=1 AND criteria_version IS NOT NULL AND label_key IS NOT NULL AND request_key IS NOT NULL AND request_hash IS NOT NULL AND consent_record IS NOT NULL AND upload_expires_at IS NOT NULL));
ALTER TABLE public.submissions ADD CONSTRAINT ck_submission_image CHECK (workflow_version IS NULL OR status='uploading' OR (content_hash IS NOT NULL AND image_format IN ('JPEG','PNG','WEBP') AND width>0 AND height>0 AND byte_size>0 AND submitted_at IS NOT NULL));

CREATE FUNCTION public.guard_submission() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; body json; used integer; own_used integer; slots integer;
BEGIN
 IF TG_OP='UPDATE' THEN
   IF OLD.workflow_version IS NULL THEN RAISE EXCEPTION 'Legacy submissions require separate review'; END IF;
   IF (to_jsonb(NEW) - ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at']) IS DISTINCT FROM
      (to_jsonb(OLD) - ARRAY['status','object_key','content_hash','image_format','width','height','byte_size','submitted_at','abandoned_at','hidden_at'])
   THEN RAISE EXCEPTION 'Submission provenance is immutable'; END IF;
   IF OLD.status <> 'uploading' OR OLD.abandoned_at IS NOT NULL THEN
     IF (to_jsonb(NEW) - 'hidden_at') IS DISTINCT FROM (to_jsonb(OLD) - 'hidden_at')
     THEN RAISE EXCEPTION 'Completed/expired submission is immutable'; END IF;
   END IF;
   IF OLD.hidden_at IS NOT NULL AND NEW.hidden_at IS DISTINCT FROM OLD.hidden_at
   THEN RAISE EXCEPTION 'Privacy suppression is permanent until reviewed'; END IF;
   IF NEW.status <> OLD.status AND NOT (OLD.status='uploading' AND NEW.status='pending')
   THEN RAISE EXCEPTION 'Moderation is not enabled'; END IF;
   IF NEW.status=OLD.status THEN RETURN NEW; END IF;
 ELSE
   IF NEW.workflow_version IS DISTINCT FROM 1 OR NEW.status <> 'uploading' OR NEW.abandoned_at IS NOT NULL OR NEW.hidden_at IS NOT NULL OR NEW.content_hash IS NOT NULL
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
CREATE TRIGGER submission_guard BEFORE INSERT OR UPDATE ON public.submissions FOR EACH ROW EXECUTE FUNCTION public.guard_submission();
CREATE TRIGGER submission_no_delete BEFORE DELETE ON public.submissions FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER submission_no_truncate BEFORE TRUNCATE ON public.submissions FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER removal_immutable BEFORE UPDATE OR DELETE ON public.removal_requests FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER removal_no_truncate BEFORE TRUNCATE ON public.removal_requests FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE FUNCTION public.guard_collection_close_with_submissions() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.status='closed' AND OLD.status<>'closed' AND EXISTS(
   SELECT 1 FROM public.submissions WHERE project_id=NEW.id AND
     (status IN ('pending','approved') OR (status='uploading' AND abandoned_at IS NULL AND upload_expires_at>clock_timestamp())))
 THEN RAISE EXCEPTION 'Outstanding submissions retain collection funding'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER collection_submission_close_guard BEFORE UPDATE ON public.projects
FOR EACH ROW EXECUTE FUNCTION public.guard_collection_close_with_submissions();
