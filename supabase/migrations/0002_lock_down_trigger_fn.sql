-- handle_new_user() is only ever invoked by the on_auth_user_created trigger
-- (which runs as the table owner). Nothing should be able to call it over the
-- REST RPC surface, so drop EXECUTE for the API roles. Clears the
-- 0028 / 0029 "public can execute SECURITY DEFINER function" advisor lints.
revoke execute on function public.handle_new_user() from public, anon, authenticated;
