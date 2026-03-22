%global debug_package %{nil}
%global __requires_exclude ^lib(dl\\.so\\.2|pthread\\.so\\.0)\\(GLIBC_[^)]*\\)\\(64bit\\)$
%undefine _disable_source_fetch
%global app_version 0.0.13
%global bun_version 1.3.9
%global github_owner pingdotgg
%global github_repo t3code
%global release_tag v%{app_version}

%ifarch x86_64
%global electron_arch x64
%global bun_pkg bun-linux-x64-baseline
%global claude_vendor_foreign_arch arm64-linux
%endif
%ifarch aarch64
%global electron_arch arm64
%global bun_pkg bun-linux-aarch64
%global claude_vendor_foreign_arch x64-linux
%endif
%{!?electron_arch:%{error:Unsupported arch %{_target_cpu}; supported arches are x86_64 and aarch64}}

Name:           t3code
Version:        %{app_version}
Release:        2%{?dist}
Summary:        Desktop UI for code agents such as Codex
License:        MIT
URL:            https://github.com/%{github_owner}/%{github_repo}
Source0:        https://github.com/%{github_owner}/%{github_repo}/archive/refs/tags/%{release_tag}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        https://registry.npmjs.org/%40oven/%{bun_pkg}/-/%{bun_pkg}-%{bun_version}.tgz#/%{bun_pkg}-%{bun_version}.tgz

BuildArch:      %{_target_cpu}

BuildRequires:  curl
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  nodejs(engine) >= 24.13.1
BuildRequires:  npm
BuildRequires:  python3
BuildRequires:  vips-devel
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
export BUN_INSTALL_CACHE_DIR="%{_builddir}/%{name}-%{version}-bun-cache"
export PYTHON="%{__python3}"
export npm_config_python="%{__python3}"
mkdir -p "$HOME" "$npm_config_cache" "$BUN_INSTALL_CACHE_DIR"

node_major="$(node -p 'process.versions.node.split(".")[0]')"
for modules_root in "/usr/lib/node_modules_${node_major}" /usr/lib/node_modules; do
  if [ -f "$modules_root/npm/node_modules/node-gyp/bin/node-gyp.js" ]; then
    node_gyp_js="$modules_root/npm/node_modules/node-gyp/bin/node-gyp.js"
    node_gyp_bin_dir="$modules_root/npm/node_modules/@npmcli/run-script/lib/node-gyp-bin"
    break
  fi
done
test -n "$node_gyp_js"
test -d "$node_gyp_bin_dir"

bun_root="%{_builddir}/%{name}-%{version}-bun"
rm -rf "$bun_root"
mkdir -p "$bun_root"
tar -xzf "%{SOURCE1}" -C "$bun_root"
if [ -x "$bun_root/package/bin/bun" ] && [ ! -e "$bun_root/package/bin/bunx" ]; then
  ln -s bun "$bun_root/package/bin/bunx"
fi
export PATH="$bun_root/package/bin:$node_gyp_bin_dir:$PATH"
export npm_config_node_gyp="$node_gyp_js"
test -f "$npm_config_node_gyp"

bun install --frozen-lockfile

# The staged production install inside `dist:desktop:artifact` must rebuild
# native Electron modules from source instead of bundling upstream prebuilts.
electron_version="$(node -p 'require("./apps/desktop/package.json").dependencies.electron')"
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
bun run dist:desktop:artifact -- \
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
find "%{buildroot}%{_libexecdir}/%{name}" -type d \
  \( -path '*/node_modules/@img/sharp-*' -o -path '*/node_modules/@img/sharp-libvips-*' \) \
  -prune -exec rm -rf '{}' +
find "%{buildroot}%{_libexecdir}/%{name}/resources/app.asar.unpacked/node_modules/@anthropic-ai/claude-agent-sdk/vendor" -type d -name '%{claude_vendor_foreign_arch}' -prune -exec rm -rf '{}' +

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
