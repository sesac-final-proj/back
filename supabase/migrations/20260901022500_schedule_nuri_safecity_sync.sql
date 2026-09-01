create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

grant all on table public.nuri_crawled to service_role;
grant usage, select on sequence public.nuri_crawled_id_seq to service_role;

do $$
declare
  existing_job_id bigint;
begin
  select jobid into existing_job_id
  from cron.job
  where jobname = 'sync-nuri-safecity-every-10-minutes';

  if existing_job_id is not null then
    perform cron.unschedule(existing_job_id);
  end if;
end
$$;

select cron.schedule(
  'sync-nuri-safecity-every-10-minutes',
  '*/10 * * * *',
  $$
  select net.http_post(
    url := (
      select decrypted_secret
      from vault.decrypted_secrets
      where name = 'nuri_project_url'
    ) || '/functions/v1/sync-nuri-safecity',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'nuri_publishable_key'
      )
    ),
    body := jsonb_build_object('scheduled_at', now())
  ) as request_id;
  $$
);
