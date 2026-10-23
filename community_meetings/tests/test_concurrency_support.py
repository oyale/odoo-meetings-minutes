from odoo.tests import TransactionCase, tagged

from .concurrency import run_concurrent_transactions


@tagged("post_install", "-at_install")
class TestConcurrencySupport(TransactionCase):
    def test_workers_use_independent_database_transactions(self):
        def prepare(env):
            return env["res.partner"].create({"name": "Concurrent transaction fixture"}).id

        def inspect_transaction(env, partner_id):
            visible_partner = env["res.partner"].browse(partner_id).exists()
            env.cr.execute("SELECT pg_backend_pid(), txid_current()")
            return (*env.cr.fetchone(), visible_partner.id)

        def cleanup(env, partner_id):
            env["res.partner"].browse(partner_id).sudo().unlink()

        results = run_concurrent_transactions(
            self,
            [inspect_transaction, inspect_transaction],
            prepare=prepare,
            cleanup=cleanup,
            timeout=5,
        )

        self.assertEqual(
            [result.error for result in results if result.error],
            [],
        )
        self.assertEqual(len({result.value[0] for result in results}), 2)
        self.assertEqual(len({result.value[1] for result in results}), 2)
        self.assertEqual(len({result.value[2] for result in results}), 1)
