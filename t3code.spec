%global debug_package %{nil}
%global __requires_exclude ^(/usr/bin/dotslash|libc\\.so\\(\\)\\(64bit\\)|lib(dl\\.so\\.2|pthread\\.so\\.0)\\(GLIBC_[^)]*\\)\\(64bit\\))$
%undefine _disable_source_fetch
%global app_version 0.1.9
%global pnpm_version 12.14.0
%global node_version 26.12.1
%global github_owner pingdotgg
%global github_repo t3code
%global release_tag v%{app_version}

%ifarch x86_64
%global electron_arch x64
%global node_source %{SOURCE2}
%global foreign_electron_arch arm64
%global claude_vendor_foreign_arch arm64-linux
%global rpm_file_arch x86-64
%endif
%ifarch aarch64
%global electron_arch arm64
%global node_source %{SOURCE3}
%global foreign_electron_arch x64
%global claude_vendor_foreign_arch x64-linux
%global rpm_file_arch ARM aarch64
%endif
%{!?electron_arch:%{error:Unsupported arch %{_target_cpu}; supported arches are x86_64 and aarch64}}

Name:           t3code
Version:        %{app_version}
Release:        1%{?dist}
Summary:        Desktop UI for code agents such as Codex
License:        MIT
URL:            https://github.com/%{github_owner}/%{github_repo}
Source0:        https://github.com/%{github_owner}/%{github_repo}/archive/refs/tags/%{release_tag}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        https://registry.npmjs.org/pnpm/-/pnpm-%{pnpm_version}.tgz#/pnpm-%{pnpm_version}.tgz
# Include both architectures so the same SRPM can build on either target.
Source2:        https://nodejs.org/dist/v%{node_version}/node-v%{node_version}-linux-x64.tar.xz
Source3:        https://nodejs.org/dist/v%{node_version}/node-v%{node_version}-linux-arm64.tar.xz
Source4:        https://nodejs.org/dist/v%{node_version}/SHASUMS256.txt#/node-v%{node_version}-SHASUMS256.txt

BuildArch:      %{_target_cpu}

BuildRequires:  cargo
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  nodejs24-npm
BuildRequires:  xz
BuildRequires:  python3
BuildRequires:  ImageMagick
BuildRequires:  libsecret-devel
BuildRequires:  vips-devel
BuildRequires:  git
Requires:       xdg-utils

%description
T3 Code is a desktop UI for code agents such as Codex. This package builds the
native Linux desktop bundle for the current target architecture from the pinned
upstream release source tarball and installs it as a regular application.

%prep
%autosetup -n %{github_repo}-%{version}

%build
export HOME="%{_builddir}/%{name}-%{version}-home"
export npm_config_cache="%{_builddir}/%{name}-%{version}-npm-cache"
export PNPM_HOME="%{_builddir}/%{name}-%{version}-pnpm-home"
export pnpm_config_store_dir="%{_builddir}/%{name}-%{version}-pnpm-store"
export PYTHON="%{__python3}"
export npm_config_python="%{__python3}"
mkdir -p "$HOME" "$npm_config_cache" "$PNPM_HOME" "$pnpm_config_store_dir"

# Upstream pins Node.js 26, which is unavailable in some target Fedora repos.
# Use the official runtime only for the build; it is not installed in the RPM.
node_archive="$(basename "%{node_source}")"
node_checksum="$(awk -v archive="$node_archive" '$2 == archive { print $1 }' "%{SOURCE4}")"
test -n "$node_checksum"
printf '%s  %s\n' "$node_checksum" "%{node_source}" | sha256sum --check --strict
node_root="%{_builddir}/%{name}-%{version}-node"
mkdir -p "$node_root"
tar -xJf "%{node_source}" -C "$node_root" --strip-components=1
node_cmd="$node_root/bin/node"
test -x "$node_cmd"
test "$("$node_cmd" -p 'process.versions.node')" = "%{node_version}"
for modules_root in /usr/lib/node_modules_24 /usr/lib/node_modules; do
  if [ -f "$modules_root/npm/node_modules/node-gyp/bin/node-gyp.js" ]; then
    npm_cli="$modules_root/npm/bin/npm-cli.js"
    node_gyp_js="$modules_root/npm/node_modules/node-gyp/bin/node-gyp.js"
    node_gyp_bin_dir="$modules_root/npm/node_modules/@npmcli/run-script/lib/node-gyp-bin"
    break
  fi
