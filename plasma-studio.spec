%global debug_package %{nil}
%undefine _disable_source_fetch
%global app_version 0.0.0.2
%global gitlab_owner niccolove
%global gitlab_repo plasma-studio
%global release_tag %{app_version}
%global source_url %{url}/-/archive/%{release_tag}/%{gitlab_repo}-%{release_tag}.tar.gz

Name:           plasma-studio
Version:        %{app_version}
Release:        1%{?dist}
Summary:        Node-based Qt/QML editor for visual effects experiments
License:        LicenseRef-Unknown
URL:            https://invent.kde.org/%{gitlab_owner}/%{gitlab_repo}

BuildRequires:  cmake
BuildRequires:  curl
BuildRequires:  desktop-file-utils
BuildRequires:  ffmpeg-devel
BuildRequires:  gcc-c++
BuildRequires:  libdrm-devel
BuildRequires:  LibRaw-devel
BuildRequires:  make
BuildRequires:  mesa-libEGL-devel
BuildRequires:  mpv-devel
BuildRequires:  pkgconfig
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtmultimedia-devel
BuildRequires:  qt6-qtshadertools-devel
BuildRequires:  qt6-qtwayland-devel

Requires:       kf6-kirigami
Requires:       kf6-kirigami-addons
Requires:       qt6-qtdeclarative
Requires:       qt6-qtmultimedia

%description
Plasma Studio is an experimental Qt/QML node graph editor for composing visual
effects, image and video processing nodes, shader-based filters, raw image
inputs, and playback/rendering experiments.

%prep
%setup -q -c -T -n %{gitlab_repo}-%{release_tag}
curl --fail --location --retry 3 '%{source_url}' | tar -xz --strip-components=1

sed -i \
  -e 's/pkg_check_modules(MPV REQUIRED mpv)/pkg_check_modules(MPV REQUIRED IMPORTED_TARGET mpv)/' \
  -e 's/pkg_check_modules(LIBRAW REQUIRED libraw)/pkg_check_modules(LIBRAW REQUIRED IMPORTED_TARGET libraw)\npkg_check_modules(FFMPEG REQUIRED IMPORTED_TARGET libavcodec libavformat libavutil libavfilter)\npkg_check_modules(EGL REQUIRED IMPORTED_TARGET egl)\npkg_check_modules(LIBDRM REQUIRED IMPORTED_TARGET libdrm)/' \
  -e 's/${LIBRAW_LIBRARIES}/${LIBRAW_LIBRARIES}\n    PkgConfig::MPV\n    PkgConfig::LIBRAW\n    PkgConfig::FFMPEG\n    PkgConfig::EGL\n    PkgConfig::LIBDRM/' \
  CMakeLists.txt

sed -i \
  -e '/engine.addImportPath(app.applicationDirPath() + "\/..\/qml");/d' \
  -e '/engine.rootContext()->setContextProperty("buildDir", app.applicationDirPath() + "\/..");/d' \
  app/main.cpp

if grep -q 'm_codecCtx->profile = FF_PROFILE_H264_HIGH;' helpers/RenderingHelper.cpp; then
  sed -i \
    -e 's/m_codecCtx->profile = FF_PROFILE_H264_HIGH;/m_codecCtx->profile = AV_PROFILE_H264_HIGH;/' \
    helpers/RenderingHelper.cpp
fi

sed -i \
  -e 's/pageStack.initialPage: Page {/pageStack.initialPage: Kirigami.Page {/' \
  app/main.qml

%build
mkdir -p %{__cmake_builddir}
pushd %{__cmake_builddir}
%{__cmake} .. \
  -G "Unix Makefiles" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=%{_prefix} \
  -DCMAKE_SKIP_RPATH=ON \
  -DCMAKE_VERBOSE_MAKEFILE=ON \
  -DQt6Quick_DIR=%{_libdir}/cmake/Qt6Quick
%make_build
popd

%install
rm -rf "%{buildroot}"

pushd %{__cmake_builddir}
%make_install
popd

ln -s plasmastudio "%{buildroot}%{_bindir}/%{name}"

find "%{buildroot}" \( -type f -o -type l \) -printf '/%%P\n' | sort > %{name}.files

%check
if [ -d "%{buildroot}%{_datadir}/applications" ]; then
  for desktop_file in "%{buildroot}%{_datadir}/applications"/*.desktop; do
    [ -e "$desktop_file" ] || continue
    desktop-file-validate "$desktop_file"
  done
fi

%files -f %{name}.files

%changelog
* Mon May 11 2026 BurningPho3nix <pr@burningpho3nix.xyz> - 0.0.0.2-1
- Update to Plasma Studio 0.0.0.2
- Use upstream app install rules and keep a plasma-studio command alias

* Thu Apr 30 2026 BurningPho3nix <pr@burningpho3nix.xyz> - 0.0.0.1-3
- Install bundled resources referenced by the QML node graph

* Thu Apr 30 2026 BurningPho3nix <pr@burningpho3nix.xyz> - 0.0.0.1-2
- Use a Kirigami page for the node graph entry point

* Wed Apr 29 2026 BurningPho3nix <pr@burningpho3nix.xyz> - 0.0.0.1-1
- Initial package for Plasma Studio 0.0.0.1
