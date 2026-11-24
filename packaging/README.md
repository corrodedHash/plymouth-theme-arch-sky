# Packaging

`plymouth-theme-arch-sky` is a normal `repo-add` package served as static files
from `pacman.thasky.one`. There is no repository server to talk to: the
"repository" is a directory tree that pacman fetches over HTTPS.

```
packaging/
├── PKGBUILD                        package definition
├── plymouth-theme-arch-sky.install   the usage hint shown after install
└── .SRCINFO                        generated, keep in sync with PKGBUILD
```

## The package does not select the theme

`pacman -S` only drops files into `/usr/share/plymouth/themes/arch-sky`. The
theme is baked into the initramfs, so nothing changes at boot until you run:

```bash
sudo plymouth-set-default-theme -R arch-sky
```

That is deliberate: a package must not reconfigure a running system, and the
initramfs is per machine. The `.install` hook prints the command instead of
running it. To go back to the distro default later:

```bash
sudo plymouth-set-default-theme --reset -R
```

## Publishing is only an upload

The repository database belongs to the server. CI never runs `repo-add` and
never handles the signing key: it builds the package and scp's the
`.pkg.tar.zst` into `$DEPLOY_TARGET/$PACMAN_ARCH/`. The server's own indexer
(`repo-add` plus signing, run by its timer) then folds it into `skyrepo.db` and
signs the database. Clients see the package after that run.

`.github/workflows/publish.yml` runs on every `v*` tag push:

1. builds the package in an `archlinux:base-devel` container,
2. `scp`s the `.pkg.tar.zst` to `$DEPLOY_TARGET/$PACMAN_ARCH/`,
3. checks that the file is served over HTTPS.

Required repository secrets:

| Secret | Meaning |
|---|---|
| `SSH_PRIVATE_KEY` | key allowed to write `$DEPLOY_TARGET` |
| `SSH_KNOWN_HOSTS` | pinned host key for `pacman.thasky.one` |

Optional repository variables: `DEPLOY_TARGET`
(default `thasky@pacman.thasky.one:/srv/pacman`) and `PACMAN_ARCH`
(default `x86_64`).

Packages stay unsigned (`SigLevel = ... PackageOptional`); only the database
carries a signature, and the server produces it.

### Why `x86_64` and not `any/`

The package is `arch=('any')`, but clients configure
`Server = https://pacman.thasky.one/$arch`, so an x86_64 machine only ever
fetches `x86_64/skyrepo.db`. Pacman installs `any` packages from that database
happily (the official repositories do the same); a file dropped in `any/` would
simply never be seen. Set `PACMAN_ARCH=any` only if you also add an `any`
server line to `/etc/pacman.conf`.

## Manual publish

Build the package:

```bash
cd packaging
makepkg --noconfirm --nodeps
```

Upload it (the whole "server side" is this one command):

```bash
scp ./*.pkg.tar.zst thasky@pacman.thasky.one:/srv/pacman/x86_64/
```

Then wait for the server's indexer, or trigger it on the host.

## Client setup

```bash
sudo pacman-key --add skyrepo.asc      # https://pacman.thasky.one/skyrepo.asc
sudo pacman-key --lsign-key <KEYID>
```

`/etc/pacman.d/skyrepo`:

```ini
[skyrepo]
SigLevel = DatabaseRequired PackageOptional
Server = https://pacman.thasky.one/$arch
```

Then:

```bash
sudo pacman -Syu plymouth-theme-arch-sky
sudo plymouth-set-default-theme -R arch-sky
```

Bump `pkgrel` for a rebuild of the same version and `pkgver` for a new one;
the tag must match (`v1.2.3` builds `pkgver=1.2.3`).