done
test -f "$npm_cli"
test -n "$node_gyp_js"
test -d "$node_gyp_bin_dir"

pnpm_root="%{_builddir}/%{name}-%{version}-pnpm"
rm -rf "$pnpm_root"
mkdir -p "$pnpm_root"
tar -xzf "%{SOURCE1}" -C "$pnpm_root"
pnpm_cli="$pnpm_root/package/bin/pnpm.mjs"
pnpx_cli="$pnpm_root/package/bin/pnpx.mjs"
test -f "$pnpm_cli"
test -f "$pnpx_cli"
cat > "$PNPM_HOME/pnpm" <<EOF
#!/bin/sh
exec "$node_cmd" "$pnpm_cli" "\$@"
EOF
cat > "$PNPM_HOME/pnpx" <<EOF
#!/bin/sh
exec "$node_cmd" "$pnpx_cli" "\$@"
EOF
cat > "$PNPM_HOME/node" <<EOF
#!/bin/sh
exec "$node_cmd" "\$@"
EOF
cat > "$PNPM_HOME/npm" <<EOF
#!/bin/sh
exec "$node_cmd" "$npm_cli" "\$@"
EOF
chmod 0755 "$PNPM_HOME/pnpm" "$PNPM_HOME/pnpx" "$PNPM_HOME/node" "$PNPM_HOME/npm"
export PATH="$PNPM_HOME:$node_gyp_bin_dir:$PATH"
export npm_config_node_gyp="$node_gyp_js"
test -f "$npm_config_node_gyp"

pnpm install --frozen-lockfile

# The staged production install inside `dist:desktop:artifact` must rebuild
# native Electron modules from source instead of bundling upstream prebuilts.
electron_version="$("$node_cmd" -p 'require("./apps/desktop/package.json").dependencies.electron')"
test -n "$electron_version"
pkg-config --modversion vips-cpp
export npm_config_runtime=electron
export npm_config_target="$electron_version"
export npm_config_arch="%{electron_arch}"
export npm_config_target_arch="%{electron_arch}"
export npm_config_disturl="https://electronjs.org/headers"
export npm_config_build_from_source=true
export npm_config_platform=linux
export npm_config_libc=glibc
export SHARP_FORCE_GLOBAL_LIBVIPS=1
pnpm run dist:desktop:artifact \
  --platform linux \
  --target tar.gz \
  --arch %{electron_arch} \
  --build-version %{version} \
  --output-dir "%{_builddir}/%{name}-%{version}-dist"

%install
rm -rf "%{buildroot}"

artifact="%{_builddir}/%{name}-%{version}-dist/T3-Code-%{version}-%{electron_arch}.tar.gz"
test -f "$artifact"

extract_dir="$(mktemp -d)"
trap 'rm -rf "$extract_dir"' EXIT
tar -xzf "$artifact" -C "$extract_dir"

appdir="$(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d | head -n1)"
test -n "$appdir"

install -d "%{buildroot}%{_libexecdir}/%{name}"
cp -a "$appdir"/. "%{buildroot}%{_libexecdir}/%{name}/"

