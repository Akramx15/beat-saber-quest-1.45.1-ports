#!/usr/bin/env python3
"""Pinned QMODs for an already patched Quest. Default plan never contacts ADB.
Only explicit install changes native mods/registrations. No APK, save, song,
runtime configuration, permission, or account writes are performed.
"""
import argparse
import datetime
import functools
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import urllib.request
import uuid
import zipfile

PACKAGE = 'com.beatgames.beatsaber'
VERSION = '1.45.1_27839'
VERSION_CODE = 3071
REMOTE = f'/sdcard/ModData/{PACKAGE}'
NATIVE_FOLDERS = {'libraryFiles': 'libs', 'modFiles': 'early_mods', 'lateModFiles': 'mods'}
SAFE_ID = re.compile(r'[A-Za-z0-9_.+-]+\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_MEMBER = 256 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def json_load(data):
    return json.loads(data, object_pairs_hook=unique_object)


def require_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError('A complete lowercase SHA256 pin is required')
    return value


def safe_member(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return False
    for part in name.rstrip('/').split('/'):
        if not part or part in ('.', '..') or part.rstrip(' .') != part:
            return False
        if re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part):
            return False
        if any(c in '<>"|?*' for c in part):
            return False
    return not PurePosixPath(name).is_absolute()


def no_local_links(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError(f'Local symlinks/junctions are not accepted: {item}')


def elf_arm64(data, name):
    if (len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<HH', data, 16) != (3, 183)
            or struct.unpack_from('<H', data, 52)[0] != 64):
        raise ValueError(f'Expected ARM64 ELF shared library: {name}')


def effective_entry(entry, receipt):
    result = dict(entry)
    if entry.get('url'):
        require_sha(entry.get('sha256'))  # Receipt never overrides download pins.
    elif entry.get('local_build'):
        inputs = require_sha(entry['local_build'].get('inputs_sha256'))
        built = (receipt or {}).get('packages', {}).get(entry['id'])
        if not built or built.get('version') != entry['version'] or built.get('inputs_sha256') != inputs:
            raise ValueError(f'Missing or mismatched verified build receipt: {entry["id"]}')
        result['sha256'] = require_sha(built.get('qmod_sha256'))
        result['native_sha256'] = built.get('native_sha256')
        result['verified_build_inputs_sha256'] = inputs
    require_sha(result.get('sha256'))
    if not isinstance(result.get('native_sha256'), dict) or not result['native_sha256']:
        raise ValueError(f'Native pins are required: {entry["id"]}')
    for pin in result['native_sha256'].values():
        require_sha(pin)
    return result


def read_qmod(path, entry):
    no_local_links(path)
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('QMOD exceeds archive size limit')
    archive = path.read_bytes()
    if digest(archive) != require_sha(entry.get('sha256')):
        raise ValueError(f'QMOD checksum mismatch: {path.name}')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        seen, total = set(), 0
        for info in z.infolist():
            mode = (info.external_attr >> 16) & 0o170000
            # ZipInfo normalizes backslashes on Windows and truncates at NUL.
            # Validate the archive's original spelling before that conversion.
            if (not safe_member(info.orig_filename)
                    or info.orig_filename != info.filename):
                raise ValueError(f'Unsafe or normalized archive path: {info.orig_filename!r}')
            name = info.filename.rstrip('/').casefold()
            if not safe_member(info.filename) or name in seen:
                raise ValueError(f'Unsafe or duplicate archive path: {info.filename}')
            if mode not in (0, 0o100000, 0o040000) or info.flag_bits & 1:
                raise ValueError('Links, special files and encrypted members are not accepted')
            if info.file_size > MAX_MEMBER or len(seen) >= 10000:
                raise ValueError('QMOD member limit exceeded')
            total += info.file_size
            if total > MAX_ARCHIVE:
                raise ValueError('QMOD expanded size limit exceeded')
            seen.add(name)
        mod = json_load(z.read('mod.json'))
        if mod['id'] != entry['id'] or mod['version'] != entry['version']:
            raise ValueError(f'Unexpected package identity: {path.name}')
        if not SAFE_ID.fullmatch(mod['id']) or not SAFE_ID.fullmatch(mod['version']):
            raise ValueError('Unsafe package identity')
        if mod.get('packageId', PACKAGE) != PACKAGE or mod.get('modloader') != 'Scotland2':
            raise ValueError('Wrong game package or modloader')
        if mod.get('packageVersion') != VERSION:
            untargeted = mod.get('packageVersion') is None and entry.get('verified_untargeted_library') is True
            approved = mod.get('packageVersion') in entry.get('allowed_package_versions', [])
            if not (untargeted or approved):
                raise ValueError(f'Wrong or missing game version: {path.name}')
        if mod.get('fileCopies'):
            raise ValueError('Auxiliary file copies are outside this installer scope')
        natives, names = [], set()
        for key, folder in NATIVE_FOLDERS.items():
            if not isinstance(mod.get(key, []), list):
                raise ValueError('Native lists must be arrays')
            for name in mod.get(key, []):
                if (not re.fullmatch(r'[A-Za-z0-9_.+-]+\.so', name)
                        or name in ('libsl2.so', 'libmain.so') or name.casefold() in names):
                    raise ValueError('Unsafe, reserved or duplicate native filename')
                names.add(name.casefold())
                data = z.read(name)
                if digest(data) != require_sha(entry.get('native_sha256', {}).get(name)):
                    raise ValueError(f'Native checksum mismatch: {name}')
                elf_arm64(data, name)
                natives.append((folder, name, data))
        if not natives or set(entry['native_sha256']) != {n for _, n, _ in natives}:
            raise ValueError('Native pin list must exactly match the native list')
    return mod, natives


@functools.total_ordering
class SemVer:
    def __init__(self, base, prerelease=()):
        self.base, self.prerelease = tuple(base), tuple(prerelease)

    def __eq__(self, other):
        return (self.base, self.prerelease) == (other.base, other.prerelease)

    def __lt__(self, other):
        if self.base != other.base:
            return self.base < other.base
        if not self.prerelease or not other.prerelease:
            return bool(self.prerelease) and not other.prerelease
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            if left.isdigit() and right.isdigit():
                return int(left) < int(right)
            if left.isdigit() != right.isdigit():
                return left.isdigit()
            return left < right
        return len(self.prerelease) < len(other.prerelease)


def version_tuple(value):
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([-A-Za-z0-9]+(?:\.[-A-Za-z0-9]+)*))?(?:\+[-A-Za-z0-9]+(?:\.[-A-Za-z0-9]+)*)?', value)
    if not match:
        raise ValueError(f'Unsupported version syntax; review required: {value}')
    pre = tuple(match[4].split('.')) if match[4] else ()
    if any(x.isdigit() and len(x)>1 and x[0]=='0' for x in pre):
        raise ValueError('Leading zeros are invalid in numeric prerelease identifiers')
    return SemVer(tuple(map(int, match.groups()[:3])), pre)


def satisfies(version, requirement):
    actual = version_tuple(version)
    for alternative in requirement.split('||'):
        terms = alternative.strip().split()
        if not terms:
            raise ValueError('Empty dependency range')
        accepted, permits_prerelease = True, False
        for term in terms:
            if term == '*':
                continue
            op, value = re.fullmatch(r'(\^|~|>=|<=|>|<|=)?(.+)', term).groups()
            wanted = version_tuple(value)
            permits_prerelease |= bool(wanted.prerelease) and wanted.base == actual.base
            if op == '^':
                i = next((i for i, n in enumerate(wanted.base) if n), 2)
                upper = SemVer(wanted.base[:i] + (wanted.base[i] + 1,) + (0,) * (2 - i))
                valid = wanted <= actual < upper
            elif op == '~':
                valid = wanted <= actual < SemVer((wanted.base[0], wanted.base[1] + 1, 0))
            else:
                valid = {None: actual == wanted, '=': actual == wanted, '>=': actual >= wanted,
                         '<=': actual <= wanted, '>': actual > wanted, '<': actual < wanted}[op]
            accepted = accepted and valid
        if accepted and (not actual.prerelease or permits_prerelease):
            return True
    return False


def select_packages(manifest, profile):
    packages, ids = {}, set()
    for entry in manifest['packages']:
        if not SAFE_ID.fullmatch(entry['id']) or not SAFE_ID.fullmatch(entry['version']):
            raise ValueError('Unsafe manifest identity')
        if entry['id'].casefold() in ids:
            raise ValueError('Duplicate manifest package ID')
        ids.add(entry['id'].casefold())
        packages[entry['id']] = entry
    selected = set(manifest['profiles'][profile])
    pending = list(selected)
    while pending:
        item = pending.pop()
        if item not in packages:
            raise ValueError(f'Unknown dependency: {item}')
        for dependency in packages[item].get('dependencies', []):
            dep = dependency['id'] if isinstance(dependency, dict) else dependency
            if dep not in selected:
                selected.add(dep)
                pending.append(dep)
    return [packages[x] for x in sorted(selected)]


def validate_dependencies(qmods):
    selected = {mod['id']: mod for _, _, mod, _ in qmods}
    if len(selected) != len(qmods):
        raise ValueError('Duplicate selected QMOD ID')
    for _, entry, mod, _ in qmods:
        for dep in mod.get('dependencies', []):
            if not isinstance(dep, dict) or not SAFE_ID.fullmatch(dep.get('id', '')):
                raise ValueError('Malformed QMOD dependency')
            found = selected.get(dep['id'])
            if not found and not dep.get('required', True):
                continue
            if not found or not satisfies(found['version'], dep['version']):
                raise ValueError(f'Unsatisfied dependency: {mod["id"]} requires {dep["id"]} {dep["version"]}')
        for dep in entry.get('dependencies', []):
            key = dep['id'] if isinstance(dep, dict) else dep
            if key not in selected:
                raise ValueError(f'Missing manifest dependency: {key}')
            if isinstance(dep, dict) and dep.get('version') and not satisfies(selected[key]['version'], dep['version']):
                raise ValueError(f'Manifest dependency version mismatch: {key}')


def locate_qmod(directory, entry):
    name = entry['filename']
    if not safe_member(name) or '/' in name or not name.endswith('.qmod'):
        raise ValueError('Unsafe QMOD filename in manifest')
    path = directory / name
    no_local_links(path)
    return path


def fetch(directory, entry):
    path = locate_qmod(directory, entry)
    if path.exists():
        read_qmod(path, entry)
        return path
    if not entry.get('url'):
        raise FileNotFoundError(f'Build locally first: {entry["id"]} (see BUILDING.md)')
    if not entry['url'].startswith('https://'):
        raise ValueError('Downloads require HTTPS')
    require_sha(entry.get('sha256'))
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, suffix='.download', delete=False) as stream:
        temp = Path(stream.name)
        try:
            request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Quest1451ExperimentalModpack/1'})
            with urllib.request.urlopen(request, timeout=60) as response:
                if not response.geturl().startswith('https://'):
                    raise ValueError('Download redirected away from HTTPS')
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARCHIVE:
                        raise ValueError('Download exceeds archive size limit')
                    stream.write(chunk)
            stream.close()
            read_qmod(temp, entry)
            temp.replace(path)
        finally:
            stream.close()
            temp.unlink(missing_ok=True)
    return path


