"""Manual scaling benchmark for predecessor history loading.

Run only on a disposable database with devctl and select
``TestDiscussionHistoryBenchmark`` explicitly. The test reports SQL query count
and wall time for histories with increasing numbers of recurring occurrences.
"""

import logging
import time
from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "-standard", "discussion_history_benchmark")
class TestDiscussionHistoryBenchmark(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Discussion history benchmark editor",
                "login": "discussion-history-benchmark-editor",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        cls.series = (
            cls.env["community.meeting.series"]
            .with_user(cls.editor)
            .create({"name": "Discussion history benchmark series"})
        )
        cls.template = (
            cls.env["community.meeting.series.agenda.template"]
            .with_user(cls.editor)
            .create(
                {
                    "series_id": cls.series.id,
                    "name": "Benchmark point",
                    "agenda_type_id": cls.env.ref("community_meetings.agenda_type_discussion").id,
                }
            )
        )

    def test_history_load_scaling(self):
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        occurrences = agenda.browse()
        meetings = []
        first_start = datetime(2027, 1, 4, 10, 0, 0)
        for index in range(30):
            meeting = (
                self.env["community.meeting"]
                .with_user(self.editor)
                .create(
                    {
                        "name": f"Benchmark meeting {index + 1}",
                        "series_id": self.series.id,
                        "start_datetime": first_start + timedelta(days=7 * index),
                    }
                )
            )
            meetings.append(meeting)
            item = self.template.with_user(self.editor)._create_occurrence(meeting)
            item.discussion_notes = f"<p>Discussion entry {index + 1}</p>"
            occurrences |= item

        for length in (1, 5, 10, 20, 30):
            self.env.flush_all()
            self.env.invalidate_all()
            item = agenda.browse(occurrences[length - 1].id)
            query_start = self.env.cr.sql_log_count
            started = time.perf_counter()
            history = item.discussion_history
            elapsed_ms = (time.perf_counter() - started) * 1000
            query_count = self.env.cr.sql_log_count - query_start
            self.assertEqual(len(history["entries"]), length - 1)
            _logger.warning(
                "DISCUSSION_HISTORY_BENCHMARK chain=%s queries=%s elapsed_ms=%.2f entries=%s",
                length,
                query_count,
                elapsed_ms,
                len(history["entries"]),
            )

        latest_item_ids = [occurrences[-1].id]
        for template_index in range(9):
            template = (
                self.env["community.meeting.series.agenda.template"]
                .with_user(self.editor)
                .create(
                    {
                        "series_id": self.series.id,
                        "name": f"Benchmark point {template_index + 2}",
                        "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                    }
                )
            )
            for index, meeting in enumerate(meetings):
                item = template._create_occurrence(meeting)
                item.discussion_notes = f"<p>Discussion {template_index + 2}.{index + 1}</p>"
                if index == len(meetings) - 1:
                    latest_item_ids.append(item.id)

        self.env.flush_all()
        self.env.invalidate_all()
        current_agenda = self.env["community.meeting.agenda.item"].with_user(self.editor).browse(latest_item_ids)
        query_start = self.env.cr.sql_log_count
        started = time.perf_counter()
        histories = current_agenda.mapped("discussion_history")
        elapsed_ms = (time.perf_counter() - started) * 1000
        query_count = self.env.cr.sql_log_count - query_start
        self.assertEqual(len(histories), 10)
        self.assertTrue(all(len(history["entries"]) == 29 for history in histories))
        _logger.warning(
            "DISCUSSION_HISTORY_BENCHMARK live_agenda_items=%s chain=30 queries=%s elapsed_ms=%.2f total_entries=%s",
            len(histories),
            query_count,
            elapsed_ms,
            sum(len(history["entries"]) for history in histories),
        )
