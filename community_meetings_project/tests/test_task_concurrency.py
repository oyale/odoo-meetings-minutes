"""Real PostgreSQL transactions: TestCursor would serialize the worker threads."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, api, sql_db
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestProjectTaskConcurrency(TransactionCase):
    # Coordinate two transactions, observe their lock wait, then verify rollback.
    def test_delete_only_task_serializes_with_todo_closure(self):  # noqa: C901
        # Use independent committed fixtures: TransactionCase's fixtures and
        # TestCursor savepoints are invisible to real concurrent connections.
        database = sql_db.db_connect(self.cr.dbname)
        registry = self.registry
        context = {"tracking_disable": True, "mail_create_nosubscribe": True}
        with database.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, context)
            user = env["res.users"].create(
                {
                    "name": "Task race regression",
                    "login": "task-race-" + uuid.uuid4().hex,
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                env.ref("base.group_user").id,
                                env.ref("community_meetings.group_meeting_manager").id,
                                env.ref("project.group_project_user").id,
                            ],
                        )
                    ],
                }
            )
            actor = env(user=user)
            series = actor["community.meeting.series"].create(
                {
                    "name": user.login,
                    "meeting_todo_requirement": "project",
                }
            )
            meeting = actor["community.meeting"].create(
                {
                    "name": "Task deletion race",
                    "series_id": series.id,
                }
            )
            item = actor["community.meeting.agenda.item"].create(
                {
                    "meeting_id": meeting.id,
                    "name": "Only task TODO",
                    "kind": "todo",
                }
            )
            project = env["project.project"].create({"name": user.login})
            task = env["project.task"].create(
                {
                    "name": "Only linked task",
                    "project_id": project.id,
                    "user_ids": [(4, user.id)],
                }
            )
            actor["community.meeting.action"].create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Required Project evidence",
                    "responsible_user_id": user.id,
                    "followup_kind": "project_task",
                    "project_task_ids": [(4, task.id)],
                }
            )
            ids = {
                "user": user.id,
                "partner": user.partner_id.id,
                "series": series.id,
                "meeting": meeting.id,
                "item": item.id,
                "topic": item.topic_id.id,
                "project": project.id,
                "task": task.id,
            }
            cr.commit()

        validated = Event()
        release_delete = Event()
        closing_started = Event()
        closing_pid = []
        deleting_thread = []
        checker = type(self.env["community.meeting.project.task.mixin"])
        original_check = checker._check_closed_todo_project_tasks

        def pause_after_validation(records, agenda_items, *args, **kwargs):
            result = original_check(records, agenda_items, *args, **kwargs)
            if current_thread() is deleting_thread[0]:
                validated.set()
                if not release_delete.wait(15):
                    raise AssertionError("Timed out waiting to release task deletion")
            return result

        def delete_task():
            deleting_thread.append(current_thread())
            with database.cursor() as cr:
                # Registry lookup is globally locked while the suite runs.
                cr.transaction = api.Transaction(registry)
                env = api.Environment(cr, ids["user"], context)
                env["project.task"].browse(ids["task"]).unlink()
                cr.commit()

        def close_todo():
            for _attempt in range(3):
                with database.cursor() as cr:
                    cr.transaction = api.Transaction(registry)
                    env = api.Environment(cr, ids["user"], context)
                    cr.execute("SELECT pg_backend_pid()")
                    closing_pid[:] = [cr.fetchone()[0]]
                    closing_started.set()
                    try:
                        with mute_logger("odoo.sql_db"):
                            env["community.meeting.agenda.item"].browse(
                                ids["item"]
                            ).write({"disposition": "closed"})
                        cr.commit()
                        return "closed"
                    except SerializationFailure:
                        cr.rollback()
                    except ValidationError:
                        cr.rollback()
                        return "rejected"
            raise AssertionError("TODO closure exhausted serialization retries")

        try:
            with patch.object(
                checker, "_check_closed_todo_project_tasks", pause_after_validation
            ):
                with ThreadPoolExecutor(max_workers=2) as workers:
                    deletion = workers.submit(delete_task)
                    try:
                        self.assertTrue(validated.wait(10), "Deletion never validated")
                        closure = workers.submit(close_todo)
                        self.assertTrue(
                            closing_started.wait(10), "Closure never started"
                        )
                        # Observe actual lock contention rather than assuming a
                        # thread has reached a particular point after a sleep.
                        deadline = time.monotonic() + 10
                        blocked = False
                        with database.cursor() as observer:
                            while not closure.done() and time.monotonic() < deadline:
                                observer.execute(
                                    "SELECT pg_blocking_pids(%s)", closing_pid
                                )
                                blocked = bool(observer.fetchone()[0])
                                if blocked:
                                    break
                                release_delete.wait(0.01)
                    finally:
                        release_delete.set()
                    deletion.result(timeout=15)
                    self.assertEqual(closure.result(timeout=15), "rejected")
                    self.assertTrue(blocked, "Closure did not wait for the topic lock")
            with database.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, context)
                self.assertFalse(env["project.task"].browse(ids["task"]).exists())
                self.assertEqual(
                    env["community.meeting.agenda.item"]
                    .browse(ids["item"])
                    .disposition,
                    "open",
                )
        finally:
            # Never commit TransactionCase's own transaction. Remove only the
            # independently committed fixtures, including their private topic.
            with database.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, context)
                env["community.meeting"].browse(ids["meeting"]).exists().unlink()
                env["community.meeting.topic"].browse(ids["topic"]).exists().unlink()
                env["community.meeting.series"].browse(ids["series"]).exists().unlink()
                env["project.project"].browse(ids["project"]).exists().unlink()
                env["res.users"].browse(ids["user"]).exists().unlink()
                env["res.partner"].browse(ids["partner"]).exists().unlink()
                cr.commit()
