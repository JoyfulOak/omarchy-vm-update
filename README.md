# Omarchy VM Update Channel

This repository is the release channel for the JoyfulOak Omarchy VM guest
runtime. Inside the VM, `omarchy update` checks this repository for the latest
stable release and applies its runtime package in place. It does not rebuild or
replace the VM disk.

## Update sources

- **JoyfulOak Omarchy runtime:** this repository's stable GitHub Releases. The
  release tag follows the Omarchy version, for example `v4.0.4`. The guest does
  not query Basecamp Omarchy's release API or package servers.
- **Arch operating system packages:** Arch Linux ARM repositories configured
  in the guest. A full Arch upgrade is required to keep package dependencies
  consistent. Repository-installed applications may be upgraded along with OS
  packages; their files in the user's home directory and their settings are
  preserved.
- **VM kernel and graphics ABI holds:** remain pinned until a coordinated
  host-managed update is available. The Mac launcher and its saved boot kit are
  outside this in-guest update path.

The updater skips Omarchy settings migrations, user hooks, AUR package updates,
mise toolchain updates, and automatic orphan removal. It does not write to
`/home`. The update stops before the Arch package transaction if JoyfulOak's
release metadata or runtime package cannot be verified.

## Release assets and checks

Every stable release must contain exactly these two assets:

1. `omarchy-vm-update.json`, generated from the runtime package. It declares
   the Omarchy version, package name and version, architecture, and payload
   filename.
2. `omarchy-runtime-update.pkg.tar.zst`, the `try-omarchy-runtime` package.

The guest gets the SHA-256 digest and size of each asset from GitHub's Releases
API, downloads the manifest first, and downloads the package only when its
version is newer than the installed version. Before installation it verifies
the manifest digest, package digest, tag/version match, package identity, and
ARM64 compatibility.

## Publishing

From the Omarchy VM project checkout:

1. Update the pinned Omarchy source, reviewed compatibility backports, and
   package lock for the release being adopted.
2. Set `guest/spec.json`'s Omarchy release and runtime package release number.
   The package version must be `X.Y.Z-N` for release tag `vX.Y.Z`.
3. Run `make guest-runtime-update`. This builds the runtime package and
   matching manifest without rebuilding the factory VM image.
4. Test the package and `omarchy update` in a disposable VM.
5. Create or update the stable release in this repository using the matching
   Omarchy version tag, such as `v4.0.5`. Upload both generated assets with
   their exact filenames. GitHub must expose SHA-256 digests for them.
6. Confirm the release is published, not a draft or prerelease.

The current release targets Omarchy `v4.0.4`, package version `4.0.4-6`, and
prints `JoyfulOak Edition` in the guest's `omarchy-version` output. Existing
VMs with runtime `4.0.4-5` need to install this package once to switch to
JoyfulOak-owned release discovery. After that bootstrap, subsequent runtime
updates are delivered by `omarchy update`.
