CREATE FUNCTION public.guard_dataset_publication() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; body json;
BEGIN
 IF TG_OP='UPDATE' THEN
   IF (to_jsonb(NEW)-'withdrawn_at') IS DISTINCT FROM (to_jsonb(OLD)-'withdrawn_at')
      OR (OLD.withdrawn_at IS NOT NULL AND NEW.withdrawn_at IS DISTINCT FROM OLD.withdrawn_at)
   THEN RAISE EXCEPTION 'Publication policy is immutable'; END IF;
 ELSE
   SELECT * INTO p FROM public.projects WHERE id=NEW.project_id FOR UPDATE;
   SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=NEW.criteria_version;
   IF p.id IS NULL OR p.owner_id<>NEW.authorised_by OR p.published_version IS DISTINCT FROM NEW.criteria_version
      OR p.status NOT IN ('published','paused','closed') OR NEW.withdrawn_at IS NOT NULL
      OR body->>'licence' NOT IN ('CC0-1.0','CC-BY-4.0','CC-BY-SA-4.0')
      OR json_typeof(NEW.public_fields) IS DISTINCT FROM 'array'
   THEN RAISE EXCEPTION 'Explicit licensed owner publication required'; END IF;
   IF EXISTS(SELECT 1 FROM json_array_elements_text(NEW.public_fields) f WHERE NOT EXISTS(
     SELECT 1 FROM json_array_elements(body->'criteria'->'questions') q
     WHERE q->>'key'=f AND q->>'type'<>'short_text'))
   THEN RAISE EXCEPTION 'Only declared structured fields may be public'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER dataset_publication_guard BEFORE INSERT OR UPDATE ON public.dataset_publications
FOR EACH ROW EXECUTE FUNCTION public.guard_dataset_publication();

CREATE FUNCTION public.guard_dataset_consent() RETURNS trigger
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
      OR s.contributor_id<>NEW.contributor_id OR s.workflow_version IS DISTINCT FROM 1
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
CREATE TRIGGER dataset_consent_guard BEFORE INSERT OR UPDATE ON public.dataset_consents
FOR EACH ROW EXECUTE FUNCTION public.guard_dataset_consent();

CREATE FUNCTION public.guard_dataset_version() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' THEN
   PERFORM 1 FROM public.dataset_publications WHERE id=NEW.publication_id AND withdrawn_at IS NULL FOR UPDATE;
   IF NOT FOUND OR NEW.manifest IS NOT NULL OR NEW.archive_sha256 IS NOT NULL OR NEW.revoked_at IS NOT NULL THEN RAISE EXCEPTION 'Active publication required'; END IF;
 ELSE
   IF (to_jsonb(NEW)-ARRAY['manifest','revoked_at','archive_sha256']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['manifest','revoked_at','archive_sha256'])
     OR (OLD.manifest IS NOT NULL AND NEW.manifest::jsonb IS DISTINCT FROM OLD.manifest::jsonb)
     OR (OLD.archive_sha256 IS NOT NULL AND NEW.archive_sha256 IS DISTINCT FROM OLD.archive_sha256)
     OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
   THEN RAISE EXCEPTION 'Dataset snapshot is immutable'; END IF;
   IF OLD.manifest IS NULL AND NEW.manifest IS NOT NULL AND
      (NEW.revoked_at IS NOT NULL OR (SELECT COUNT(*) FROM public.dataset_members WHERE version_id=NEW.id)=0)
   THEN RAISE EXCEPTION 'A live nonempty snapshot is required'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER dataset_version_guard BEFORE INSERT OR UPDATE ON public.dataset_versions
FOR EACH ROW EXECUTE FUNCTION public.guard_dataset_version();

