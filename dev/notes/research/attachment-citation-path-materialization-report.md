# Attachment / citation path materialization across the WSL2 <-> Windows filesystem boundary

Prepared: 2026-07-02

## 1. **Restated question**

The implementation question is: when an operator attaches a file, or when a WSL2-hosted Claude Code agent cites a file, where should awl-cc-dash place the durable byte-file, and what path should be delivered to each receiver so that the Windows Electron renderer and the WSL2 agent both open the same underlying bytes?

This is not a chip/UI/upload-widget problem. It is a storage and path-materialization problem across three process views: Windows sidecar, Windows renderer, and WSL2 agent. The greenfield target is `<project>/.awl-cc-dash/assets/`, while the current implementation does not yet have that assets directory or media/document write-back path. [confirmed, prompt-provided]

The answer must cover both project-root cases:

- Project on a Windows drive: Windows sees `C:\...`; WSL sees `/mnt/c/...`. [confirmed, prompt-provided; S1]
- Project on the WSL-native filesystem: WSL sees `/home/...`; Windows sees a UNC path such as `\\wsl.localhost\Ubuntu\home\...` or `\\wsl$\Ubuntu\home\...`. [confirmed, prompt-provided; S1; S6]

## 2. **Options considered**

### Option A - Project-relative asset catalog; copy bytes into `<project>/.awl-cc-dash/assets/`; rewrite per receiver. Recommended.

Concrete shape:

```text
<project>/.awl-cc-dash/
  assets/
    <asset-id>/
      <safe-original-name-or-content-name>
  state/
    assets.json or asset rows in sidecar state
```

Store asset state as project-relative data, not as a Windows-absolute or WSL-absolute path:

```json
{
  "id": "01J...",
  "rel_path": "assets/01J.../screenshot.png",
  "original_name": "screenshot.png",
  "sha256": "...",
  "size_bytes": 123456,
  "mime": "image/png",
  "created_from": {
    "side": "operator|agent",
    "original_path_for_audit_only": "..."
  }
}
```

At project-open time, compute a `ProjectPathContext` with both receiver-specific roots:

```json
{
  "kind": "windows_drive|wsl_native",
  "distro": "Ubuntu",                    // required for wsl_native
  "project_root_windows": "C:\\repo"     // or \\wsl.localhost\Ubuntu\home\user\repo
  "project_root_wsl": "/mnt/c/repo"       // or /home/user/repo
}
```

Then materialize paths by joining the receiver root with the stored relative path:

```text
agent path    = <project_root_wsl>/ .awl-cc-dash / <rel_path>
renderer path = <project_root_windows>/ .awl-cc-dash / <rel_path>
```

For a Windows-drive project, this yields `C:\...\.awl-cc-dash\assets\...` for the renderer and `/mnt/c/.../.awl-cc-dash/assets/...` for the agent. [confirmed for `/mnt` shape; S1; S3]

For a WSL-native project, this yields `\\wsl.localhost\<Distro>\home\...\.awl-cc-dash\assets\...` for the renderer and `/home/.../.awl-cc-dash/assets/...` for the agent. [confirmed that Windows apps can access WSL files through `\\wsl$\<distro>` and that `\\wsl.localhost` is the modern prefix; S1; S6] The exact behavior of `wslpath -w /home/...` across all distro/path edge cases should be spike-tested; manual UNC construction from a known distro plus canonical WSL path is the deterministic fallback. [speculative; needs live spike]

Why it fits the problem:

- It satisfies the intended assets home inside the project. [confirmed, prompt-provided]
- It makes every attachment/citation a project-owned file instead of a dangling pointer to a user-local original. [plausible]
- It avoids storing receiver-specific absolute paths in durable state. [plausible]
- It supports both `/mnt/<drive>` and WSL-native projects if the project-root resolver knows which side owns the root. [plausible; requires implementation/spike]
- It aligns with Claude Code accepting file and image paths in prompts, including absolute paths. [confirmed; S8; S9]

### Option B - Store canonical Windows-absolute paths and translate to WSL paths when needed.

Concrete shape: store `C:\...\.awl-cc-dash\assets\foo.png` in state, and convert to `/mnt/c/.../.awl-cc-dash/assets/foo.png` for the agent.

This is attractive because the sidecar and renderer are Windows processes. It is already compatible with the known mount-only translation primitive for projects on Windows drives. [confirmed, prompt-provided; S1]

