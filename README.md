# OpenCode SDK for Workshop

This SDK provides OpenCode for AI-assisted coding within a workshop.
The OpenCode binary is sandboxed in the workshop container. Configuration
and application data are persisted between workshop updates.

---

## Reference workshop

A minimal workshop:

```yaml
# workshop.yaml
name: opencode
base: ubuntu@24.04
sdks:
  - name: opencode
    channel: 1.3/stable

actions:
  opencode: opencode "$@"
```

This creates a basic OpenCode environment with an interactive action.

---

## Using the SDK

### Prerequisites, project layout

1. No prerequisite SDKs are required.
2. Place your project files in your project directory. No special layout is
   required; OpenCode works with any codebase.
3. On launch, the SDK configures `PATH` for the `opencode` binary. If VS Code
   is available, the SDK also installs the OpenCode VS Code extension.

### Start a coding session

Once the workshop is ready:

```bash
workshop shell
opencode
```

This opens an interactive OpenCode session inside the workshop.

### Authenticate with OpenCode

OpenCode stores its configuration in `~/.config/opencode` and session data
in `~/.local/share/opencode`. Both directories are persisted between
workshop updates via mount plugs.

To configure API credentials, set the appropriate environment variable
inside the workshop. You can pass it using the `--env` option with
`workshop run` or `workshop exec`.

---

## Plugs (resources this SDK consumes)

### `opencode-data`

- Interface: `mount`
- Workshop target: `/home/workshop/.local/share/opencode`
- Purpose: Persists OpenCode's session data and history between workshop updates.

### `opencode-config`

- Interface: `mount`
- Workshop target: `/home/workshop/.config/opencode`
- Purpose: Preserves OpenCode's configuration and credentials between workshop updates.
  You can also use `workshop remount` to control its contents on the host.
  To mount your existing `~/.config/opencode` settings into the workshop, stop
  the workshop first, remount, then start it again:

  ```bash
  workshop stop <workshop-name>
  workshop remount <workshop-name>/opencode:opencode-config ~/.config/opencode
  workshop start <workshop-name>
  ```

## Slots (resources this SDK provides)

This SDK doesn't define any slots.

---

## Documentation and guidance

- [OpenCode repository](https://github.com/anomalyco/opencode)
- [Workshop documentation](https://canonical-workshop.readthedocs-hosted.com/latest/)

---

## Community and support

- OpenCode community: [OpenCode GitHub Discussions](https://github.com/anomalyco/opencode/discussions)
- Workshop forum:
  [Workshop Discourse](https://discourse.canonical.com/c/engineering/workshops/34)
- Please review our
  [Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct) before
  participating.

---

## Contributions

All contributions, including code, documentation updates, and issue reports,
are welcome!

- See `CONTRIBUTING.md` for guidelines.
- Open issues or pull requests on the official repository.

---

## License and copyright

Copyright 2026 Canonical Ltd.

This program is free software: you can redistribute it and/or modify it under
the terms of the
[GNU Lesser General Public License version 2.1 (LGPLv2.1)](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html)
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.

[OpenCode](https://github.com/anomalyco/opencode) is licensed under
the [MIT License](https://opensource.org/licenses/MIT).
