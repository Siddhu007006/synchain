"""
E8 Organization management tests.

Covers:
  - Create organization
  - List user's organizations
  - Get org details
  - Update org
  - Add/invite member
  - Update member role
  - Remove member
  - Role enforcement (owner protection, admin-only actions)
"""

from tests.conftest import _auth_headers, _register_user


class TestOrgCRUD:
    def test_create_org(self, client):
        reg = _register_user(client, email="orgcreate@synchain.io")
        headers = _auth_headers(reg["access_token"])
        resp = client.post("/api/v1/orgs/", json={"name": "New Corp"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Corp"
        assert data["slug"] == "new-corp"
        assert data["member_count"] == 1

    def test_create_duplicate_org_name(self, client):
        reg = _register_user(client, email="orgdup@synchain.io")
        headers = _auth_headers(reg["access_token"])
        client.post("/api/v1/orgs/", json={"name": "Unique Corp"}, headers=headers)
        resp = client.post(
            "/api/v1/orgs/", json={"name": "Unique Corp"}, headers=headers
        )
        assert resp.status_code == 409

    def test_list_orgs(self, client):
        reg = _register_user(client, email="orglist@synchain.io", org_name="Primary")
        headers = _auth_headers(reg["access_token"])
        client.post("/api/v1/orgs/", json={"name": "Secondary"}, headers=headers)
        resp = client.get("/api/v1/orgs/", headers=headers)
        assert resp.status_code == 200
        orgs = resp.json()
        assert len(orgs) == 2
        names = {o["name"] for o in orgs}
        assert "Primary" in names
        assert "Secondary" in names

    def test_get_org(self, client):
        reg = _register_user(client, email="orgget@synchain.io", org_name="Get Org")
        headers = _auth_headers(reg["access_token"])
        resp = client.get(f"/api/v1/orgs/{reg['org_slug']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Org"

    def test_update_org_name(self, client):
        reg = _register_user(client, email="orgupd@synchain.io", org_name="Old Name")
        headers = _auth_headers(reg["access_token"])
        resp = client.patch(
            f"/api/v1/orgs/{reg['org_slug']}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"


class TestMembership:
    def _setup_two_users(self, client):
        """Register two users. Returns (admin_headers, user2_data, org_slug)."""
        admin = _register_user(client, email="admin@synchain.io", org_name="Team Org")
        user2 = _register_user(client, email="member@synchain.io", org_name="User2 Org")
        return _auth_headers(admin["access_token"]), user2, admin["org_slug"]

    def test_invite_member(self, client):
        admin_h, user2, slug = self._setup_two_users(client)
        resp = client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "member"},
            headers=admin_h,
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "member"

    def test_list_members(self, client):
        admin_h, user2, slug = self._setup_two_users(client)
        client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "viewer"},
            headers=admin_h,
        )
        resp = client.get(f"/api/v1/orgs/{slug}/members", headers=admin_h)
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 2  # owner + invited

    def test_update_member_role(self, client):
        admin_h, user2, slug = self._setup_two_users(client)
        client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "member"},
            headers=admin_h,
        )
        resp = client.patch(
            f"/api/v1/orgs/{slug}/members/{user2['user_id']}",
            json={"role": "admin"},
            headers=admin_h,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_remove_member(self, client):
        admin_h, user2, slug = self._setup_two_users(client)
        client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "member"},
            headers=admin_h,
        )
        resp = client.delete(
            f"/api/v1/orgs/{slug}/members/{user2['user_id']}",
            headers=admin_h,
        )
        assert resp.status_code == 204

    def test_cannot_remove_owner(self, client):
        reg = _register_user(client, email="owner@synchain.io", org_name="Owner Org")
        headers = _auth_headers(reg["access_token"])
        resp = client.delete(
            f"/api/v1/orgs/{reg['org_slug']}/members/{reg['user_id']}",
            headers=headers,
        )
        assert resp.status_code == 403
        assert "owner" in resp.json()["detail"].lower()

    def test_cannot_change_owner_role(self, client):
        reg = _register_user(client, email="ownerrole@synchain.io")
        headers = _auth_headers(reg["access_token"])
        resp = client.patch(
            f"/api/v1/orgs/{reg['org_slug']}/members/{reg['user_id']}",
            json={"role": "member"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_invite_duplicate_member(self, client):
        admin_h, user2, slug = self._setup_two_users(client)
        client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "member"},
            headers=admin_h,
        )
        resp = client.post(
            f"/api/v1/orgs/{slug}/members",
            json={"email": "member@synchain.io", "role": "admin"},
            headers=admin_h,
        )
        assert resp.status_code == 409


class TestOrgPermissions:
    def test_viewer_cannot_invite(self, client):
        admin = _register_user(
            client, email="orgadmin@synchain.io", org_name="Perm Org"
        )
        _register_user(client, email="orgviewer@synchain.io", org_name="Viewer Org")
        admin_h = _auth_headers(admin["access_token"])

        # Invite viewer
        client.post(
            f"/api/v1/orgs/{admin['org_slug']}/members",
            json={"email": "orgviewer@synchain.io", "role": "viewer"},
            headers=admin_h,
        )

        # Login viewer into admin's org
        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "orgviewer@synchain.io",
                "password": "testpass123",
                "org_id": admin["org_id"],
            },
        )
        viewer_token = login_resp.json()["access_token"]
        viewer_h = _auth_headers(viewer_token)

        # Viewer tries to invite — should fail
        _register_user(client, email="third@synchain.io", org_name="Third")
        resp = client.post(
            f"/api/v1/orgs/{admin['org_slug']}/members",
            json={"email": "third@synchain.io", "role": "member"},
            headers=viewer_h,
        )
        assert resp.status_code == 403

    def test_unauthenticated_org_access(self, client, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "debug", False)
        resp = client.get("/api/v1/orgs/")
        assert resp.status_code in (401, 403)
