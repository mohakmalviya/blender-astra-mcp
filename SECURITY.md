# Security

This add-on is a local editor-control service. Use it on a trusted workstation and keep source control
or checkpoints for valuable scenes. It is not an OS sandbox.

- Loopback binding and a per-start random bearer-equivalent secret are required. Every socket method
  checks the secret before dispatch. There are no browser HTTP/CORS endpoints.
- The descriptor is a credential. It lives in the user's local application state, not the repository.
  On Unix it is created with mode 0600; on Windows protection relies on the parent profile's inherited
  ACLs. Same-user processes can read it. Do not sync or share the state directory.
- **Write**, **render**, **delete** and **save** permissions are enforced in Blender. Only write and
  render default on. Stop and restart to change them. A client cannot grant itself permissions.
- Deletion also needs `confirm: true`. This is an explicit intent flag, not proof of human approval;
  the AI client's approval policy remains responsible for human confirmation.
- There is no arbitrary Python, shell, file-read, network-fetch, plugin-install or unrestricted property
  setter endpoint. Those are deliberate v0.1 omissions.
- Save/capture accept basenames under a fixed output directory, and existing files are refused.
  This is not a defense against a malicious same-user process racing the filesystem.
- Managed-object tagging is not a sandbox. Inspect can expose object names and positions to the AI;
  capture sends a rendered scene image. Your AI provider still processes the data your client sends.
- Render is blocking and cannot be remotely cancelled mid-call. Disconnect is not rollback. Timeouts
  explicitly report an unknown outcome and never automatically replay mutations.
- Assets already present in a `.blend` are trusted Blender content. This project does not make an
  untrusted Blender file safe to open or neutralize other installed add-ons.

The project itself has no telemetry. Test logs, descriptors, local paths and exports are excluded from
normal source commits. When reporting a bug, redact credentials and proprietary scene information.
