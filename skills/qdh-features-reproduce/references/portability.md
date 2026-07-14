# Portability and installation

The orchestrator has no runtime dependency on an external development workspace, a user name, an agent home, or a fixed qdh drive. `--qdh-root`, `--run-root` and `--ch-url` are explicit. `<skill-root>` always means the directory containing the `SKILL.md` currently loaded by the executing agent.

All five skills form one versioned distribution unit. A multi-agent skill manager must enable or disable the complete set for each target agent and preserve the package bytes. The agent-specific installed copy is runtime input; the manager's storage location is not a runtime convention.

By default the orchestrator locates all formula skills as siblings of its own installed directory. For a nonstandard installation, set the absolute environment variable `QDH_FEATURE_SKILLS_ROOT` to the directory containing all five skill folders.

Required sibling folder names:

- `wh6-factor-reproduce`
- `indicator-py-factor-reproduce`
- `excel-factor-reproduce`
- `tv-factor-reproduce`
- `qdh-features-reproduce`

Discovery requires the complete sibling set and verifies every locked artifact by SHA256 before importing it. It does not scan the machine or infer an installation root from the current working directory.

The numerical runtime contract is exact: Python 3.10.20, NumPy 2.2.6, pandas 2.3.3 and PyArrow 23.0.1 with Snappy support. Requests, Windows `msvcrt`, a reachable read-only ClickHouse HTTP endpoint, and enough same-volume free space are also required. The interpreter is selected explicitly by the executing agent; no machine-specific interpreter path belongs in the package.

The orchestration CLI is Windows-only because build, validation and publishing share the same `msvcrt` run-lock implementation and Windows drive-anchor safety checks. Formula cores are pure Python, but this orchestration CLI is not cross-platform.

Skill directories are read-only at runtime. Every agent receives a unique external run root. One operator owns a run root from build through READY. Different runs may execute concurrently within CPU, memory, ClickHouse and disk-I/O limits. Production publishing is serialized by the qdh publish lock and must have one operator.