class Device:
    def __init__(self, adb, serial):
        self.command = [adb]
        listing = subprocess.check_output([adb, 'devices'], text=True)
        devices = [line.split()[0] for line in listing.splitlines()[1:] if len(line.split()) == 2 and line.split()[1] == 'device']
        if serial:
            if serial not in devices:
                raise ValueError('Selected Quest is not connected and authorized')
        elif len(devices) == 1:
            serial = devices[0]
        else:
            raise ValueError('Connect one authorized Quest, or supply --serial')
        self.command += ['-s', serial]

    def run(self, *args, check=True):
        return subprocess.run(self.command + list(args), check=check, capture_output=True, text=True, encoding='utf-8')

    def shell(self, command, check=True):
        return self.run('shell', command, check=check).stdout.strip()

    def read_bytes(self, command):
        # exec-out preserves the command argument for sh -c. Quoting this
        # entire argument again makes Android treat it as one executable name.
        # Individual paths inside command are already shell-quoted by callers.
        return subprocess.check_output(self.command + ['exec-out', 'sh', '-c', command])

    def exists(self, remote):
        result = self.run('shell', 'test -e ' + shlex.quote(remote), check=False)
        if result.returncode not in (0, 1):
            raise RuntimeError('Cannot determine remote path state')
        return result.returncode == 0

    def no_links(self, root):
        p = PurePosixPath(root)
        # /sdcard itself is Android's standard storage alias.
        parents = [str(p), *(str(x) for x in p.parents if str(x).startswith('/sdcard/ModData'))]
        for path in parents:
            result = self.run('shell', 'test -L ' + shlex.quote(path), check=False)
            if result.returncode == 0:
                raise ValueError(f'Remote symlink rejected: {path}')
            if result.returncode != 1:
                raise RuntimeError('Cannot inspect remote symlinks')
        if self.exists(root) and self.read_bytes('find ' + shlex.quote(root) + ' -type l -print0'):
            raise ValueError('Remote mod directories contain symlinks')

    def files(self, root):
        self.no_links(root)
        if not self.exists(root):
            return set()
        raw = self.read_bytes('find ' + shlex.quote(root) + ' -type f -print0')
        names = {p.decode('utf-8') for p in raw.split(b'\0') if p}
        for name in names:
            rel = str(PurePosixPath(name).relative_to(root))
            if not safe_member(rel):
                raise ValueError(f'Unsafe installed path: {name}')
        return names

    def file_hash(self, remote):
        if not self.exists(remote):
            return None
        return require_sha(self.shell('sha256sum ' + shlex.quote(remote)).split()[0])

    def pull(self, remote, local):
        local.parent.mkdir(parents=True, exist_ok=True)
        self.run('pull', remote, str(local))

    def mkdir(self, remote):
        self.no_links(str(PurePosixPath(remote).parent))
        self.shell('mkdir -p ' + shlex.quote(remote))

    def push(self, local, remote):
        self.run('push', str(local), remote)

    def move(self, source, destination):
        self.no_links(str(PurePosixPath(destination).parent))
        self.shell('mv -f ' + shlex.quote(source) + ' ' + shlex.quote(destination))

    def remove(self, remote):
        self.shell('rm -f ' + shlex.quote(remote))

    def rmdir(self, remote):
        # Only empty directories; never erase concurrent foreign content.
        self.shell('rmdir ' + shlex.quote(remote), check=False)

    def chmod(self, remote):
        self.shell('chmod 644 ' + shlex.quote(remote))

    def stop(self):
        self.shell(f'am force-stop {PACKAGE}')

    def validate_game(self, pins):
        dump = self.shell(f'dumpsys package {PACKAGE}')
        if not re.search(r'(?m)^\s*versionName=' + re.escape(VERSION) + r'\s*$', dump):
            raise ValueError(f'Install requires {PACKAGE} {VERSION}; no downgrade is performed')
        if not re.search(r'\bversionCode=' + str(VERSION_CODE) + r'\b', dump):
            raise ValueError('Installed game versionCode does not match the reviewed build')
        boots, loaders = pins.get('apk_libmain_sha256', []), pins.get('loader_sha256', [])
        if isinstance(boots, str): boots = [boots]
        if isinstance(loaders, str): loaders = [loaders]
        if not boots or not loaders:
            raise ValueError('Manifest must pin the patched APK bootstrap and external Scotland2 loader')
        for pin in boots + loaders: require_sha(pin)
        paths = self.shell(f'pm path {PACKAGE}').splitlines()
        bases = [p[8:] for p in paths if p.startswith('package:/data/app/') and p.endswith('/base.apk')]
        if len(bases) != 1:
            raise ValueError('Cannot identify the installed base APK')
        apk = bases[0]
        members = ('modded.json', 'lib/arm64-v8a/libmain.so')
        try:
            marker, bootstrap = [self.read_bytes('unzip -p ' + shlex.quote(apk) + ' ' + shlex.quote(n)) for n in members]
        except subprocess.CalledProcessError:
            # Read-only private pull, deleted after validation, never distributed.
            with tempfile.TemporaryDirectory(prefix='quest1451-private-apk-') as tmp:
                local = Path(tmp) / 'base.apk'
                self.pull(apk, local)
                with zipfile.ZipFile(local) as z:
                    marker, bootstrap = [z.read(n) for n in members]
        tag = json_load(marker)
        # QuestPatcher legitimately writes a null modloaderVersion. Exact
        # reviewed libmain/libsl2 hashes establish the actual loader identity.
        if tag.get('modloaderName') != 'Scotland2':
            raise ValueError('Installed APK lacks a valid Scotland2 patched marker')
        elf_arm64(bootstrap, 'APK libmain.so')
        if digest(bootstrap) not in boots:
            raise ValueError('Installed APK bootstrap does not match reviewed pins')
        loader = REMOTE + '/Modloader/libsl2.so'
        self.no_links(REMOTE + '/Modloader')
        data = self.read_bytes('cat ' + shlex.quote(loader))
        elf_arm64(data, 'external libsl2.so')
        if digest(data) not in loaders:
            raise ValueError('External Scotland2 loader does not match reviewed pins')
        return {'apk_libmain_sha256': digest(bootstrap), 'loader_sha256': digest(data), 'modded': tag}