# Drop unused native addons that trigger invalid RPM deps on glibc-based Fedora.
find "%{buildroot}%{_libexecdir}/%{name}" -type f -name '*.musl.node' -delete
rm -rf "%{buildroot}%{_libexecdir}/%{name}/resources/app.asar.unpacked/node_modules/node-pty/prebuilds"
find "%{buildroot}%{_libexecdir}/%{name}/resources/app.asar.unpacked/node_modules" -type d \
  \( -path '*/prebuilds/linux-%{foreign_electron_arch}' -o -path '*/linux64-bin' \) \
  -prune -exec rm -rf '{}' +
find "%{buildroot}%{_libexecdir}/%{name}/resources/app.asar.unpacked/node_modules" -type d \
  -iname '*musl*' -prune -exec rm -rf '{}' +
find "%{buildroot}%{_libexecdir}/%{name}" -type d \
  \( -path '*/node_modules/@img/sharp-*' -o -path '*/node_modules/@img/sharp-libvips-*' \) \
  -prune -exec rm -rf '{}' +
claude_vendor_dir="%{buildroot}%{_libexecdir}/%{name}/resources/app.asar.unpacked/node_modules/@anthropic-ai/claude-agent-sdk/vendor"
if [ -d "$claude_vendor_dir" ]; then
  find "$claude_vendor_dir" -type d -name '%{claude_vendor_foreign_arch}' -prune -exec rm -rf '{}' +
  find "$claude_vendor_dir" -type d -iname '*musl*' -prune -exec rm -rf '{}' +
fi
file_manifest="$(mktemp)"
find "%{buildroot}%{_libexecdir}/%{name}" -type f -print0 | xargs -0 file > "$file_manifest"
if grep -i musl "$file_manifest"; then
  echo "musl-linked files remain in %{_libexecdir}/%{name}; prune or rebuild them for glibc" >&2
  exit 1
fi
if grep -E 'ELF .* (x86-64|ARM aarch64)' "$file_manifest" | grep -Fv '%{rpm_file_arch}'; then
  echo "foreign-architecture ELF files remain in %{_libexecdir}/%{name}; prune or rebuild them for %{_target_cpu}" >&2
  exit 1
fi
rm -f "$file_manifest"

if [ -f "%{buildroot}%{_libexecdir}/%{name}/chrome-sandbox" ]; then
  chmod 4755 "%{buildroot}%{_libexecdir}/%{name}/chrome-sandbox"
fi

main_exe="$(find "$appdir" -mindepth 1 -maxdepth 1 -type f -perm /111 \
  ! -name '*.desktop' \
  ! -name '*.so' \
  ! -name '*.so.*' \
  ! -name 'chrome-sandbox' \
  ! -name 'chrome_crashpad_handler' \
  ! -name 'AppRun' \
  -printf '%f\n' | sort | head -n1)"
test -n "$main_exe"

install -d "%{buildroot}%{_bindir}"
cat > "%{buildroot}%{_bindir}/%{name}" <<EOF
#!/bin/sh
exec %{_libexecdir}/%{name}/${main_exe} "\$@"
EOF
chmod 0755 "%{buildroot}%{_bindir}/%{name}"

install -d "%{buildroot}%{_datadir}/applications"
desktop_src="$(find "$appdir" -mindepth 1 -maxdepth 1 -type f -name '*.desktop' | head -n1)"
if [ -n "$desktop_src" ]; then
  sed \
    -e 's|^Exec=.*|Exec=%{_bindir}/%{name} %U|' \
    -e 's|^Icon=.*|Icon=%{name}|' \
    "$desktop_src" > "%{buildroot}%{_datadir}/applications/%{name}.desktop"
else
  cat > "%{buildroot}%{_datadir}/applications/%{name}.desktop" <<EOF
[Desktop Entry]
Name=T3 Code
Comment=Desktop UI for code agents
Exec=%{_bindir}/%{name} %U
Terminal=false
Type=Application
Icon=%{name}
Categories=Development;
EOF
fi

install -d "%{buildroot}%{_datadir}/icons/hicolor/512x512/apps"
install -pm0644 "assets/prod/black-universal-1024.png" \
  "%{buildroot}%{_datadir}/icons/hicolor/512x512/apps/%{name}.png"

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/512x512/apps/%{name}.png
%{_libexecdir}/%{name}

