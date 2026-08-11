"""Stage 4 — Verify: identity + evidence checks → Resolution."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from terminal_insight_v2.category.loader import load_category_schema
from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.stages.base import Stage
from terminal_insight_v2.store.db import transaction, utc_now
from terminal_insight_v2.verify.resolution import (
    clear_verify_for_run,
    insert_verification,
    load_assertions_for_run,
    load_devices_for_run,
    load_locked_fields,
    resolve_field,
    upsert_resolution,
)
from terminal_insight_v2.verify.validators import run_validators, snippet_supports_value

console = Console()


class VerifyStage(Stage):
    name = "verify"

    def prereq(self, ctx: StageContext) -> None:
        assertions = load_assertions_for_run(ctx.run_id)
        path = Path(ctx.run_dir) / "assertions.jsonl"
        if not assertions and not path.exists():
            raise FileNotFoundError(
                f"缺少 assertions（run={ctx.run_id}）；请先跑 extract"
            )

    def run(self, ctx: StageContext) -> StageResult:
        schema = load_category_schema(ctx.category, persist=False)
        field_defs = {f.name: f for f in schema.fields}
        identity_names = set(schema.identity_fields)

        assertions = load_assertions_for_run(ctx.run_id)
        devices = load_devices_for_run(ctx.run_id)
        console.log(
            f"[verify] devices={len(devices)} assertions={len(assertions)}"
        )

        verification_rows: List[Dict[str, Any]] = []
        accepted_by_df: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        issues: List[Dict[str, Any]] = []

        with transaction() as conn:
            clear_verify_for_run(conn, ctx.run_id)

            for a in assertions:
                identity_ok = int(a.get("match_ok") or 0) == 1 or (
                    (a.get("identity_status") or "") in ("match", "unknown", "")
                )
                # Prefer explicit mismatch
                if (a.get("identity_status") or "") == "mismatch":
                    identity_ok = False
                if int(a.get("match_ok") or 1) == 0:
                    identity_ok = False

                evidence_ok, ev_note = snippet_supports_value(
                    a.get("snippet") or "", a.get("value_text") or ""
                )
                fdef = field_defs.get(a["field_name"])
                val_ok, val_note = True, "no_validators"
                if fdef and fdef.validators:
                    val_ok, val_note = run_validators(
                        a.get("value_text") or "", fdef.validators
                    )

                if not identity_ok:
                    status = "identity_fail"
                elif not evidence_ok:
                    status = "evidence_fail"
                elif not val_ok:
                    status = "validator_fail"
                else:
                    status = "accepted"

                notes = f"ev={ev_note}; val={val_note}"
                insert_verification(
                    conn,
                    assertion_id=a["assertion_id"],
                    identity_ok=identity_ok,
                    evidence_ok=evidence_ok and val_ok,
                    accuracy_status=status,
                    notes=notes,
                )
                verification_rows.append(
                    {
                        "assertion_id": a["assertion_id"],
                        "device_id": a["device_id"],
                        "brand": a["brand"],
                        "model": a["model"],
                        "field_name": a["field_name"],
                        "value_text": a["value_text"],
                        "status": status,
                        "notes": notes,
                        "source_url": a.get("url"),
                    }
                )
                if status == "accepted":
                    accepted_by_df[(a["device_id"], a["field_name"])].append(a)
                else:
                    issues.append(
                        {
                            "severity": "error" if status == "identity_fail" else "warning",
                            "device_id": a["device_id"],
                            "brand": a["brand"],
                            "model": a["model"],
                            "field_name": a["field_name"],
                            "issue": status,
                            "notes": notes,
                            "source_url": a.get("url"),
                        }
                    )

            # Build resolutions per device × field
            resolved_rows: List[Dict[str, Any]] = []
            coverage: List[Dict[str, Any]] = []
            review_queue: List[Dict[str, Any]] = []

            for device in devices:
                did = device["device_id"]
                locked = load_locked_fields(did)
                missing: List[str] = []
                filled = 0
                for fdef in schema.fields:
                    fname = fdef.name
                    # Identity columns from device row
                    if fname in identity_names:
                        if fname == "品牌":
                            display = device["brand"]
                            policy, ids, conflict = "identity", [], False
                        elif fname == "机型":
                            display = device["model"]
                            policy, ids, conflict = "identity", [], False
                        elif fname == "发布时间":
                            display = device.get("release_date") or ""
                            # Prefer accepted assertion if present
                            acc = accepted_by_df.get((did, fname), [])
                            if acc:
                                display, policy, ids, conflict = resolve_field(
                                    acc, conflict_policy=fdef.conflict_policy
                                )
                            else:
                                policy, ids, conflict = "identity", [], False
                        else:
                            display, policy, ids, conflict = "", "missing", [], False
                        if fname in locked:
                            display = locked[fname]
                            policy, conflict = "locked", False
                            ids = []
                        upsert_resolution(
                            conn,
                            device_id=did,
                            field_name=fname,
                            display_text=display or "",
                            policy=policy,
                            assertion_ids=ids,
                            conflict=conflict,
                            run_id=ctx.run_id,
                            locked=fname in locked,
                            locked_value=locked.get(fname),
                        )
                        resolved_rows.append(
                            {
                                "device_id": did,
                                "brand": device["brand"],
                                "model": device["model"],
                                "field_name": fname,
                                "display_text": display or "",
                                "policy": policy,
                                "conflict": conflict,
                            }
                        )
                        if display:
                            filled += 1
                        elif fdef.required:
                            missing.append(fname)
                        continue

                    if fname in locked:
                        display = locked[fname]
                        upsert_resolution(
                            conn,
                            device_id=did,
                            field_name=fname,
                            display_text=display,
                            policy="locked",
                            assertion_ids=[],
                            conflict=False,
                            run_id=ctx.run_id,
                            locked=True,
                            locked_value=display,
                        )
                        resolved_rows.append(
                            {
                                "device_id": did,
                                "brand": device["brand"],
                                "model": device["model"],
                                "field_name": fname,
                                "display_text": display,
                                "policy": "locked",
                                "conflict": False,
                            }
                        )
                        filled += 1
                        continue

                    acc = accepted_by_df.get((did, fname), [])
                    display, policy, ids, conflict = resolve_field(
                        acc, conflict_policy=fdef.conflict_policy
                    )
                    upsert_resolution(
                        conn,
                        device_id=did,
                        field_name=fname,
                        display_text=display,
                        policy=policy if display else "missing",
                        assertion_ids=ids,
                        conflict=conflict,
                        run_id=ctx.run_id,
                    )
                    resolved_rows.append(
                        {
                            "device_id": did,
                            "brand": device["brand"],
                            "model": device["model"],
                            "field_name": fname,
                            "display_text": display,
                            "policy": policy if display else "missing",
                            "conflict": conflict,
                            "assertion_ids": ids,
                        }
                    )
                    if display:
                        filled += 1
                        if conflict:
                            review_queue.append(
                                {
                                    "device_id": did,
                                    "brand": device["brand"],
                                    "model": device["model"],
                                    "field_name": fname,
                                    "reason": "conflict",
                                    "display_text": display,
                                }
                            )
                    else:
                        missing.append(fname)

                coverage.append(
                    {
                        "device_id": did,
                        "brand": device["brand"],
                        "model": device["model"],
                        "filled": filled,
                        "total": len(schema.fields),
                        "missing_fields": missing,
                    }
                )
                if missing:
                    review_queue.append(
                        {
                            "device_id": did,
                            "brand": device["brand"],
                            "model": device["model"],
                            "reason": "missing_fields",
                            "missing_fields": missing,
                        }
                    )

        run_dir = Path(ctx.run_dir)
        header = {
            "schema_version": 1,
            "run_id": ctx.run_id,
            "category": ctx.category,
            "schema_fingerprint": ctx.schema_fingerprint or schema.fingerprint,
            "generated_at": utc_now(),
            "input_revision": ctx.input_revision or f"run:{ctx.run_id}",
        }
        paths = {
            "verification.json": verification_rows,
            "resolved.json": resolved_rows,
            "coverage_report.json": coverage,
            "review_queue.json": {"issues": issues, "queue": review_queue},
        }
        artifacts: Dict[str, str] = {}
        for name, payload in paths.items():
            p = run_dir / name
            p.write_text(
                json.dumps({**header, "items": payload} if name != "review_queue.json" else {**header, **payload},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            artifacts[name] = str(p)

        accepted_n = sum(1 for v in verification_rows if v["status"] == "accepted")
        missing_n = sum(len(c["missing_fields"]) for c in coverage)
        console.log(
            f"[verify] accepted={accepted_n}/{len(verification_rows)} "
            f"missing_fields={missing_n}"
        )

        return StageResult(
            stage=self.name,
            status="ok" if resolved_rows else "partial",
            output_revision=f"verify:{ctx.run_id}:r{len(resolved_rows)}",
            metrics={
                "devices": len(devices),
                "assertions": len(assertions),
                "accepted": accepted_n,
                "rejected": len(verification_rows) - accepted_n,
                "resolutions": len(resolved_rows),
                "missing_fields": missing_n,
                "conflicts": sum(1 for r in resolved_rows if r.get("conflict")),
            },
            artifacts=artifacts,
        )