It breaks down for WSL-native projects because the Windows path is a UNC path, not a drive path. A WSL agent cannot open `\\wsl.localhost\Ubuntu\home\...` as a Linux path; it needs `/home/...`. [confirmed for distinct path shapes; S1; S6] Translating a UNC path back to the correct distro and Linux path is possible only if the sidecar explicitly records or infers the distro and validates the WSL path. [plausible; needs live spike]

### Option C - Store canonical WSL-absolute paths and translate to Windows paths when needed.

Concrete shape: store `/mnt/c/.../.awl-cc-dash/assets/foo.png` or `/home/user/proj/.awl-cc-dash/assets/foo.png` in state, and convert to `C:\...` or `\\wsl.localhost\Ubuntu\...` for the renderer.

This is attractive because the primary coding agents run in WSL and Claude Code can be given WSL-shaped absolute paths. [confirmed for Claude Code path references; S8; S9]

It is weaker as durable state because a WSL absolute path embeds the project root and distro assumptions. Moving the project or changing distro identity makes the stored path stale. [plausible] It also requires Windows path materialization for renderer display; for WSL-native paths this needs distro identity and UNC handling, not just `/mnt/<drive>` translation. [confirmed for distinct path forms; S1; S6]

### Option D - Reference the original file in place; do not copy into project assets.

Concrete shape: store the path from the upload/citation event as `source_path`, then rewrite it per receiver when needed.

This avoids disk duplication. [confirmed by design] It is the least reliable option. The original file can be deleted, moved, edited, permission-blocked, locked, or invisible to the other side of the boundary. [plausible] It also fails the target project data model because attachments/citations do not live in `<project>/.awl-cc-dash/assets/`. [confirmed, prompt-provided]

For an operator attachment selected from a Windows-only location, a WSL agent may not have a stable path unless the location is under a mounted drive. [confirmed for `/mnt` drive model; S1; S3] For an agent citation from `/home/...`, the renderer needs UNC materialization and may not be able to re-open the original if permissions, distro availability, or path lifetime changes. [plausible; needs spike]

### Option E - Dual-copy/mirror cache: one Windows copy plus one WSL copy.

Concrete shape: copy each asset to a Windows-side cache for renderer use and to a WSL-side cache for agent use, with content hashes linking the two copies.

This can optimize per-side performance and avoid frequent cross-boundary reads. [plausible] It does not satisfy the “same referenced byte-file” requirement unless the mirror is explicitly treated as a derived cache of an immutable canonical object. [plausible] It adds synchronization, garbage collection, and race/coherency logic. [plausible] It should be a later performance optimization, not the first correctness layer.

### Option F - Display-only fallback.

Concrete shape: store the chip metadata and maybe a preview, but do not provide the agent with an openable path.

This is the honest fallback when the sidecar cannot prove a durable cross-boundary storage/path mapping. It preserves UI state without pretending the agent can open a file. [confirmed by prompt constraint]

## 3. **Trade-offs**

### Canonical stored form

Recommendation: store a project-relative asset path plus metadata. Do not store the Windows path or WSL path as the canonical asset locator. [plausible]

Reasoning:

- Windows-absolute canonical state is convenient for the sidecar/renderer but does not naturally address WSL-native projects. [confirmed for path-shape mismatch; S1; S6]
- WSL-absolute canonical state is convenient for agents but embeds distro/root assumptions and still needs Windows materialization for the renderer. [plausible]
- Project-relative canonical state preserves the invariant “asset belongs to this project’s `.awl-cc-dash` data directory”; absolute paths become per-receiver renderings. [plausible]

Implementation cost: introduce `ProjectPathContext`, path joining, canonicalization, validation, and asset metadata. [plausible; requires repo implementation]

Verification needed before relying on it: path resolver behavior for WSL-native project roots, especially UNC parsing, distro names with unusual characters, spaces/unicode in paths, and `wslpath -w` output. [speculative; needs live spike]

### Copy vs reference

Recommendation: copy attached/cited files into `<project>/.awl-cc-dash/assets/` and treat assets as immutable. [plausible]

Why copy:

- Copying makes the file durable, project-owned, hashable, and portable with the project data folder. [plausible]
- Copying avoids dangling references when the operator deletes or moves an original attachment. [plausible]
- Copying normalizes agent citations: a cited output file becomes an asset record before the renderer is asked to open it. [plausible]

Cost: extra disk usage, ingestion time, cleanup/GC policy, and possible duplicate copies. [plausible]

Mitigation: hash by `sha256`, deduplicate later if needed, keep `original_path_for_audit_only` but never use it as the resolver’s source of truth. [plausible]