%changelog

* Fri Nov 13 2026 Codex <codex@openai.com> - 0.1.9-1
- Update to the latest non-nightly upstream release

* Wed Nov 04 2026 Codex <codex@openai.com> - 0.1.7-2
- Fix the pnpm 12.14.0 source URL
- Use pnpm 12's module entry points
- Use the upstream-pinned Node.js 26.12.1 build runtime on all Fedora targets

* Tue Oct 20 2026 Codex <codex@openai.com> - 0.1.0-1
- Update to the latest non-nightly upstream release

* Wed Oct 14 2026 Codex <codex@openai.com> - 0.0.45-1
- Update to the latest non-nightly upstream release

* Mon Sep 21 2026 Codex <codex@openai.com> - 0.0.42-1
- Update to the latest non-nightly upstream release

* Wed Sep 09 2026 Codex <codex@openai.com> - 0.0.40-2
- Add the libsecret development dependency required by the desktop build
- Add an npm wrapper for native dependency build fallbacks on Fedora 43

* Wed Sep 09 2026 Codex <codex@openai.com> - 0.0.40-1
- Update to the latest non-nightly upstream release

* Sun Sep 06 2026 Codex <codex@openai.com> - 0.0.38-1
- Update to the latest non-nightly upstream release

* Tue Aug 18 2026 Codex <codex@openai.com> - 0.0.33-1
- Update to the latest non-nightly upstream release

* Thu Jul 30 2026 Codex <codex@openai.com> - 0.0.31-2
- Add Cargo for building the native resource monitor

* Sat Jul 04 2026 Codex <codex@openai.com> - 0.0.28-8
- Make bundled native file checks robust and prune musl dependency directories

* Sat Jul 04 2026 Codex <codex@openai.com> - 0.0.28-7
- Prune foreign-architecture Linux prebuilds from bundled node modules

* Thu Jul 02 2026 Codex <codex@openai.com> - 0.0.28-5
- Prune bundled musl vendor binaries so the Fedora package does not require an
  unprovided musl libc soname

* Wed Jul 01 2026 Codex <codex@openai.com> - 0.0.28-4
- Add build-time node shim for package scripts that call unversioned node

* Wed Jul 01 2026 Codex <codex@openai.com> - 0.0.28-3
- Use Fedora's portable nodejs24-npm dependency instead of Fedora 44-only bin subpackages

* Wed Jul 01 2026 Codex <codex@openai.com> - 0.0.28-2
- Exclude bundled DotSlash and generic libc auto-requires from packaged agent tooling

* Wed Jun 10 2026 Codex <codex@openai.com> - 0.0.27-2
- Add ImageMagick build dependency for Linux icon generation
- Use Fedora's Node.js 24 runtime and npm symlinks consistently during the build

* Mon Jun 08 2026 Codex <codex@openai.com> - 0.0.25-1
- Update to 0.0.25
- Switch the build from Bun to the upstream pinned pnpm package manager

* Sat Mar 07 2026 Codex <codex@openai.com> - 0.0.4-4
- Use `assets/prod/black-universal-1024.png` as the installed desktop icon

* Sat Mar 07 2026 Codex <codex@openai.com> - 0.0.4-3
- Use Fedora's `nodejs-npm` package name for the bundled npm/node-gyp tooling
- Resolve Fedora's versioned npm path dynamically

* Sat Mar 07 2026 Codex <codex@openai.com> - 0.0.4-2
- Add an explicit npm-related BuildRequires and resolve Fedora's versioned npm path dynamically

* Sat Mar 07 2026 Codex <codex@openai.com> - 0.0.4-1
- Update to 0.0.4
- Force Bun to use the packaged node-gyp during native addon builds
- Prune unused musl and non-Linux node addon prebuilds to avoid invalid RPM deps
