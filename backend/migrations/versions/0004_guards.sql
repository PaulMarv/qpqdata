ALTER TABLE public.projects DROP CONSTRAINT projects_status_check;
ALTER TABLE public.projects ADD CONSTRAINT ck_project_status CHECK (status IN ('draft','published','paused','closed'));
ALTER TABLE public.credit_ledger_entries ADD CONSTRAINT ck_collection_ledger CHECK (
  (reason NOT IN ('collection_reservation','collection_release') AND project_id IS NULL) OR
  (reason = 'collection_reservation' AND project_id IS NOT NULL AND amount < 0
     AND reversal_of_id IS NULL AND idempotency_key = 'reservation:v1:' || project_id::text) OR
  (reason = 'collection_release' AND project_id IS NOT NULL AND amount > 0
     AND reversal_of_id IS NOT NULL AND idempotency_key = 'release:v1:' || project_id::text)
);

CREATE FUNCTION public.reject_project_history_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN RAISE EXCEPTION 'Project history is immutable'; END; $$;
CREATE TRIGGER project_versions_immutable BEFORE UPDATE OR DELETE ON public.project_versions
FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER project_versions_no_truncate BEFORE TRUNCATE ON public.project_versions
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER reservations_no_delete BEFORE DELETE ON public.project_reservations
FOR EACH ROW EXECUTE FUNCTION public.reject_project_history_mutation();
CREATE TRIGGER reservations_no_truncate BEFORE TRUNCATE ON public.project_reservations
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_project_history_mutation();

CREATE FUNCTION public.guard_reservation_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
 IF (to_jsonb(NEW) - 'release_entry_id') IS DISTINCT FROM (to_jsonb(OLD) - 'release_entry_id')
    OR (OLD.release_entry_id IS NOT NULL AND NEW.release_entry_id IS DISTINCT FROM OLD.release_entry_id)
 THEN RAISE EXCEPTION 'Reservation history is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER reservation_update_guard BEFORE UPDATE ON public.project_reservations
FOR EACH ROW EXECUTE FUNCTION public.guard_reservation_update();

CREATE FUNCTION public.guard_project_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
 IF NEW.id <> OLD.id OR NEW.owner_id <> OLD.owner_id OR NEW.created_at <> OLD.created_at
 THEN RAISE EXCEPTION 'Project identity is immutable'; END IF;
 IF OLD.status = 'closed' AND NEW IS DISTINCT FROM OLD
 THEN RAISE EXCEPTION 'Closed projects are terminal'; END IF;
 IF OLD.published_version IS NOT NULL AND
    (NEW.name,NEW.description,NEW.category,NEW.search_text,NEW.current_version,NEW.published_version)
    IS DISTINCT FROM
    (OLD.name,OLD.description,OLD.category,OLD.search_text,OLD.current_version,OLD.published_version)
 THEN RAISE EXCEPTION 'Published definition is frozen'; END IF;
 IF NEW.status <> OLD.status AND NOT (
    (OLD.status = 'draft' AND NEW.status IN ('published','closed')) OR
    (OLD.status = 'published' AND NEW.status IN ('paused','closed')) OR
    (OLD.status = 'paused' AND NEW.status IN ('published','closed')))
 THEN RAISE EXCEPTION 'Invalid lifecycle transition'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER project_update_guard BEFORE UPDATE ON public.projects
FOR EACH ROW EXECUTE FUNCTION public.guard_project_update();

CREATE FUNCTION public.lock_ledger_wallet() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
 PERFORM 1 FROM public.users WHERE id = NEW.user_id FOR UPDATE;
 RETURN NEW;
END; $$;
CREATE TRIGGER ledger_wallet_lock BEFORE INSERT ON public.credit_ledger_entries
FOR EACH ROW EXECUTE FUNCTION public.lock_ledger_wallet();
CREATE FUNCTION public.assert_nonnegative_wallet() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
 IF (SELECT COALESCE(SUM(amount),0) FROM public.credit_ledger_entries WHERE user_id = NEW.user_id) < 0
 THEN RAISE EXCEPTION 'Insufficient QC'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER ledger_nonnegative AFTER INSERT ON public.credit_ledger_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.assert_nonnegative_wallet();