CREATE FUNCTION public.guard_dataset_member() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE v public.dataset_versions%ROWTYPE; c public.dataset_consents%ROWTYPE; s public.submissions%ROWTYPE;
BEGIN
 SELECT * INTO v FROM public.dataset_versions WHERE id=NEW.version_id FOR UPDATE;
 SELECT * INTO c FROM public.dataset_consents WHERE id=NEW.consent_id;
 SELECT * INTO s FROM public.submissions WHERE id=NEW.submission_id;
 IF v.id IS NULL OR v.manifest IS NOT NULL OR v.revoked_at IS NOT NULL
    OR EXISTS(SELECT 1 FROM public.dataset_builds WHERE version_id=v.id)
    OR c.submission_id IS DISTINCT FROM s.id OR c.publication_id IS DISTINCT FROM v.publication_id
    OR c.authorised_at IS NULL OR c.withdrawn_at IS NOT NULL OR s.status<>'approved'
    OR s.hidden_at IS NOT NULL OR s.image_deleted_at IS NOT NULL
    OR EXISTS(SELECT 1 FROM public.removal_requests WHERE submission_id=s.id)
 THEN RAISE EXCEPTION 'Only approved explicitly authorised images belong in snapshots'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER dataset_member_guard BEFORE INSERT ON public.dataset_members
FOR EACH ROW EXECUTE FUNCTION public.guard_dataset_member();

CREATE FUNCTION public.revoke_dataset_exports() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_TABLE_NAME='submissions' THEN
   IF NEW.hidden_at IS NOT NULL OR NEW.image_deleted_at IS NOT NULL THEN
     UPDATE public.dataset_versions SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL AND id IN
       (SELECT version_id FROM public.dataset_members WHERE submission_id=NEW.id);
   END IF;
 ELSIF TG_TABLE_NAME='removal_requests' THEN
   UPDATE public.dataset_versions SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL AND id IN
     (SELECT version_id FROM public.dataset_members WHERE submission_id=NEW.submission_id);
 ELSIF TG_TABLE_NAME='dataset_consents' AND NEW.withdrawn_at IS NOT NULL THEN
   UPDATE public.dataset_versions SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL AND id IN
     (SELECT version_id FROM public.dataset_members WHERE consent_id=NEW.id);
 ELSIF TG_TABLE_NAME='dataset_publications' AND NEW.withdrawn_at IS NOT NULL THEN
   UPDATE public.dataset_versions SET revoked_at=clock_timestamp() WHERE publication_id=NEW.id AND revoked_at IS NULL;
 END IF;
 RETURN NULL;
END; $$;
CREATE TRIGGER submission_export_revoke AFTER UPDATE OF hidden_at,image_deleted_at ON public.submissions
FOR EACH ROW EXECUTE FUNCTION public.revoke_dataset_exports();
CREATE TRIGGER removal_export_revoke AFTER INSERT ON public.removal_requests
FOR EACH ROW EXECUTE FUNCTION public.revoke_dataset_exports();
CREATE TRIGGER consent_export_revoke AFTER UPDATE ON public.dataset_consents
FOR EACH ROW EXECUTE FUNCTION public.revoke_dataset_exports();
CREATE TRIGGER publication_export_revoke AFTER UPDATE ON public.dataset_publications
FOR EACH ROW EXECUTE FUNCTION public.revoke_dataset_exports();

CREATE TRIGGER dataset_publications_no_delete BEFORE DELETE ON public.dataset_publications FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_publications_no_truncate BEFORE TRUNCATE ON public.dataset_publications FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_consents_no_delete BEFORE DELETE ON public.dataset_consents FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_consents_no_truncate BEFORE TRUNCATE ON public.dataset_consents FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_versions_no_delete BEFORE DELETE ON public.dataset_versions FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_versions_no_truncate BEFORE TRUNCATE ON public.dataset_versions FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_members_no_delete BEFORE DELETE ON public.dataset_members FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_members_no_truncate BEFORE TRUNCATE ON public.dataset_members FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_builds_no_delete BEFORE DELETE ON public.dataset_builds FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_builds_no_truncate BEFORE TRUNCATE ON public.dataset_builds FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_members_no_update BEFORE UPDATE ON public.dataset_members FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE TRIGGER dataset_reports_immutable BEFORE UPDATE OR DELETE ON public.dataset_reports FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER dataset_reports_no_truncate BEFORE TRUNCATE ON public.dataset_reports FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();
