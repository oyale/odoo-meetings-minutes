"""Helpers for tests that need genuinely independent PostgreSQL transactions."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Barrier, BrokenBarrierError, Thread
from typing import Any

from odoo import api


@dataclass(frozen=True)
class ConcurrentResult:
    """Result of one committed or rolled-back worker transaction."""

    index: int
    value: Any = None
    error: Exception | None = None


def _run_worker(index, operation, registry, uid, context, fixture, timeout, barrier, results):
    try:
        with registry.cursor() as cursor:
            # Environment.__new__ calls Registry(dbname), whose global registry
            # lock is held by Odoo's post-install test runner. Reuse the loaded
            # registry and give this transaction its own ORM cache.
            cursor.transaction = api.Transaction(registry)
            env = api.Environment(cursor, uid, context)
            timeout_ms = max(1, int(timeout * 1000))
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [f"{timeout_ms}ms"])
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                [f"{timeout_ms}ms"],
            )
            try:
                barrier.wait(timeout=timeout)
                value = operation(env, fixture)
                cursor.commit()
                result = ConcurrentResult(index=index, value=value)
            except BrokenBarrierError:
                cursor.rollback()
                result = ConcurrentResult(
                    index=index,
                    error=TimeoutError("workers did not reach the start barrier"),
                )
            except Exception as error:  # noqa: BLE001 - return worker failures for assertions
                cursor.rollback()
                result = ConcurrentResult(index=index, error=error)
            results.append(result)
    except Exception as error:  # noqa: BLE001 - include cursor setup failures
        results.append(ConcurrentResult(index=index, error=error))


def run_concurrent_transactions(  # noqa: C901 - keep transaction lifecycle orchestration together
    test_case,
    operations: list[Callable[[api.Environment, Any], Any]],
    *,
    prepare: Callable[[api.Environment], Any] | None = None,
    cleanup: Callable[[api.Environment, Any], None] | None = None,
    timeout: float = 5,
) -> list[ConcurrentResult]:
    """Run operations at a barrier in separate cursors and transactions.

    ``prepare`` and ``cleanup`` run in their own committed transactions so all
    workers can see the fixture. The cleanup callback runs after completed
    workers even when one operation fails. A successful worker commits; a
    failed worker rolls back and returns its exception in ``ConcurrentResult``.
    PostgreSQL lock and statement timeouts bound database waits.

    Do not pass records created in ``test_case.env``: worker transactions
    cannot see uncommitted ``TransactionCase`` data. Keep callbacks limited to
    bounded database work; Python code blocked outside PostgreSQL cannot be
    interrupted safely from another thread.
    """
    if len(operations) < 2:
        raise ValueError("concurrent tests need at least two operations")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if (prepare is None) != (cleanup is None):
        raise ValueError("prepare and cleanup must be provided together")

    registry = test_case.env.registry
    uid = test_case.env.uid
    context = dict(test_case.env.context)

    def in_transaction(callback, *args):
        with registry.cursor() as cursor:
            env = api.Environment(cursor, uid, context)
            value = callback(env, *args)
            cursor.commit()
            return value

    fixture = in_transaction(prepare) if prepare else None
    barrier = Barrier(len(operations))
    results = []
    threads = [
        Thread(
            target=_run_worker,
            args=(
                index,
                operation,
                registry,
                uid,
                context,
                fixture,
                timeout,
                barrier,
                results,
            ),
            name=f"odoo-concurrency-test-{index}",
            daemon=True,
        )
        for index, operation in enumerate(operations)
    ]
    try:
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + timeout * 2
        for thread in threads:
            thread.join(max(0, deadline - time.monotonic()))
        pending = [thread for thread in threads if thread.is_alive()]
        if pending:
            barrier.abort()
            raise TimeoutError(f"{len(pending)} concurrent database operation(s) exceeded {timeout * 2:g}s")
        results_by_index = sorted(results, key=lambda result: result.index)
        if len(results_by_index) != len(operations):
            raise RuntimeError("a concurrent worker exited without returning a result")
        timeout_results = [result for result in results_by_index if isinstance(result.error, TimeoutError)]
        if timeout_results:
            raise timeout_results[0].error
        return results_by_index
    finally:
        if cleanup and all(not thread.is_alive() for thread in threads):
            in_transaction(cleanup, fixture)