def stage(qmods, destination):
    files, names = {}, set()
    for path, entry, mod, natives in qmods:
        actual_mod, actual_natives = read_qmod(path, entry)
        if actual_mod != mod or actual_natives != natives:
            raise ValueError('QMOD changed after verification')
        for folder, name, data in natives:
            if name.casefold() in names:
                raise ValueError(f'Duplicate selected native: {name}')
            names.add(name.casefold())
            files[f'Modloader/{folder}/{name}'] = data
        registered = f'Packages/{VERSION}/{mod["id"]}_v{mod["version"]}'
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    files[registered + '/' + info.filename] = z.read(info)
    for rel, data in files.items():
        target = destination.joinpath(*PurePosixPath(rel).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {REMOTE + '/' + rel: destination.joinpath(*PurePosixPath(rel).parts) for rel in files}


def selected_registrations(device, files, ids):
    roots = set()
    prefix = REMOTE + '/Packages/' + VERSION + '/'
    for remote in files:
        rel = remote[len(prefix):] if remote.startswith(prefix) else ''
        directory = rel.split('/', 1)[0]
        for ident in ids:
            if directory.startswith(ident + '_v'):
                if not SAFE_ID.fullmatch(directory[len(ident) + 2:]):
                    raise ValueError('Unsafe existing package registration')
                roots.add(prefix + directory)
    for root in roots:
        marker = root + '/mod.json'
        if marker not in files:
            raise ValueError('Existing selected package has no readable registration')
        mod = json_load(device.read_bytes('cat ' + shlex.quote(marker)))
        if mod.get('id') not in ids or root != prefix + mod['id'] + '_v' + mod.get('version', ''):
            raise ValueError('Existing registration identity does not match its folder')
    return roots


def parent_dirs(paths, stop):
    result = set()
    for path in paths:
        p = PurePosixPath(path).parent
        while str(p).startswith(stop + '/'):
            result.add(str(p))
            p = p.parent
    return result


def install(device, qmods, backup_parent, patched_game):
    validate_dependencies(qmods)
    no_local_links(backup_parent)
    with tempfile.TemporaryDirectory(prefix='quest1451-stage-') as temporary:
        writes = stage(qmods, Path(temporary) / 'prepared')
        game = device.validate_game(patched_game)
        current = device.files(REMOTE + '/Modloader')
        packages = device.files(REMOTE + '/Packages/' + VERSION)
        allowed = {p for p in writes if p.startswith(REMOTE + '/Modloader/')}
        outside = {p for p in current if p.lower().endswith('.so') and p not in allowed and p != REMOTE + '/Modloader/libsl2.so'}
        if outside:
            raise ValueError('Other or misplaced native mods installed: ' + ', '.join(sorted(outside)))
        ids = {mod['id'] for _, _, mod, _ in qmods}
        old_roots = selected_registrations(device, packages, ids)
        old_files = {p for p in packages if any(p.startswith(r + '/') for r in old_roots)}
        deletes = old_files - writes.keys()
        affected = set(writes) | deletes
        before = {p: device.file_hash(p) for p in sorted(affected)}
        expected = {p: digest(local.read_bytes()) for p, local in writes.items()}
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]
        backup = backup_parent / stamp
        backup.mkdir(parents=True, exist_ok=False)
        receipt = {'target': VERSION, 'game': game, 'complete': False, 'status': 'backing_up',
                   'before': before, 'expected': expected, 'deletes': sorted(deletes), 'journal': [],
                   'packages': [{'id': entry['id'], 'version': entry['version'], 'qmod_sha256': entry['sha256'],
                                 'build_inputs_sha256': entry.get('verified_build_inputs_sha256')} for _, entry, _, _ in qmods]}
        def save_receipt():
            (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        save_receipt()
        # Back up and verify every affected existing file before device writes.
        for remote, pin in before.items():
            if pin is not None:
                local = backup.joinpath(*PurePosixPath(remote).relative_to(REMOTE).parts)
                device.pull(remote, local)
                if digest(local.read_bytes()) != pin or device.file_hash(remote) != pin:
                    raise ValueError('Backup verification failed; no device changes were made')
        stage_root = REMOTE + '/.modpack-staging-' + stamp
        if device.exists(stage_root):
            raise ValueError('Unexpected existing staging directory')
        created_dirs = {p for p in parent_dirs(affected, REMOTE) if not device.exists(p)}
        staging_paths, touched = set(), []
        receipt['status'] = 'staging'
        save_receipt()
        try:
            device.stop()
            device.mkdir(stage_root)
            for index, (remote, local) in enumerate(sorted(writes.items())):
                staged = stage_root + '/' + str(index)
                staging_paths.add(staged)
                device.push(local, staged)
                if device.file_hash(staged) != expected[remote]:
                    raise ValueError('Staged upload hash mismatch')
                device.chmod(staged)
            receipt['status'] = 'committing'
            save_receipt()
            for index, (remote, local) in enumerate(sorted(writes.items())):
                if device.file_hash(remote) != before[remote]:
                    raise ValueError('Destination changed since backup: ' + remote)
                device.mkdir(str(PurePosixPath(remote).parent))
                touched.append(remote)  # Before an ambiguously failing move.
                receipt['journal'].append(remote)
                save_receipt()
                device.move(stage_root + '/' + str(index), remote)
                if device.file_hash(remote) != expected[remote]:
                    raise ValueError('Committed file hash mismatch')
            for remote in sorted(deletes):
                if device.file_hash(remote) != before[remote]:
                    raise ValueError('Old registration changed since backup')
                touched.append(remote)
                receipt['journal'].append(remote)
                save_receipt()
                device.remove(remote)
            if device.files(REMOTE + '/Modloader') != current | allowed:
                raise ValueError('Modloader inventory changed during install')
            expected_packages = (packages - old_files) | {p for p in writes if '/Packages/' in p}
            if device.files(REMOTE + '/Packages/' + VERSION) != expected_packages:
                raise ValueError('Package inventory changed during install')
            if any(device.file_hash(p) != pin for p, pin in expected.items()):
                raise ValueError('Installed content changed before final verification')
            receipt['complete'] = True
            receipt['status'] = 'complete'
        except BaseException as failure:
            receipt['failure'] = str(failure)
            errors = []
            for index, remote in enumerate(reversed(touched)):
                try:
                    now, old = device.file_hash(remote), before[remote]
                    if now == old:
                        continue
                    ours = expected.get(remote) if remote in writes else None
                    if now != ours:
                        raise ValueError('Concurrent foreign change preserved: ' + remote)
                    if old is None:
                        device.remove(remote)
                    else:
                        saved = backup.joinpath(*PurePosixPath(remote).relative_to(REMOTE).parts)
                        if digest(saved.read_bytes()) != old:
                            raise ValueError('Local backup changed; refusing restoration')
                        restore = stage_root + '/restore-' + str(index)
                        staging_paths.add(restore)
                        device.push(saved, restore)
                        if device.file_hash(restore) != old:
                            raise ValueError('Rollback upload hash mismatch')
                        device.chmod(restore)
                        device.mkdir(str(PurePosixPath(remote).parent))
                        device.move(restore, remote)
                    if device.file_hash(remote) != old:
                        raise ValueError('Rollback verification failed')
                except BaseException as error:
                    errors.append(str(error))
            receipt['rollback_errors'] = errors
            receipt['status'] = 'rollback_incomplete' if errors else 'rolled_back'
            raise RuntimeError(f'Install failed; {receipt["status"]}. Backup/receipt: {backup}') from failure
        finally:
            cleanup_errors = []
            for remote in sorted(staging_paths):
                try:
                    device.remove(remote)
                except Exception as error:
                    cleanup_errors.append(str(error))
            obsolete_dirs = set()
            if receipt['complete']:
                for old_root in old_roots:
                    obsolete_dirs |= parent_dirs(deletes, old_root) | {old_root}
            for directory in sorted(created_dirs | obsolete_dirs | {stage_root}, key=len, reverse=True):
                try:
                    device.rmdir(directory)
                except Exception as error:
                    cleanup_errors.append(str(error))
            receipt['cleanup_errors'] = cleanup_errors
            save_receipt()
        print(f'Installed {len(qmods)} packages. Verified backup: {backup}')
        print('Start Beat Saber from the headset. Experimental compatibility remains limited.')
        return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='plan', choices=('download', 'verify', 'plan', 'install'))
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('modpack.json'))
    parser.add_argument('--qmods', type=Path, default=Path(__file__).with_name('qmods'))
    parser.add_argument('--profile', default='recommended')
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial')
    parser.add_argument('--backups', type=Path, default=Path(__file__).with_name('private-backups'))
    parser.add_argument('--build-receipt', type=Path)
    args = parser.parse_args(argv)
    manifest = json_load(args.manifest.read_text(encoding='utf-8'))
    if manifest['target'] != VERSION:
        raise ValueError('Wrong manifest target')
    if manifest.get('package', PACKAGE) != PACKAGE:
        raise ValueError('Wrong manifest game package')
    selected = select_packages(manifest, args.profile)
    if args.command == 'plan':
        print(json.dumps([{'id': x['id'], 'version': x['version'], 'source': 'download' if x.get('url') else 'local build'} for x in selected], indent=2))
        return
    receipt = json_load(args.build_receipt.read_text(encoding='utf-8')) if args.build_receipt else None
    qmods, missing = [], []
    for original in selected:
        if args.command == 'download' and not original.get('url'):
            print('Local build required: ' + original['id'])
            continue
        entry = effective_entry(original, receipt)
        try:
            path = fetch(args.qmods, entry) if args.command == 'download' else locate_qmod(args.qmods, entry)
            if not path.is_file():
                raise FileNotFoundError(f'Missing {entry["id"]}: {path.name}')
            mod, natives = read_qmod(path, entry)
            qmods.append((path, entry, mod, natives))
        except FileNotFoundError as error:
            missing.append(str(error))
    if missing:
        raise ValueError('\n'.join(missing) + '\nNo device changes were made. See BUILDING.md.')
    if args.command != 'download':
        validate_dependencies(qmods)
    if args.command == 'install':
        install(Device(args.adb, args.serial), qmods, args.backups, manifest.get('patched_game', {}))
    else:
        print(f'Verified {len(qmods)} pinned QMODs; no device changes were made.')


if __name__ == '__main__':
    main()
