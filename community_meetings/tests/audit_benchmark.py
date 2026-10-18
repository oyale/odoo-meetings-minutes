"""Repeatable ORM-path measurements for PLAN_AUDIT_REMEDIATION_2026-10-18.

Run through Odoo shell with this file on stdin against an isolated database.
Setup writes are outside each measured section; each size uses fresh records in
the same company and user context. Calendar synchronization uses
``calendar.block_mail``.
"""

import json
import re
import time
import uuid
from collections import Counter

from odoo.exceptions import ValidationError
from odoo.models import BaseModel
from odoo.tools.profiler import Profiler

env = globals()["env"]
run_id = uuid.uuid4().hex[:8]
editor = env["res.users"].create(
    {
        "name": f"Audit Benchmark Editor {run_id}",
        "login": f"audit-benchmark-editor-{run_id}",
        "company_id": env.company.id,
        "company_ids": [(6, 0, [env.company.id])],
        "groups_id": [
            (
                6,
                0,
                [
                    env.ref("base.group_user").id,
                    env.ref("community_meetings.group_meeting_editor").id,
                    env.ref("project.group_project_user").id,
                ],
            )
        ],
    }
)


def model(name):
    return env[name].with_user(editor)


def measure(label, size, operation):
    # Keep fixture writes out of the measured interval, but include deferred
    # writes and recomputations caused by the operation itself.
    env.flush_all()
    started = time.perf_counter()
    with Profiler(collectors=["sql"]) as profiler:
        operation()
        env.flush_all()
    wall_seconds = time.perf_counter() - started
    sql = next(
        collector for collector in profiler.collectors if collector.name == "sql"
    )
    entries = sql.entries
    result = {
        "benchmark_run_id": run_id,
        "operation": label,
        "size": size,
        "sql_count": len(entries),
        "sql_seconds": round(sum(entry["time"] for entry in entries), 6),
        "wall_seconds": round(wall_seconds, 6),
    }
    if label == "todo_validation_valid":
        result["mail_activity_selects"] = sum(
            'FROM "mail_activity"' in entry["query"]
            and entry["query"].lstrip().startswith("SELECT")
            for entry in entries
        )
        query_counts = Counter(
            re.sub(r"\s+", " ", entry["query"]).strip() for entry in entries
        )
        result["top_sql_shapes"] = [
            {"count": count, "query": query[:400]}
            for query, count in query_counts.most_common(12)
            if count > 1
        ]
    return result


def measure_rejected(label, size, operation):
    def reject_in_savepoint():
        try:
            with env.cr.savepoint():
                operation()
        except ValidationError:
            return
        raise AssertionError(f"{label} unexpectedly succeeded")

    return measure(label, size, reject_in_savepoint)


def new_meetings(label, size, **values):
    return model("community.meeting").create(
        [
            {
                "name": f"Audit {label} {size} {index}",
                "start_datetime": "2026-12-01 10:00:00",
                **values,
            }
            for index in range(size)
        ]
    )