### Access performance and reliability

Microsoft’s WSL guidance says to avoid working across operating systems with files unless there is a specific reason; for fastest performance, use the WSL filesystem for Linux command-line tools and the Windows filesystem for Windows tools. Cross-OS access can significantly slow performance. [confirmed; S1; S2]

Implications:

- For a project on `C:\...`, the agent will read assets through `/mnt/c/...`. That is supported, but it is a Windows filesystem mounted into WSL through DrvFs, and it may be slower or have permission/case quirks compared with WSL-native storage. [confirmed for DrvFs `/mnt`; S1; S3; S4]
- For a project on `/home/...`, the agent reads native WSL files, which is the right side for Linux tooling. The renderer reads through `\\wsl.localhost\<Distro>\...` or `\\wsl$\<Distro>\...`, which is supported for Windows apps but should be treated as a cross-boundary read path, not as a high-churn working directory for Windows tools. [confirmed for UNC access and performance principle; S1; S2; S6]
- Exact throughput depends on file size, file count, antivirus/indexing, WSL version, and Windows build; benchmark the dashboard’s expected image/PDF/media workloads before adding mirror caches. [speculative; needs benchmark]

### Boundary pitfalls

Symlinks. Do not store assets as symlinks. Ingest should resolve the selected/cited path to a regular file, copy the bytes, and reject or explicitly follow symlinks according to a security policy. [plausible] WSL/DrvFs symlink behavior has special handling and historical constraints; WSL release notes describe DrvFs creating NT symlinks only under certain conditions and otherwise creating WSL symlinks. [confirmed; S6]

Case sensitivity. Use asset IDs and lowercase generated filenames; never allow two asset records that differ only by case. Linux filesystems are case-sensitive by default, while Windows is generally case-insensitive unless a per-directory flag is set. [confirmed; S1; S5]

Permissions and ownership. For Windows-drive assets, WSL sees permissions through DrvFs; WSL permissions for Windows files are calculated from Windows ACLs or WSL metadata, and metadata is not enabled by default. [confirmed; S4] For WSL-native assets, prefer writing via `wsl.exe -d <Distro> -- sh -c 'cat > tmp && mv tmp final'` as the target WSL user, then set `chmod` as needed, rather than relying on Windows UNC writes for important asset creation. [plausible; needs live spike]

Line endings and binary integrity. Treat every asset as binary. Never pass attachment bytes through tmux keystrokes or text-mode transformations. Use byte streams, write temp files, rename into place, and verify `sha256` after write. [plausible] This aligns with the existing bridge primitive that can stream bytes to WSL with `cat > file` to avoid Windows command-line argument limits. [confirmed, prompt-provided] The underlying Windows `CreateProcess` command line limit is 32,767 characters, so large payloads should not be passed as arguments. [confirmed; S7]

File locking and concurrent readers. Do not rely on cross-boundary lock semantics for correctness. Make assets immutable after publication; write `*.tmp`, flush enough for the chosen filesystem, then rename/move to the final path. Readers should open only final asset paths. [plausible; needs spike for exact Windows/WSL behavior]

Path length and unsafe characters. Generated asset directory names should be short IDs, not original long paths. Preserve original names only as display metadata or a sanitized leaf filename. This reduces Windows path-length and quoting issues. [plausible; S10]

### Writer/reader direction

Operator attachment: Windows sidecar writes, WSL agent reads.

- Windows-drive project: sidecar copies bytes into `C:\...\.awl-cc-dash\assets\...` using binary Windows file I/O; agent receives `/mnt/c/.../.awl-cc-dash/assets/...`. [confirmed for path shape; S1]
- WSL-native project: sidecar streams bytes into WSL using `wsl.exe -d <Distro> -- sh -c 'mkdir -p ...; cat > tmp; mv tmp final; chmod 0644 final'`; renderer receives the corresponding UNC path. [plausible; uses documented WSL command interop and UNC access; S1; S6]

Agent citation: WSL agent writes or points to a file; Windows renderer reads.

- Agent-provided path is canonicalized inside the agent’s distro with `realpath -e`, checked as a regular file, size-limited, and copied into assets. [plausible; requires implementation]
- If the cited path is already inside `.awl-cc-dash/assets/`, record it by relative path after validation. [plausible]
- If it is outside assets, copy it into assets first; do not store the original agent path as the renderer-openable target. [plausible]
- After copy, renderer receives `C:\...` for Windows-drive projects or `\\wsl.localhost\<Distro>\...` for WSL-native projects. [confirmed for path shapes; S1; S6]