CREATE FUNCTION public.assert_project_funding(target uuid) RETURNS void
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE p public.projects%ROWTYPE; r public.project_reservations%ROWTYPE;
 d public.credit_ledger_entries%ROWTYPE; c public.credit_ledger_entries%ROWTYPE;
 body json; budget bigint; events integer;
BEGIN
 SELECT * INTO p FROM public.projects WHERE id = target;
 IF NOT FOUND THEN RETURN; END IF;
 IF p.current_version > 0 THEN
   SELECT definition INTO body FROM public.project_versions WHERE project_id=p.id AND version=p.current_version;
   IF NOT FOUND OR body->>'name' IS DISTINCT FROM p.name
      OR body->>'description' IS DISTINCT FROM p.description OR body->>'category' IS DISTINCT FROM p.category
   THEN RAISE EXCEPTION 'Project snapshot mismatch'; END IF;
 END IF;
 IF p.status IN ('published','paused') AND
    (p.published_version IS NULL OR p.published_version <> p.current_version OR p.current_version < 1)
 THEN RAISE EXCEPTION 'Published snapshot required'; END IF;
 SELECT * INTO r FROM public.project_reservations WHERE project_id=p.id;
 SELECT COUNT(*) INTO events FROM public.credit_ledger_entries WHERE project_id=p.id;
 IF r.id IS NULL THEN
   IF p.status IN ('published','paused') OR p.published_version IS NOT NULL OR events <> 0
   THEN RAISE EXCEPTION 'Funded reservation required'; END IF;
   RETURN;
 END IF;
 IF p.published_version IS NULL OR p.published_version <> p.current_version OR p.status='draft'
 THEN RAISE EXCEPTION 'Reservation requires published snapshot'; END IF;
 budget := (body->>'image_count')::bigint * (body->>'reward_per_image')::bigint;
 IF budget IS NULL OR budget <= 0 OR r.amount <> budget
 THEN RAISE EXCEPTION 'Reservation budget mismatch'; END IF;
 SELECT * INTO d FROM public.credit_ledger_entries WHERE id=r.debit_entry_id;
 IF d.id IS NULL OR d.user_id <> p.owner_id OR d.project_id IS DISTINCT FROM p.id
    OR d.amount <> -r.amount OR d.reason <> 'collection_reservation'
 THEN RAISE EXCEPTION 'Reservation debit mismatch'; END IF;
 IF r.release_entry_id IS NULL THEN
   IF p.status NOT IN ('published','paused') OR events <> 1
   THEN RAISE EXCEPTION 'Held funding mismatch'; END IF;
 ELSE
   SELECT * INTO c FROM public.credit_ledger_entries WHERE id=r.release_entry_id;
   IF p.status <> 'closed' OR c.id IS NULL OR c.user_id <> p.owner_id OR c.project_id IS DISTINCT FROM p.id
      OR c.amount <> r.amount OR c.reason <> 'collection_release' OR c.reversal_of_id IS DISTINCT FROM d.id
      OR events <> 2
   THEN RAISE EXCEPTION 'Reservation release mismatch'; END IF;
 END IF;
END; $$;

CREATE FUNCTION public.check_project_funding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
 IF TG_TABLE_NAME = 'projects' THEN PERFORM public.assert_project_funding(NEW.id);
 ELSIF NEW.project_id IS NOT NULL THEN PERFORM public.assert_project_funding(NEW.project_id); END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER project_funding_complete AFTER INSERT OR UPDATE ON public.projects
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_project_funding();
CREATE CONSTRAINT TRIGGER reservation_funding_complete AFTER INSERT OR UPDATE ON public.project_reservations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_project_funding();
CREATE CONSTRAINT TRIGGER ledger_funding_complete AFTER INSERT ON public.credit_ledger_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_project_funding();
