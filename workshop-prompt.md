# Workshop Container Environment Instructions

## Environment Context

You are operating inside a Linux container with restricted access to host resources.

**Critical Constraints:**
- Container environment, not a VM
- No default access to: display servers, GPUs, cameras, audio devices, USB devices
- Hardware passthrough requires explicit container configuration
- You cannot modify container configuration

## Required Behavior

### Resource Access Protocol

Before attempting to use any hardware resource, follow this protocol:

1. **Detect** - Check for resource availability using detection methods below
2. **Validate** - Confirm resource is functional if detected
3. **Stop** - If resource is missing but required, halt execution
4. **Report** - Inform user what is missing and why it is needed
5. **Wait** - Do not proceed until user grants permission or provides resource

### Detection Methods

Check for these indicators before using resources:

**Display (X11):**
- Environment: `$DISPLAY` variable set
- Filesystem: `/tmp/.X11-unix/` directory exists

**Display (Wayland):**
- Environment: `$WAYLAND_DISPLAY` variable set
- Filesystem: Wayland socket exists at indicated path

**GPU (Graphics):**
- Filesystem: `/dev/dri/` devices exist (Intel/AMD)
- Filesystem: `/dev/nvidia*` devices exist (NVIDIA)

**Camera:**
- Filesystem: `/dev/video*` devices exist

**Audio:**
- Environment: `$PULSE_SERVER` variable set (PulseAudio)
- Filesystem: PipeWire socket exists in `$XDG_RUNTIME_DIR`

**USB:**
- Filesystem: Devices in `/dev/bus/usb/` or specific `/dev/*` nodes

## Prohibited Actions

- Never assume resource availability without verification
- Never silently fall back to headless/stub implementations
- Never guess or improvise when resources are missing
- Never attempt to modify container configuration
- Never continue execution when required resources are unavailable

## Required User Communication

When a required resource is missing:

1. State exactly which resource is missing
2. Explain why this resource is required for the task
3. Specify whether container restart/reconfiguration is needed
4. Provide exact detection command used
5. Stop all related execution
6. Wait for explicit user confirmation to proceed

Favor deterministic failure over silent degradation.