## 4. **Per-finding confidence**

| ID | Finding | Confidence |
|---|---|---|
| F1 | Windows-drive files appear in WSL under mounted paths such as `/mnt/c/...`; WSL-native files are visible to Windows through WSL UNC paths such as `\\wsl$\<Distro>\...`, with `\\wsl.localhost` also supported. | confirmed [S1; S3; S6] |
| F2 | Microsoft recommends storing files on the same OS filesystem as the tools doing the work; cross-OS filesystem access can significantly slow performance. | confirmed [S1; S2] |
| F3 | `wsl.exe <command>` can run Linux binaries from Windows, and the Linux command must receive WSL-format paths. | confirmed [S1] |
| F4 | `wslpath` exists for WSL-to-Windows and Windows-to-WSL path conversion. | confirmed [S6] |
| F5 | Claude Code supports file/directory references with `@`, supports relative or absolute file paths, and can analyze images when given an image path. | confirmed [S8; S9] |
| F6 | WSL permissions for files on Windows drives are calculated from Windows permissions or WSL metadata, and metadata is not enabled by default. | confirmed [S4] |
| F7 | Linux/WSL filesystems are case-sensitive by default; Windows is generally case-insensitive unless configured per directory. | confirmed [S1; S5] |
| F8 | Symlink behavior across WSL/DrvFs is a boundary hazard; DrvFs symlink creation has special conditions. | confirmed for documented special handling; broader policy recommendation is plausible [S6] |
| F9 | The strongest canonical stored form for awl-cc-dash assets is project-relative `assets/...` plus metadata, with per-receiver path rendering. | plausible; design inference needing repo implementation |
| F10 | Copying attachments/citations into project assets is preferable to referencing originals in place because it gives durability, stable hashes, and one project-owned byte-file. | plausible; design inference |
| F11 | For WSL-native projects, using a WSL-side `cat > tmp; mv final` write path is more reliable than treating UNC writes from Windows as the primary write mechanism. | plausible; needs live spike |
| F12 | `wslpath -w /home/...` may be usable for WSL-native Windows path materialization, but output and edge cases should be tested before relying on it. | speculative; needs live spike |
| F13 | Electron/Chromium may need either a Windows/UNC file path or a sidecar-served asset URL depending on security policy; this does not change the canonical asset storage recommendation. | speculative; needs Electron integration spike |
| F14 | Immutable assets plus temp-file/rename publication is safer than cross-boundary file locking for concurrent sidecar/renderer/agent access. | plausible; needs live spike for exact lock behavior |

## 5. **Sources & citations**

- [S1] Microsoft Learn, “Working across Windows and Linux file systems.” https://learn.microsoft.com/en-us/windows/wsl/filesystems
  - Relevant points: Microsoft recommends avoiding cross-OS file work unless needed; WSL uses `/mnt/...` for mounted Windows drives; `\\wsl$` exposes WSL distributions to Windows File Explorer; `wsl.exe` commands need WSL-format paths; Windows and Linux differ in case-sensitivity.
- [S2] Microsoft Learn, “Set up a WSL development environment.” https://learn.microsoft.com/en-us/windows/wsl/setup/environment
  - Relevant points: Store project files on the same operating system as the tools; WSL project examples use `\\wsl$\<DistroName>\home\...`; cross-OS access can significantly slow performance.
- [S3] Microsoft Learn, “Advanced settings configuration in WSL.” https://learn.microsoft.com/en-us/windows/wsl/wsl-config
  - Relevant points: DrvFs mounts fixed Windows drives under `/mnt` by default; automount root and options; metadata/case-related mount options.
- [S4] Microsoft Learn, “File Permissions for WSL.” https://learn.microsoft.com/en-us/windows/wsl/file-permissions
  - Relevant points: permissions for Windows-drive files accessed from WSL are calculated from Windows permissions or WSL metadata; metadata is not enabled by default; DrvFS `/mnt/c` scenarios.
- [S5] Microsoft Learn, “Case Sensitivity.” https://learn.microsoft.com/en-us/windows/wsl/case-sensitivity
  - Relevant points: Linux/WSL filesystem directories are case-sensitive by default; Windows directories are generally case-insensitive unless configured; Windows tools may break in case-sensitive directories.
- [S6] Microsoft Learn, “Release Notes for Windows Subsystem for Linux.” https://learn.microsoft.com/en-us/windows/wsl/release-notes
  - Relevant points: Windows can access Linux files in a WSL distro through `\\wsl$\<distro_name>`; `\\wsl.localhost` prefix; `wslpath` usage; DrvFs symlink behavior; historical `\\wsl$` fixes.
