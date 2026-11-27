from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import Permission, Role, RolePermission
from app.permissions.catalog import ALL_PERMISSIONS, ROLES


async def sync_rbac(db: AsyncSession) -> None:
    """Idempotently mirror the code catalog into the roles/permissions tables. A transaction
    advisory lock makes several app instances starting at once take turns, instead of racing
    to insert the same rows."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('scoutsphere.sync_rbac'))"))
    existing_perms = {p.key: p for p in (await db.scalars(select(Permission))).all()}
    for key in ALL_PERMISSIONS:
        if key not in existing_perms:
            p = Permission(key=key)
            db.add(p)
            existing_perms[key] = p

    existing_roles = {r.key: r for r in (await db.scalars(select(Role))).all()}
    for key, (name, scope, _) in ROLES.items():
        role = existing_roles.get(key)
        if role is None:
            role = Role(key=key, name=name, scope=scope)
            db.add(role)
            existing_roles[key] = role
        else:
            role.name, role.scope = name, scope
    await db.flush()

    current = {
        (rp.role_id, rp.permission_id): rp
        for rp in (await db.scalars(select(RolePermission))).all()
    }
    wanted: set = set()
    for key, (_, _, perms) in ROLES.items():
        for perm in perms:
            wanted.add((existing_roles[key].id, existing_perms[perm].id))
    for pair in wanted - current.keys():
        db.add(RolePermission(role_id=pair[0], permission_id=pair[1]))
    for pair in current.keys() - wanted:
        await db.delete(current[pair])
    await db.commit()
