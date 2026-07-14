# Safety policy

- `selftest` and `preflight` are read-only.
- `build`, `validate` and `finalize` may write only below an explicit absolute run root outside qdh and on the same volume.
- The run root may not equal, contain or be contained by qdh. Reparse points and symlinks are rejected.
- CH access enforces `readonly=2`; secrets are redacted from persisted evidence.
- A filtered pilot is permanently non-publishable.
- READY is immutable and is written last.
- Publish defaults to dry-run and requires exact run id plus READY SHA256 for execution.
- Publish changes only the `features` directory. qdh meta remains untouched by policy.
- The pre-publish live tree is renamed into run-private quarantine and retained. It is never automatically deleted.
- A transaction journal supports commit-forward or rollback after a crash. No recursive delete is part of publishing or recovery.
- Market, warmup and source identity are checked before READY, before publish, under the publish lock, and after the candidate becomes live.
- Directory exchange uses two same-volume renames. This is crash recoverable, but a direct reader that ignores the external publish lock can observe the short interval between renames. Coordinate a maintenance window for such readers.
- Metadata is outside the publish scope and is never modified without separate user authorization and a separate governance workflow.
- Skill packages are read-only runtime inputs. Staging, logs, locks and temporary files belong only in the explicit external run root.
- Each agent must use a unique run root. The run lock rejects a second process for the same run, and a run has one operator through READY and recovery.
- Separate runs may build concurrently only within declared resource limits. A global qdh publish lock serializes live verification, switching and recovery across all agents.
