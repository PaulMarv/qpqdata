CREATE OR REPLACE FUNCTION public.lock_ledger_wallet() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.reason='collection_reward' THEN
   PERFORM 1 FROM public.projects WHERE id=NEW.project_id FOR UPDATE;
 ELSE
   -- Wallet writers still exclude one another. KEY SHARE foreign-key checks
   -- may proceed because wallet operations never change a user's primary key.
   PERFORM 1 FROM public.users WHERE id=NEW.user_id FOR NO KEY UPDATE;
 END IF;
 RETURN NEW;
END; $$;
