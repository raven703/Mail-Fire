# Authentication and future Active Directory integration

## Current state

Mail-Fire already has local Argon2 password authentication, session cookies,
CSRF checking, audit events, administrative account creation/editing and role
checks. The Users page exposes that existing functionality. Removing an account
is a **revocation**: it disables login and invalidates sessions while preserving
foreign-key relationships and investigation/audit history. The last active
administrator and the current administrator cannot be revoked.

Existing roles (admin, analyst, observer) and the separate `originals` permission
are intentionally maintained for backwards compatibility. New users default to
analyst with content access in the UI; administrators can change these values.

## AD / LDAP plan (not enabled in this PR)

Keep external identity verification separate from authorization:

1. Add an `auth_source` field to `accounts` (`local` / `ad`) and a stable external
   issuer+object ID mapping with a unique database constraint. Never rely on
   a mutable display name or UPN alone.
2. Define an identity-provider interface returning a validated subject and
   directory groups. Continue to use the existing local verifier for local
   accounts. The AD adapter should use LDAPS/StartTLS with validated certificates,
   or preferably OIDC through a supported identity provider. Never log or
   persist AD passwords, and never use insecure LDAP binds.
3. Map approved directory groups to the internal authorization policy in one
   administrator-controlled configuration; default deny, no automatic admin
   grants. Do not let clients choose roles or `originals` access.
4. Keep authentication and authorization separate: all API dependencies
   (`user`, `analyst`, `admin`) must enforce server-side permissions on
   every request. MFA and account lockouts should be provided by the identity
   provider where available.
5. Decide explicitly on account provisioning, group-sync cadence, offline
   login policy, deprovisioning, session invalidation, certificate rotation and
   audit semantics. Removing directory membership must revoke sessions.
6. Migrate existing local accounts with an explicit linking flow. Never
   silently join an AD subject to a local account by matching username.
7. Include integration tests with a fake directory provider before enabling
   the new provider in deployment.

The current application does **not** connect to AD; no untested authentication
bypass, network credentials, or new authentication surface is introduced here.
