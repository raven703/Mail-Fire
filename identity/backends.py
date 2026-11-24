from django.contrib.auth.backends import ModelBackend


class RoleBackend(ModelBackend):
    """Roles remain authoritative; originals is never implied by admin status."""

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        permissions = set()
        if user_obj.role in {"admin", "analyst", "observer"}:
            permissions.add("identity.access_mice")
        if user_obj.role in {"admin", "analyst"}:
            permissions.add("identity.investigate")
        if user_obj.role == "admin":
            permissions.add("identity.administer")
        if user_obj.originals:
            permissions.add("identity.view_originals")
        # MICE's four capabilities are resolved from current fields, not cached
        # group grants that might outlive a role downgrade.
        return permissions | {
            permission
            for permission in super().get_all_permissions(user_obj, obj)
            if permission
            not in {
                "identity.access_mice",
                "identity.investigate",
                "identity.administer",
                "identity.view_originals",
            }
        }

    def has_perm(self, user_obj, perm, obj=None):
        return perm in self.get_all_permissions(user_obj, obj)
