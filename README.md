# Omarchy VM Update Channel

This repository is the JoyfulOak release channel for an in-place Omarchy VM
runtime update. `omarchy update` downloads a verified runtime package and then
updates eligible Arch Linux ARM packages in the existing guest. It does not
rebuild the VM image, replace the VM disk, or copy over `/home`.

## Release selection and source pinning

The official upstream repository is [`omacom/omarchy`](https://github.com/omacom/omarchy).
The updater asks GitHub for `/repos/omacom/omarchy/releases/latest` and accepts
only a published, non-prerelease release whose tag is exactly `vX.Y.Z`. It then
requires a JoyfulOak release with the same tag. Version comparisons use Arch's
`vercmp` for package versions and numeric tuples for Omarchy release versions;
a downgrade or malformed version is rejected.

The adapted runtime is built from the official release tag/commit, not from an
un-pinned branch. The current adapted release is Omarchy `v4.0.4`, commit
`c668141e9c42b13c80c9ca4ea108e11708c5e8a5`. Its source tree and VM-specific
inputs are recorded in `/usr/share/try-omarchy/build-spec.json` in the package.
The build specification records the source tree hash, package-lock inputs,
ARM64 package pins, and every compatibility backport with its reference,
preimage/postimage hashes, and patch hash. The channel repository contains the
finished runtime package; source adaptation and package construction occur in
the Omarchy VM build project referenced by the build specification.

VM-specific adaptations are deliberately limited to guest update delivery,
ARM64/VM integration, and compatibility pins. The package retains the required
boot/runtime integration, including the native cursor bridge. Upstream behavior
omitted from this in-place path is settings migration, user hooks, AUR updates,
mise/toolchain updates, orphan removal, and package-cache pruning. Those steps
are not required to preserve this VM's user state and are not run by this
channel's `omarchy update`.

## JoyfulOak release contract

Each published stable release must use the matching upstream tag, for example
`v4.0.4`, and contain exactly these assets:

- `omarchy-vm-update.json`
- `omarchy-runtime-update.pkg.tar.zst`

The manifest is JSON with `schemaVersion: 1`, `omarchyVersion`,
`packageName: "try-omarchy-runtime"`, `packageVersion` (`X.Y.Z-N`),
`architecture` (`any` or `aarch64`), and `runtimeAsset`. GitHub's Releases API
must expose a `sha256:<64 lowercase hex>` digest and positive size for both
assets. The guest validates release state, tag, asset names, URLs, sizes,
digests, manifest contents, package identity, package version, and ARM64
compatibility before `pacman -U`.

The manifest is downloaded and checked first. A malformed manifest, missing
asset, unsupported architecture, redirect to an untrusted host, checksum
mismatch, package inspection failure, or package-install failure aborts the
update before the Arch package transaction. A matching current release is a
safe no-op after the manifest has been verified. Temporary downloads are
removed automatically.

## What changes and what is preserved

The runtime package updates `/usr/share/omarchy`, the guest-owned update
helpers, and other package-owned runtime paths. The subsequent Arch transaction
uses the guest's configured Arch Linux ARM repositories and existing package
policy. It does not remove packages, update AUR packages, run migrations or
hooks, update mise toolchains, remove orphans, or prune caches.

`/home`, personal documents, user configuration, application profiles, and
installed applications are not copied or deleted by the updater. Arch packages
already installed may receive normal repository upgrades, so application
binaries managed by pacman can change while their home-directory data remains.
The VM's host-managed direct-boot kernel and graphics ABI packages remain held
until a coordinated host update; the build specification records the pinned
`aquamarine`, `hyprtoolkit`, and Hyprland compatibility set. The exact holds
and repository policy are in the guest's `pacman.aarch64.conf` and package
inputs used by the build, not inferred from the release tag.

## Build, install, and publish

From the Omarchy VM build-project checkout:

```sh
# Update the pinned upstream tag/commit, reviewed VM patches, and package locks.
# Then build only the guest runtime package and manifest:
make guest-runtime-update
```

Review the generated package, manifest, source revision, patch hashes, package
locks, and ARM64 holds. Test the package in a disposable VM before publishing.
Do not rebuild the factory image for this channel update.

With GitHub CLI authentication available, publish a stable release and verify
it is not a draft or prerelease:

```sh
gh release create vX.Y.Z \
  dist/guest/omarchy-runtime-update.pkg.tar.zst \
  dist/guest/omarchy-vm-update.json \
  --title "Omarchy VM runtime vX.Y.Z" \
  --notes-file RELEASE_NOTES.md

gh release view vX.Y.Z --repo JoyfulOak/omarchy-vm-update
```

Use the exact two asset filenames. Publishing credentials are not required to
build or test locally; if unavailable, leave the generated artifacts prepared
for an authorized publisher and do not claim publication.

For an already bootstrapped guest, run:

```sh
omarchy update
```

The command logs to `/tmp/omarchy-update.log` and uses the normal Omarchy update
lock and free-space check. `-y` enables unattended confirmation. A runtime
verification failure stops before the Arch package transaction; a pacman
failure leaves its error in the log and must be diagnosed before retrying.

## Recovery and inspection

```sh
less /tmp/omarchy-update.log
pacman -Q try-omarchy-runtime
omarchy debug
pacman -Q aquamarine hyprland hyprtoolkit linux-aarch64 linux-aarch64-headers
pacman -Qu
```

Retry only after correcting the reported release, manifest, network, checksum,
package, repository, or disk-space problem. Do not bypass verification with an
untrusted package or force-install a held graphics/kernel package. A failed
runtime download is safe to retry because it is staged in a temporary directory and no `/home` content is modified.

## Current channel state

The repository's verified published release is Omarchy `v4.0.4`; the checked-in
manifest identifies runtime package `try-omarchy-runtime` version `4.0.4-6`.
The local untracked `omarchy-vm-update.json`, if present, is preserved as a
working-tree change and is not part of the source edits made by this update.
