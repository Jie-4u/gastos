"""Regression tests for invitation security and Premium fail-closed behavior."""
import os
import unittest
from unittest.mock import patch
from datetime import date
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "gastos-test-secret"
os.environ["APP_BASE_URL"] = "https://gastos.example.test"
for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
    os.environ[key] = ""

import app as gastos


class CriticalFlowTests(unittest.TestCase):
    def setUp(self):
        with gastos.app.app_context():
            gastos.db.drop_all()
            gastos.db.create_all()
        self.client = gastos.app.test_client()
        owner = self.client.post("/api/signup", json={
            "name": "Owner", "email": "owner@example.com", "password": "password123"
        })
        self.owner_headers = {"Authorization": f"Bearer {owner.json['token']}"}
        self.client.post("/api/family", headers=self.owner_headers, json={"name": "Test Family"})

    def test_health_endpoint_checks_database_and_returns_ready(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_profile_edit_photo_email_and_password(self):
        initial = self.client.get("/api/profile", headers=self.owner_headers)
        self.assertEqual(initial.json["name"], "Owner")
        png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0ioAAAAASUVORK5CYII="
        wrong_password = self.client.put("/api/profile", headers=self.owner_headers, json={
            "name": "Updated Owner", "email": "new-owner@example.com", "current_password": "wrong",
        })
        self.assertEqual(wrong_password.status_code, 403)
        saved = self.client.put("/api/profile", headers=self.owner_headers, json={
            "name": "Updated Owner", "email": "new-owner@example.com", "current_password": "password123",
            "avatar_data": png,
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json["avatar_data"], png)
        self.assertEqual(self.client.get("/api/profile", headers=self.owner_headers).status_code, 200)
        self.assertEqual(self.client.put("/api/profile", headers=self.owner_headers,
            json={"avatar_data": "data:image/svg+xml,<svg onload=alert(1)>"}).status_code, 400)
        changed_password = self.client.put("/api/profile", headers=self.owner_headers, json={
            "current_password": "password123", "new_password": "changed-password",
        })
        self.assertEqual(changed_password.status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).status_code, 401)
        new_headers = {"Authorization": f"Bearer {changed_password.json['token']}"}
        self.assertEqual(self.client.get("/api/profile", headers=new_headers).json["email"], "new-owner@example.com")

    def test_new_family_starts_free_and_upgrade_never_grants_premium(self):
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "free")
        response = self.client.post("/api/upgrade", headers=self.owner_headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "free")

    def test_demo_upgrade_and_downgrade_only_when_demo_payments_enabled(self):
        with patch.dict(os.environ, {"DEMO_PAYMENTS": "1"}):
            self.assertEqual(self.client.post("/api/upgrade", headers=self.owner_headers,
                                              json={"period": "weekly"}).status_code, 400)
            self.assertEqual(self.client.post("/api/upgrade", headers=self.owner_headers,
                                              json={"period": "monthly"}).status_code, 200)
            self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "premium")
            self.assertEqual(self.client.post("/api/downgrade", headers=self.owner_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "free")

    def test_invitation_survives_refresh_resend_rotates_link_and_accepts_once(self):
        created = self.client.post("/api/invite", headers=self.owner_headers, json={"email": "member@example.com"})
        self.assertEqual(created.status_code, 200)
        invitation = created.json["invitation"]
        self.assertEqual(invitation["delivery"], "manual_share")
        token = invitation["link"].split("invite=", 1)[1]
        self.assertEqual(self.client.get(f"/api/invitations/{token}").status_code, 200)
        persisted = self.client.get("/api/me", headers=self.owner_headers).json["family"]["invites"][0]
        self.assertEqual(persisted["link"], invitation["link"])

        resent = self.client.post(f"/api/invitations/{invitation['id']}/resend", headers=self.owner_headers)
        replacement = resent.json["link"].split("invite=", 1)[1]
        self.assertEqual(self.client.get(f"/api/invitations/{token}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/invitations/{replacement}").status_code, 200)

        member = self.client.post("/api/signup", json={
            "name": "Member", "email": "member@example.com", "password": "password123"
        })
        member_headers = {"Authorization": f"Bearer {member.json['token']}"}
        self.assertIsNone(self.client.get("/api/me", headers=member_headers).json["family"])
        accept_url = f"/api/invitations/{replacement}/accept"
        self.assertEqual(self.client.post(accept_url, headers=member_headers).status_code, 200)
        self.assertEqual(self.client.post(accept_url, headers=member_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=member_headers).json["family"]["name"], "Test Family")

    def test_signup_with_invitation_joins_the_invited_family_atomically(self):
        created = self.client.post("/api/invite", headers=self.owner_headers,
                                   json={"email": "new-member@example.com"})
        token = created.json["invitation"]["link"].split("invite=", 1)[1]
        wrong_email = self.client.post("/api/signup", json={
            "name": "Wrong", "email": "wrong@example.com", "password": "password123",
            "invite_token": token,
        })
        self.assertEqual(wrong_email.status_code, 403)
        with gastos.app.app_context():
            self.assertIsNone(gastos.User.query.filter_by(email="wrong@example.com").first())
        accepted = self.client.post("/api/signup", json={
            "name": "New Member", "email": "new-member@example.com", "password": "password123",
            "invite_token": token,
        })
        self.assertEqual(accepted.status_code, 200)
        headers = {"Authorization": f"Bearer {accepted.json['token']}"}
        member = self.client.get("/api/me", headers=headers).json
        self.assertEqual(member["family"]["name"], "Test Family")
        self.assertFalse(member["family"]["owner"])
        self.assertEqual(member["family"]["role"], "Member")
        self.assertEqual(next(m["role"] for m in member["family"]["members"]
                              if m["name"] == "New Member"), "Member")
        self.assertEqual(self.client.get(f"/api/invitations/{token}").status_code, 404)

    def test_invitation_url_uses_configured_public_origin_and_missing_config_does_not_save(self):
        made = self.client.post("/api/invite", headers=self.owner_headers,
                                json={"email": "url-member@example.com"})
        self.assertTrue(made.json["invitation"]["link"].startswith("https://gastos.example.test/?invite="))
        with patch.dict(os.environ, {"APP_BASE_URL": ""}):
            missing = self.client.post("/api/invite", headers=self.owner_headers,
                                       json={"email": "no-link@example.com"})
        self.assertEqual(missing.status_code, 503)
        with gastos.app.app_context():
            self.assertIsNone(gastos.Invite.query.filter_by(email="no-link@example.com").first())

    def test_email_failure_is_reported_and_persisted_for_retry_ui(self):
        with patch("app.send_invitation_email", return_value="failed"):
            response = self.client.post("/api/invite", headers=self.owner_headers,
                                        json={"email": "delivery-failed@example.com"})
        self.assertEqual(response.json["invitation"]["delivery"], "failed")
        with gastos.app.app_context():
            stored = gastos.Invite.query.filter_by(email="delivery-failed@example.com").first()
            self.assertEqual(stored.delivery_status, "failed")
            self.assertIsNotNone(stored.delivery_attempted_at)

    def test_email_contains_html_button_and_plain_text_fallback(self):
        created = self.client.post("/api/invite", headers=self.owner_headers,
                                   json={"email": "html-member@example.com"})
        with gastos.app.app_context():
            invite = gastos.Invite.query.filter_by(email="html-member@example.com").one()
        link = created.json["invitation"]["link"]

        class FakeSMTP:
            def __init__(self, *args, **kwargs): self.message = None
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def ehlo(self): pass
            def starttls(self, **kwargs): pass
            def login(self, *args): pass
            def send_message(self, message): self.message = message

        fake = FakeSMTP()
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.example.test", "SMTP_PORT": "587",
                                     "SMTP_USERNAME": "test-login", "SMTP_PASSWORD": "test-secret",
                                     "SMTP_FROM": "noreply@example.test"}), patch("app.smtplib.SMTP", return_value=fake):
            with gastos.app.app_context():
                result = gastos.send_invitation_email(invite, link)
        self.assertEqual(result, "sent")
        self.assertTrue(fake.message.is_multipart())
        self.assertIn("Accept Family Invitation", fake.message.get_payload()[1].get_content())
        self.assertIn("Invitation link:", fake.message.get_payload()[1].get_content())
        self.assertIn(link, fake.message.get_payload()[0].get_content())

    def test_invited_member_has_limited_family_management_and_transaction_access(self):
        self.client.post("/api/transactions", headers=self.owner_headers, json={
            "kind": "expense", "amount": 20, "category": "Food", "note": "Owner purchase",
        })
        invite = self.client.post("/api/invite", headers=self.owner_headers,
                                  json={"email": "limited-member@example.com"}).json["invitation"]
        token = invite["link"].split("invite=", 1)[1]
        signup = self.client.post("/api/signup", json={"name": "Limited Member",
            "email": "limited-member@example.com", "password": "password123", "invite_token": token})
        member_headers = {"Authorization": f"Bearer {signup.json['token']}"}
        owner_tx_id = self.client.get("/api/transactions", headers=self.owner_headers).json[0]["id"]
        self.client.post("/api/transactions", headers=member_headers, json={
            "kind": "expense", "amount": 15, "category": "Food", "note": "Member purchase",
        })
        member_rows = self.client.get("/api/transactions", headers=member_headers).json
        own_row = next(row for row in member_rows if row["member"] == "Limited Member")
        other_row = next(row for row in member_rows if row["member"] == "Owner")
        self.assertTrue(own_row["can_edit"])
        self.assertFalse(other_row["can_edit"])
        self.assertEqual(self.client.put(f"/api/transactions/{owner_tx_id}", headers=member_headers,
            json={"kind": "expense", "amount": 25, "category": "Food", "date": date.today().isoformat()}).status_code, 403)
        self.client.post("/api/bills", headers=self.owner_headers, json={
            "name": "Internet", "amount": 50, "due": date.today().isoformat(),
        })
        self.assertEqual(self.client.post("/api/bills", headers=member_headers,
            json={"name": "Unauthorized bill", "amount": 1, "due": date.today().isoformat()}).status_code, 403)
        self.assertEqual(self.client.get("/api/bills", headers=member_headers).status_code, 200)
        with gastos.app.app_context():
            bill_id = gastos.Bill.query.filter_by(name="Internet").one().id
        self.assertEqual(self.client.post(f"/api/bills/{bill_id}/pay", headers=member_headers).status_code, 403)
        self.assertEqual(self.client.post("/api/budgets", headers=member_headers,
            json={"category": "Food", "monthly_limit": 100}).status_code, 403)
        self.assertEqual(self.client.post("/api/goals", headers=member_headers,
            json={"name": "Emergency fund", "target": 500}).status_code, 403)

    def test_dashboard_budget_progress_and_transaction_crud_are_family_scoped(self):
        created = self.client.post("/api/transactions", headers=self.owner_headers, json={
            "kind": "expense", "amount": 200, "category": "Food", "note": "Groceries",
            "date": date.today().isoformat(),
        })
        self.assertEqual(created.status_code, 200)
        budget = self.client.post("/api/budgets", headers=self.owner_headers,
                                  json={"category": "Food", "monthly_limit": 250})
        self.assertEqual(budget.status_code, 200)
        dashboard = self.client.get("/api/dashboard", headers=self.owner_headers).json
        self.assertEqual(dashboard["category_totals"]["Food"], 200)
        self.assertEqual(dashboard["budgets"][0]["status"], "approaching")
        self.assertEqual(dashboard["recent"][0]["member"], "Owner")
        tx = self.client.get("/api/transactions", headers=self.owner_headers).json[0]
        changed = self.client.put(f"/api/transactions/{tx['id']}", headers=self.owner_headers,
                                  json={"kind": "expense", "amount": 300, "category": "Food",
                                        "note": "Updated groceries", "date": tx["date"]})
        self.assertEqual(changed.status_code, 200)
        report = self.client.get("/api/reports", headers=self.owner_headers).json
        self.assertEqual(report["category_totals"]["Food"], 300)
        self.assertEqual(self.client.delete(f"/api/transactions/{tx['id']}", headers=self.owner_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/transactions", headers=self.owner_headers).json, [])

    def test_expired_invite_can_be_resent_and_other_family_cannot_see_transactions(self):
        created = self.client.post("/api/invite", headers=self.owner_headers,
                                   json={"email": "expiry-member@example.com"})
        invite_id = created.json["invitation"]["id"]
        with gastos.app.app_context():
            invitation = gastos.db.session.get(gastos.Invite, invite_id)
            invitation.expires_at = datetime.utcnow() - timedelta(seconds=1)
            gastos.db.session.commit()
        self.assertEqual(self.client.get(f"/api/invitations/{created.json['invitation']['link'].split('invite=')[1]}").status_code, 404)
        resent = self.client.post(f"/api/invitations/{invite_id}/resend", headers=self.owner_headers)
        self.assertEqual(resent.status_code, 200)
        self.assertEqual(self.client.get(f"/api/invitations/{resent.json['link'].split('invite=')[1]}").status_code, 200)

        other = self.client.post("/api/signup", json={"name": "Other", "email": "other-family@example.com", "password": "password123"})
        headers = {"Authorization": f"Bearer {other.json['token']}"}
        self.client.post("/api/family", headers=headers, json={"name": "Different Family"})
        self.client.post("/api/transactions", headers=self.owner_headers,
                         json={"kind": "income", "amount": 50, "category": "Allowance"})
        self.assertEqual(self.client.get("/api/transactions", headers=headers).json, [])

    def test_password_reset_uses_single_use_expiring_token_without_email_enumeration(self):
        with patch("app.send_password_reset_email", return_value="sent") as send_email:
            response = self.client.post("/api/password-reset/request", json={"email": "owner@example.com"})
            self.assertEqual(response.status_code, 200)
            link = send_email.call_args.args[1]
        token = parse_qs(urlsplit(link).query)["reset"][0]
        changed = self.client.post("/api/password-reset/complete", json={"token": token, "password": "newpassword123"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).status_code, 401)
        self.assertEqual(self.client.post("/api/signin", json={"email": "owner@example.com", "password": "password123"}).status_code, 401)
        self.assertEqual(self.client.post("/api/signin", json={"email": "owner@example.com", "password": "newpassword123"}).status_code, 200)
        self.assertEqual(self.client.post("/api/password-reset/complete", json={"token": token, "password": "anotherpass123"}).status_code, 400)
        with patch("app.send_password_reset_email") as no_account_email:
            unknown = self.client.post("/api/password-reset/request", json={"email": "unknown@example.com"})
            self.assertEqual(unknown.json, response.json)
            no_account_email.assert_not_called()

    def test_invitation_requires_matching_email_and_owner_to_revoke(self):
        created = self.client.post("/api/invite", headers=self.owner_headers, json={"email": "intended@example.com"})
        invitation = created.json["invitation"]
        token = invitation["link"].split("invite=", 1)[1]
        other = self.client.post("/api/signup", json={
            "name": "Other", "email": "other@example.com", "password": "password123"
        })
        other_headers = {"Authorization": f"Bearer {other.json['token']}"}
        self.client.post("/api/family", headers=other_headers, json={"name": "Other Family"})
        self.assertEqual(self.client.post(f"/api/invitations/{token}/accept", headers=other_headers).status_code, 403)
        self.assertEqual(self.client.post(f"/api/invitations/{invitation['id']}/revoke", headers=other_headers).status_code, 404)
        self.assertEqual(self.client.post(f"/api/invitations/{invitation['id']}/revoke", headers=self.owner_headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/invitations/{token}").status_code, 404)

    def test_invalid_money_dates_and_repeat_bill_payment_are_rejected(self):
        bad_amount = self.client.post("/api/transactions", headers=self.owner_headers,
                                      json={"amount": "NaN", "kind": "expense"})
        self.assertEqual(bad_amount.status_code, 400)
        bad_date = self.client.post("/api/transactions", headers=self.owner_headers,
                                    json={"amount": 10, "kind": "transfer", "date": "not-a-date"})
        self.assertEqual(bad_date.status_code, 400)
        self.client.post("/api/bills", headers=self.owner_headers, json={"name": "Power", "amount": 10})
        with gastos.app.app_context():
            bill_id = gastos.Bill.query.first().id
        edited = self.client.put(f"/api/bills/{bill_id}", headers=self.owner_headers,
                                 json={"name": "Power bill", "amount": 12, "due": date.today().isoformat()})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(self.client.post(f"/api/bills/{bill_id}/pay", headers=self.owner_headers).status_code, 200)
        self.assertEqual(self.client.post(f"/api/bills/{bill_id}/pay", headers=self.owner_headers).status_code, 409)
        self.assertEqual(self.client.delete(f"/api/bills/{bill_id}", headers=self.owner_headers).status_code, 409)
        self.client.post("/api/bills", headers=self.owner_headers, json={"name": "Water", "amount": 9})
        with gastos.app.app_context():
            water_id = gastos.Bill.query.filter_by(name="Water").one().id
        self.assertEqual(self.client.delete(f"/api/bills/{water_id}", headers=self.owner_headers).status_code, 200)

    def test_paymongo_checkout_is_mocked_and_does_not_grant_premium(self):
        plan = {"data": {"attributes": {"currency": "PHP", "amount": 9900,
                                           "interval": "monthly", "interval_count": 1}}}
        customer = {"data": {"id": "cus_test_1"}}
        created = {"data": {"id": "sub_test_1", "attributes": {
            "status": "incomplete", "latest_invoice": {"payment_intent": {"id": "pi_test_1"}}
        }}}
        intent = {"data": {"attributes": {"client_key": "pi_test_1_client"}}}

        def fake_request(method, path, payload=None, idempotency_key=None):
            if method == "GET" and path.startswith("/subscriptions/plans/"):
                return plan
            if method == "POST" and path == "/customers":
                return customer
            if method == "POST" and path == "/subscriptions":
                return created
            if method == "GET" and path == "/payment_intents/pi_test_1":
                return intent
            self.fail(f"Unexpected PayMongo request: {method} {path}")

        with patch.dict(os.environ, {
            "PAYMENT_PROVIDER": "paymongo", "PAYMENT_PROVIDER_SECRET": "sk_test_mock",
            "PAYMENT_PUBLIC_KEY": "pk_test_mock", "PAYMONGO_PLAN_MONTHLY_ID": "plan_test_monthly",
        }, clear=False), patch("app.paymongo_request", side_effect=fake_request):
            response = self.client.post("/api/subscriptions/checkout", headers=self.owner_headers,
                                        json={"period": "monthly", "payment_method": "card"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["payment_intent_id"], "pi_test_1")
        self.assertEqual(response.json["amount"], 99)
        self.assertTrue(response.json["return_url"].startswith("https://gastos.example.test/"))
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "free")

    def test_paymongo_webhook_requires_valid_signature_and_deduplicates_events(self):
        with gastos.app.app_context():
            family_id = gastos.Family.query.one().id
            subscription = gastos.Subscription(family_id=family_id, plan="premium", period="monthly",
                                               amount=99, status="incomplete", provider_reference="sub_test_webhook")
            gastos.db.session.add(subscription)
            gastos.db.session.commit()

        envelope = {"data": {"id": "evt_test_1", "attributes": {
            "type": "subscription.activated", "livemode": False,
            "data": {"id": "sub_test_webhook", "attributes": {"status": "active"}},
        }}}
        raw = __import__("json").dumps(envelope, separators=(",", ":")).encode()
        timestamp = str(int(__import__("time").time()))
        digest = gastos.hmac.new(b"whsec_test_mock", timestamp.encode() + b"." + raw,
                                 gastos.hashlib.sha256).hexdigest()
        headers = {"Paymongo-Signature": f"t={timestamp},te={digest}"}
        with patch.dict(os.environ, {
            "PAYMENT_PROVIDER_SECRET": "sk_test_mock", "PAYMONGO_WEBHOOK_SECRET": "whsec_test_mock",
        }, clear=False):
            self.assertEqual(self.client.post("/webhooks/paymongo", data=raw,
                                               headers={"Paymongo-Signature": f"t={timestamp},te=bad"}).status_code, 401)
            first = self.client.post("/webhooks/paymongo", data=raw, headers=headers)
            second = self.client.post("/webhooks/paymongo", data=raw, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json.get("duplicate"), True)
        self.assertEqual(self.client.get("/api/me", headers=self.owner_headers).json["family"]["plan"], "premium")

    def test_owner_can_remove_member_without_deleting_account_or_history(self):
        invite = self.client.post("/api/invite", headers=self.owner_headers,
                                  json={"email": "remove-me@example.com"}).json["invitation"]
        signed = invite["link"].split("invite=", 1)[1]
        signup = self.client.post("/api/signup", json={"name": "Member", "email": "remove-me@example.com",
                                                        "password": "password123", "invite_token": signed})
        member_headers = {"Authorization": f"Bearer {signup.json['token']}"}
        self.client.post("/api/transactions", headers=member_headers,
                         json={"kind": "expense", "amount": 75, "category": "Food", "note": "History"})
        with gastos.app.app_context():
            member = gastos.User.query.filter_by(email="remove-me@example.com").one()
            member_id = member.id
        self.assertEqual(self.client.delete(f"/api/family/members/{member_id}", headers=member_headers).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/family/members/{member_id}", headers=self.owner_headers).status_code, 200)
        self.assertIsNone(self.client.get("/api/me", headers=member_headers).json["family"])
        with gastos.app.app_context():
            self.assertEqual(gastos.Tx.query.filter_by(note="History").count(), 1)

    def test_bill_status_uses_philippine_local_date(self):
        today = gastos.app_today()
        for label, due in (("Today bill", today), ("Old bill", today - timedelta(days=1))):
            self.client.post("/api/bills", headers=self.owner_headers,
                             json={"name": label, "amount": 100, "due": due.isoformat()})
        bills = {row["name"]: row for row in self.client.get("/api/bills", headers=self.owner_headers).json}
        self.assertEqual(bills["Today bill"]["due_status"], "due_today")
        self.assertEqual(bills["Old bill"]["due_status"], "overdue")


    def test_wallets_belong_to_each_account_and_track_balances(self):
        def post(path, body, headers=None):
            return self.client.post(path, headers=headers or self.owner_headers, json=body)

        cash = post("/api/wallets", {"kind": "cash", "name": "Cash on hand", "opening_balance": 1000}).json["id"]
        debit = post("/api/wallets", {"kind": "card", "card_type": "debit", "name": "Payroll", "bank": "BDO",
                                      "last4": "4821", "opening_balance": 5000}).json["id"]
        credit = post("/api/wallets", {"kind": "card", "card_type": "credit", "name": "Shopping", "bank": "BPI",
                                       "last4": "1188", "credit_limit": 30000, "opening_balance": 2000}).json["id"]
        # Only the last 4 digits are accepted; bad input is rejected.
        for bad in ({"last4": "4111111111111111"}, {"last4": "12a4"}, {"last4": ""}, {"card_type": "prepaid"}):
            body = {"kind": "card", "card_type": "debit", "name": "Bad", "last4": "1234", **bad}
            self.assertEqual(post("/api/wallets", body).status_code, 400, bad)
        self.assertEqual(post("/api/wallets", {"kind": "cash", "name": "", "opening_balance": 0}).status_code, 400)
        self.assertEqual(post("/api/wallets", {"kind": "cash", "name": "X", "opening_balance": -5}).status_code, 400)
        self.assertEqual(post("/api/wallets", {"kind": "crypto", "name": "X"}).status_code, 400)

        today = date.today().isoformat()
        for wallet_id, kind, amount in ((cash, "expense", 250), (cash, "income", 100), (debit, "expense", 1200),
                                        (credit, "expense", 500), (credit, "income", 300)):
            self.assertEqual(post("/api/transactions", {"kind": kind, "amount": amount, "category": "Other",
                                                        "date": today, "wallet_id": wallet_id}).status_code, 200)
        listing = self.client.get("/api/wallets", headers=self.owner_headers).json
        balances = {w["id"]: w for w in listing["wallets"]}
        self.assertEqual(balances[cash]["balance"], 850)
        self.assertEqual(balances[debit]["balance"], 3800)
        self.assertEqual(balances[credit]["owed"], 2200)          # 2000 owed + 500 spent - 300 paid
        self.assertEqual(balances[credit]["available"], 27800)
        self.assertEqual(listing["totals"], {"cash": 850, "debit": 3800, "available": 4650, "owed": 2200})
        self.assertEqual([w["kind"] for w in listing["wallets"]], ["cash", "card", "card"])

        # Adjust sets the balance (or the amount owed) without adding a transaction.
        self.assertEqual(post(f"/api/wallets/{cash}/adjust", {"amount": 1000}).status_code, 200)
        self.assertEqual(post(f"/api/wallets/{credit}/adjust", {"amount": 0}).status_code, 200)
        balances = {w["id"]: w for w in self.client.get("/api/wallets", headers=self.owner_headers).json["wallets"]}
        self.assertEqual(balances[cash]["balance"], 1000)
        self.assertEqual(balances[credit]["owed"], 0)
        self.assertEqual(len(self.client.get("/api/transactions", headers=self.owner_headers).json), 5)

        # Wallet detail shows its own transactions; edit keeps the card type and never changes the balance.
        detail = self.client.get(f"/api/wallets/{debit}", headers=self.owner_headers).json
        self.assertEqual([t["wallet"] for t in detail["transactions"]], ["Payroll"])
        edited = self.client.put(f"/api/wallets/{debit}", headers=self.owner_headers,
                                 json={"name": "Payroll card", "bank": "BDO", "last4": "9999", "card_type": "credit"})
        self.assertEqual(edited.status_code, 200)
        detail = self.client.get(f"/api/wallets/{debit}", headers=self.owner_headers).json
        self.assertEqual((detail["name"], detail["last4"], detail["card_type"], detail["balance"]),
                         ("Payroll card", "9999", "debit", 3800))

        # A transaction can only use a wallet that exists and belongs to the person logging it.
        self.assertEqual(post("/api/transactions", {"kind": "expense", "amount": 5, "category": "Food",
                                                    "wallet_id": 99999}).status_code, 400)

        # A family member has their own wallets: they cannot see, use or change the owner's, and any
        # member can manage their own without being a Parent.
        invite = self.client.post("/api/invite", headers=self.owner_headers, json={"email": "wallet-member@example.com"}).json["invitation"]
        token = invite["link"].split("invite=", 1)[1]
        signup = self.client.post("/api/signup", json={"name": "Wallet Member", "email": "wallet-member@example.com",
                                                       "password": "password123", "invite_token": token})
        member = {"Authorization": f"Bearer {signup.json['token']}"}
        self.assertEqual(self.client.get("/api/wallets", headers=member).json["wallets"], [])
        self.assertEqual(self.client.get(f"/api/wallets/{cash}", headers=member).status_code, 404)
        self.assertEqual(self.client.put(f"/api/wallets/{cash}", headers=member, json={"name": "Mine"}).status_code, 404)
        self.assertEqual(post(f"/api/wallets/{cash}/adjust", {"amount": 1}, member).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/wallets/{cash}", headers=member).status_code, 404)
        self.assertEqual(post("/api/transactions", {"kind": "expense", "amount": 10, "category": "Food",
                                                    "wallet_id": cash}, member).status_code, 400)
        mine = post("/api/wallets", {"kind": "cash", "name": "Allowance", "opening_balance": 200}, member)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(post("/api/transactions", {"kind": "expense", "amount": 50, "category": "Food",
                                                    "date": today, "wallet_id": mine.json["id"]}, member).status_code, 200)
        member_wallets = self.client.get("/api/wallets", headers=member).json
        self.assertEqual([(w["name"], w["balance"]) for w in member_wallets["wallets"]], [("Allowance", 150)])
        # The owner's balances are unaffected, and the owner never sees the member's wallet name or id.
        owner_wallets = self.client.get("/api/wallets", headers=self.owner_headers).json["wallets"]
        self.assertEqual(sorted(w["name"] for w in owner_wallets), ["Cash on hand", "Payroll card", "Shopping"])
        member_tx = [t for t in self.client.get("/api/transactions", headers=self.owner_headers).json if t["amount"] == 50][0]
        self.assertEqual((member_tx["wallet"], member_tx["wallet_id"], member_tx["mine"]), (None, None, False))
        # Even an owner editing the member's transaction cannot attach the owner's wallet to it.
        self.assertEqual(self.client.put(f"/api/transactions/{member_tx['id']}", headers=self.owner_headers,
                                         json={"kind": "expense", "amount": 50, "category": "Food", "date": today,
                                               "wallet_id": cash}).status_code, 400)

        # Another family's account sees nothing of this one.
        other = self.client.post("/api/signup", json={"name": "Other", "email": "other-wallets@example.com", "password": "password123"})
        other_headers = {"Authorization": f"Bearer {other.json['token']}"}
        self.client.post("/api/family", headers=other_headers, json={"name": "Other Family"})
        self.assertEqual(self.client.get(f"/api/wallets/{cash}", headers=other_headers).status_code, 404)
        self.assertEqual(self.client.get("/api/wallets", headers=other_headers).json["wallets"], [])

        # Dashboard summary is per account, then deleting a wallet keeps its transactions but unlinks them.
        dash = self.client.get("/api/dashboard", headers=self.owner_headers).json
        self.assertEqual(dash["wallet_count"], 3)
        self.assertEqual(dash["wallet_totals"]["available"], dash["wallet_totals"]["cash"] + dash["wallet_totals"]["debit"])
        self.assertEqual(self.client.get("/api/dashboard", headers=member).json["wallet_count"], 1)
        self.assertEqual(self.client.delete(f"/api/wallets/{debit}", headers=self.owner_headers).status_code, 200)
        rows = self.client.get("/api/transactions", headers=self.owner_headers).json
        self.assertEqual(len(rows), 6)
        self.assertEqual([r["wallet"] for r in rows if r["amount"] == 1200], [None])


if __name__ == "__main__":
    unittest.main()
