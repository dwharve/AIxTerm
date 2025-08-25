# Migration Guide

## 0.2.0 (Unreleased) – Unified Socket Service

This release removes the legacy HTTP "server mode" and replaces it with a single
always-on (auto-started) Unix domain socket service located at:

```
~/.aixterm/server.sock
```

The runtime directory (created automatically) now has the following layout (home directory):

```
   ~/.aixterm/
      config        # JSON configuration file
      server.sock   # Unix domain socket for client <-> service IPC
      start.lock    # Transient lock used during auto-start to avoid races
```

### What Changed

| Area | Previous | Now |
|------|----------|-----|
| Service startup | Optional `--server` HTTP mode | Auto-started socket service on demand |
| Transport | HTTP / WebSocket / TCP | Unix domain socket (Linux/macOS) |
| Config location | `~/.aixterm_config.json` | `~/.aixterm/config` |
| Config key | (legacy network/server settings) | Removed |
| Module | `aixterm.server` | Removed |

### Backward Compatibility

Any legacy network/server configuration sections from prior versions are no
longer recognized and should be deleted manually if present.

### Action Required

1. Remove any usage of `--server`, `--host`, `--port` flags in automation scripts.
2. Stop depending on HTTP endpoints – communicate exclusively via the CLI or
   (future) formal tool APIs.
3. If you previously used `~/.aixterm_config.json`, the new file path is
   `~/.aixterm/config`; copy or merge any custom settings.

### Rationale

Unifying on a single local IPC mechanism in a fixed home directory location
simplifies deployment, eliminates duplicated code paths, and reduces surface
area for configuration drift or security misconfiguration.

### Removal Complete

All HTTP "server mode" code paths and related config helpers have been purged.
No additional action is required beyond removing obsolete flags from scripts.

---

For questions or migration issues, please open a GitHub issue with the label
`migration-0.2`.