- [S7] Microsoft Learn, “CreateProcessA function.” https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessa
  - Relevant point: Windows command-line string maximum is 32,767 characters, including the terminating null.
- [S8] Anthropic Claude Code Docs, “Common workflows.” https://code.claude.com/docs/en/common-workflows
  - Relevant points: Claude Code can analyze an image when given an image path; `@` references can include files/directories; file paths can be relative or absolute.
- [S9] Anthropic Claude Code Docs, “Use Claude Code in VS Code.” https://code.claude.com/docs/en/ide-integrations
  - Relevant points: `@` mentions give Claude context about files/folders; drag-and-drop attachments exist; selected files can be referenced with paths.
- [S10] Microsoft Learn, “Maximum Path Length Limitation.” https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
  - Relevant point: classic Windows API paths have `MAX_PATH` limitations unless long-path handling is enabled/used; generated short asset paths reduce exposure.

## 6. **Recommendation + fallback**

Recommended implementation path:

1. Build `ProjectPathContext` before enabling agent-openable attachments.
   - For Windows-drive roots, keep the existing `/mnt/<drive>` translation, but add canonicalization and validation. [plausible]
   - For WSL-native roots, require distro identity plus canonical WSL root. Parse `\\wsl.localhost\<Distro>\...` / `\\wsl$\<Distro>\...` to a candidate WSL path, validate with `wsl.exe -d <Distro> -- realpath -e`, and derive the Windows UNC root from the validated WSL path. [plausible; needs live spike]

2. Build an asset catalog under `<project>/.awl-cc-dash/assets/`.
   - Store `rel_path`, `sha256`, size, MIME, original display name, and provenance. [plausible]
   - Do not store receiver-specific absolute paths as canonical state. [plausible]
   - Use short generated IDs and sanitized filenames. [plausible]

3. Ingest operator attachments by copying bytes into assets.
   - If project is on a Windows drive, write through Windows binary file I/O to the Windows project path; deliver the WSL `/mnt/<drive>/...` path to the agent. [plausible; path shape confirmed]
   - If project is WSL-native, stream bytes through `wsl.exe -d <Distro> -- sh -c 'cat > tmp; mv tmp final'` into the WSL asset path; deliver the UNC path to the renderer. [plausible; needs spike]
   - Hash after write and compare recorded size/hash. [plausible]

4. Ingest agent citations by copying cited files into assets before renderer use.
   - Canonicalize the agent path inside WSL.
   - Reject directories, devices, sockets, pipes, broken symlinks, unreadable files, and over-limit files.
   - If already under assets, record the relative asset path; otherwise copy into assets and then emit the canonical asset record. [plausible]

5. Deliver paths only as receiver-specific renderings.
   - Agent prompt/TUI text should include the absolute WSL path, optionally as a Claude Code `@/abs/path` reference for text/code files or as “Analyze this image: /abs/path” for images. [confirmed Claude Code supports these patterns; S8; S9]
   - Renderer should receive a Windows absolute path or UNC path derived from the same relative asset record. If Electron security policy makes direct `file://`/UNC loading unreliable, serve the file from the Windows sidecar over an authenticated local HTTP endpoint while keeping the same asset record as the source of truth. [speculative; needs Electron spike]

6. Add focused acceptance tests before considering the feature complete.
   - Project on `C:\...` with agent path `/mnt/c/...`.
   - Project on `/home/...` opened from Windows as `\\wsl.localhost\Ubuntu\home\...`.
   - Filenames with spaces, unicode, `#`, `%`, quotes, and long names.
   - Case-only collisions: `Foo.png` and `foo.png`.
   - Symlink source files and symlinks inside assets.
   - Binary integrity: PNG/PDF/ZIP hash before and after materialization.
   - Large file path through stdin streaming, not command-line args.
   - Agent citation inside project, outside project, and already inside assets.
   - Renderer open from Windows-drive path and WSL UNC path.

Honest fallback:

If the project root cannot be resolved into both a validated WSL absolute root and a validated Windows absolute/UNC root, or if the sidecar cannot write the asset bytes into the project-owned assets directory and verify the hash, the attachment/citation must remain a display-only chip. Do not send an agent-openable path. The chip can show name, size, MIME, and “not materialized for WSL agent” status, but it should not imply the WSL agent can open the file. [confirmed by prompt constraint; implementation policy is plausible]