def run(size):
    rows = []

    meeting = new_meetings("create", 1)
    rows.append(
        measure(
            "agenda_create_default_type",
            size,
            lambda: model("community.meeting.agenda.item").create(
                [
                    {
                        "meeting_id": meeting.id,
                        "name": f"Default point {size} {index}",
                        "kind": "discussion",
                    }
                    for index in range(size)
                ]
            ),
        )
    )

    explicit_type_meeting = new_meetings("explicit-type", 1)
    explicit_type = env.ref("community_meetings.agenda_type_discussion")
    rows.append(
        measure(
            "agenda_create_explicit_type",
            size,
            lambda: model("community.meeting.agenda.item").create(
                [
                    {
                        "meeting_id": explicit_type_meeting.id,
                        "name": f"Explicit point {size} {index}",
                        "agenda_type_id": explicit_type.id,
                    }
                    for index in range(size)
                ]
            ),
        )
    )

    mixed_meeting = new_meetings("mixed-create", 1)
    kinds = ("discussion", "todo", "decision")
    rows.append(
        measure(
            "agenda_create_mixed_behaviors",
            size,
            lambda: model("community.meeting.agenda.item").create(
                [
                    {
                        "meeting_id": mixed_meeting.id,
                        "name": f"Mixed point {size} {index}",
                        "kind": kinds[index % len(kinds)],
                    }
                    for index in range(size)
                ]
            ),
        )
    )

    decision_meeting = new_meetings("decision-validation", 1)
    decisions = model("community.meeting.agenda.item").create(
        [
            {
                "meeting_id": decision_meeting.id,
                "name": f"Decision {size} {index}",
                "kind": "decision",
            }
            for index in range(size)
        ]
    )
    model("community.meeting.resolution").create(
        [
            {
                "meeting_id": decision_meeting.id,
                "agenda_item_id": item.id,
                "title": f"Resolution {size} {index}",
                "decision_outcome": "approved",
            }
            for index, item in enumerate(decisions)
        ]
    )
    rows.append(
        measure(
            "decision_validation",
            size,
            decisions._check_workflow_requirements,
        )
    )
    invalid_decision = model("community.meeting.agenda.item").create(
        {
            "meeting_id": decision_meeting.id,
            "name": f"Invalid decision {size}",
            "kind": "decision",
        }
    )
    rows.append(
        measure_rejected(
            "decision_validation_invalid",
            size,
            lambda: invalid_decision.write({"disposition": "closed"}),
        )
    )

    todo_meeting = new_meetings("todo-validation", 1)
    todo_items = model("community.meeting.agenda.item").create(
        [
            {
                "meeting_id": todo_meeting.id,
                "name": f"TODO {size} {index}",
                "kind": "todo",
            }
            for index in range(size)
        ]
    )
    model("community.meeting.action").create(
        [
            {
                "meeting_id": todo_meeting.id,
                "agenda_item_id": item.id,
                "name": f"TODO action {size} {index}",
                "responsible_user_id": editor.id,
                "followup_kind": "activity",
            }
            for index, item in enumerate(todo_items)
        ]
    )
    agenda_item_class = type(todo_items)
    lookup_name = (
        "_followup_actions_by_topic"
        if hasattr(agenda_item_class, "_followup_actions_by_topic")
        else "_followup_actions"
    )
    original_followup_lookup = getattr(agenda_item_class, lookup_name)
    action_model_class = type(model("community.meeting.action"))
    evidence_method_name = (
        "_execution_evidence_by_action"
        if hasattr(action_model_class, "_execution_evidence_by_action")
        else "_has_execution_evidence"
    )
    original_execution_evidence = getattr(action_model_class, evidence_method_name)
    followup_lookup_batch_sizes = []
    evidence_check_counts = []
    action_topic_mapping_sizes = []

    def count_followup_lookups(items):
        followup_lookup_batch_sizes.append(len(items))
        return original_followup_lookup(items)

    def count_execution_evidence(actions):
        evidence_check_counts.append(len(actions))
        return original_execution_evidence(actions)

    original_mapped = BaseModel.mapped

    def count_action_topic_mapping(records, field_name):
        if records._name == "community.meeting.action" and field_name == "topic_id":
            action_topic_mapping_sizes.append(len(records))
        return original_mapped(records, field_name)

    setattr(agenda_item_class, lookup_name, count_followup_lookups)
    setattr(action_model_class, evidence_method_name, count_execution_evidence)
    setattr(BaseModel, "mapped", count_action_topic_mapping)
    try:
        todo_measurement = measure(
            "todo_validation_valid",
            size,
            lambda: todo_items.write({"disposition": "closed"}),
        )
    finally:
        setattr(agenda_item_class, lookup_name, original_followup_lookup)
        setattr(action_model_class, evidence_method_name, original_execution_evidence)
        setattr(BaseModel, "mapped", original_mapped)
    todo_measurement["followup_lookup_batch_sizes"] = followup_lookup_batch_sizes
    todo_measurement["evidence_check_counts"] = evidence_check_counts
    todo_measurement["execution_evidence_calls"] = len(evidence_check_counts)
    todo_measurement["action_topic_mapping_sizes"] = action_topic_mapping_sizes
    if lookup_name == "_followup_actions_by_topic":
        assert followup_lookup_batch_sizes == [size], (
            f"Expected one batched lookup of {size} items, got {followup_lookup_batch_sizes}"
        )
    if evidence_method_name == "_execution_evidence_by_action":
        assert evidence_check_counts == [size], (
            f"Expected one per-action evidence batch of {size}, got {evidence_check_counts}"
        )
    rows.append(todo_measurement)
    invalid_todo = model("community.meeting.agenda.item").create(
        {
            "meeting_id": todo_meeting.id,
            "name": f"Invalid TODO {size}",
            "kind": "todo",
        }
    )
    rows.append(
        measure_rejected(
            "todo_validation_invalid",
            size,
            lambda: invalid_todo.write({"disposition": "closed"}),
        )
    )

    promotion_meetings = new_meetings("promotion", size)
    for meeting_item in promotion_meetings:
        item = model("community.meeting.agenda.item").create(
            {"meeting_id": meeting_item.id, "name": "Closed origin"}
        )
        item.write({"disposition": "closed"})
        model("community.meeting.action").create(
            {
                "meeting_id": meeting_item.id,
                "agenda_item_id": item.id,
                "name": "Promote this follow-up",
            }
        )
    rows.append(
        measure(
            "followup_promotion_new",
            size,
            promotion_meetings._promote_followups,
        )
    )
    rows.append(
        measure(
            "followup_promotion_already_promoted",
            size,
            promotion_meetings._promote_followups,
        )
    )

    project = env["project.project"].create(
        {"name": f"Audit project {size}", "user_id": editor.id}
    )
    unlinked_tasks = model("project.task").create(
        [
            {"name": f"Unlinked task {size} {index}", "project_id": project.id}
            for index in range(size)
        ]
    )
    rows.append(
        measure(
            "project_task_write_unlinked_irrelevant_field",
            size,
            lambda: unlinked_tasks.write({"name": f"Unlinked renamed {size}"}),
        )
    )
    task_meeting = new_meetings("task-write", 1)
    task_item = model("community.meeting.agenda.item").create(
        {"meeting_id": task_meeting.id, "name": "Task write point"}
    )
    linked_tasks = model("project.task").create(
        [
            {"name": f"Linked task {size} {index}", "project_id": project.id}
            for index in range(size)
        ]
    )
    model("community.meeting.action").create(
        {
            "meeting_id": task_meeting.id,
            "agenda_item_id": task_item.id,
            "name": "Linked follow-up",
            "followup_kind": "project_task",
            "project_task_ids": [(6, 0, linked_tasks.ids)],
        }
    )
    rows.append(
        measure(
            "project_task_write_linked_irrelevant_field",
            size,
            lambda: linked_tasks.write({"name": f"Linked renamed {size}"}),
        )
    )
    rows.append(
        measure(
            "project_task_write_linked_state",
            size,
            lambda: linked_tasks.write({"state": "01_in_progress"}),
        )
    )

    model("ir.config_parameter").sudo().set_param("calendar.block_mail", "1")
    calendar_meetings = new_meetings(
        "calendar", size, attendee_partner_ids=[(4, editor.partner_id.id)]
    )
    rows.append(
        measure(
            "calendar_attendee_constraint",
            size,
            calendar_meetings._check_calendar_attendees,
        )
    )
    env.cr.execute(
        "UPDATE community_meeting SET state='scheduled' WHERE id IN %s",
        [tuple(calendar_meetings.ids)],
    )
    calendar_meetings.invalidate_recordset(["state"])
    calendar_meetings._lock_calendar_event()
    rows.append(
        measure(
            "calendar_sync_create",
            size,
            calendar_meetings._sync_calendar_event,
        )
    )
    rows.append(
        measure(
            "calendar_sync_no_change",
            size,
            calendar_meetings._sync_calendar_event,
        )
    )
    return rows


print(json.dumps([row for size in (1, 10, 100) for row in run(size)], sort_keys=True))
