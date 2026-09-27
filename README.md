# Omarchy VM Update Channel

This repository distributes the Try Omarchy guest integration package for the
existing Omarchy VM. It lets `omarchy update` refresh the Omarchy runtime and
then run Omarchy's normal Arch package update in place, without rebuilding the
VM image or replacing its disk.

## How version selection works

The guest checks the latest stable release in [`omacom/omarchy`](https://github.com/omacom/omarchy/releases).
It then looks for a release with the exact same tag in this repository. For
example, upstream `v4.0.5` must have a matching `v4.0.5` release here. The
matching release must contain exactly one asset named
`omarchy-runtime-update.pkg.tar.zst`.

Before installation, the guest checks GitHub's SHA-256 asset digest, package
identity, architecture, Omarchy version, and Arch package version ordering. A
runtime package for a lower or mismatched Omarchy version is rejected. If the
matching release or asset cannot be verified, the update stops before the Arch
package transaction. Publish this release only after the package has been
built and checked against that Omarchy release.

The runtime package is installed first. `omarchy update` then refreshes
signing keys and updates eligible packages from the configured Arch Linux ARM
repositories. It does not run Omarchy settings migrations or user hooks, update
AUR packages or mise toolchains, or remove orphan packages. It leaves `/home`
untouched. Pacman still upgrades installed packages from Arch repositories,
including personal applications installed through pacman; Arch does not support
a safe partial system upgrade. The VM's direct-boot kernel and graphics ABI
compatibility packages remain held for separate host-managed updates.

## Publishing a runtime update

1. In the Omarchy VM project checkout, update the pinned Omarchy source and
   compatibility patches for the upstream release. Review any ABI or package
   changes before updating the guest package locks.
2. Build the guest runtime update package with `make guest-runtime-update`.
   This builds the package without rebuilding the factory VM image.
3. Check the package version and contents. Its Arch package version must start
   with the upstream release version, for example `4.0.5-1` for tag `v4.0.5`.
4. Create a stable GitHub release here using the exact upstream tag, such as
   `v4.0.5`.
5. Attach `dist/guest/omarchy-runtime-update.pkg.tar.zst` under that exact
   filename. GitHub must expose its SHA-256 digest in the Releases API.
6. Test `omarchy update` in a disposable VM before relying on the release.

The current policy update package targets Omarchy `v4.0.4` and uses package
version `4.0.4-4`. It includes the updater and points guests at this repository.
VMs already running `4.0.4-3` can run `omarchy update` after the matching
GitHub release is published. A VM that has not installed the bootstrap runtime
must first install this package manually:

```sh
sudo pacman -U ~/Downloads/omarchy-runtime-update.pkg.tar.zst
```

Future stable Omarchy releases are checked and installed from their matching
tags here.

## Current update asset

The ignored local file `omarchy-runtime-update.pkg.tar.zst` is attached to the
draft `v4.0.4` GitHub release. It is a release upload asset, not a source file
to commit into Git history. Publish the draft after reviewing the update
behavior above; guests can download its asset only after publication.
