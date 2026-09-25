"""Offline security and transaction tests. Never starts ADB or contacts a headset."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shlex
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manage_modpack', ROOT / 'manage_modpack.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
R = m.REMOTE


def elf(tag=b''):
    data = bytearray(64)
    data[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HH', data, 16, 3, 183)
    struct.pack_into('<H', data, 52, 64)
    return bytes(data) + tag


def make_qmod(directory, ident='A', version='2.0.0', deps=(), extra=(), native=None, overrides=None):
    name = 'lib' + ident + '.so'
    native = elf(b'new-' + ident.encode()) if native is None else native
    mod = {'id': ident, 'version': version, 'packageId': m.PACKAGE, 'packageVersion': m.VERSION,
           'modloader': 'Scotland2', 'modFiles': [name], 'dependencies': list(deps)}
    mod.update(overrides or {})
    path = directory / (ident + '.qmod')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mod.json', json.dumps(mod))
        z.writestr(name, native)
        for item, data in extra:
            if isinstance(item, str):
                # Encode the intended raw archive spelling on every OS, even
                # where ZipInfo's constructor would normalize or truncate it.
                info = zipfile.ZipInfo()
                info.filename = info.orig_filename = item
                z.writestr(info, data)
            else:
                z.writestr(item, data)
    entry = {'id': ident, 'version': version, 'filename': path.name,
             'sha256': m.digest(path.read_bytes()), 'native_sha256': {name: m.digest(native)}, 'dependencies': list(deps)}
    return path, entry


def package_tuple(pair):
    path, entry = pair
    mod, natives = m.read_qmod(path, entry)
    return path, entry, mod, natives


class MockADB(m.Device):
    """In-memory ADB filesystem adapter exercising the real install transaction."""
    def __init__(self):
        self.data = {R + '/Modloader/libsl2.so': elf(b'loader'),
                     R + '/Modloader/early_mods/libA.so': elf(b'old'),
                     R + '/Packages/' + m.VERSION + '/A_v1.0.0/mod.json': json.dumps({'id':'A','version':'1.0.0'}).encode(),
                     R + '/Packages/' + m.VERSION + '/A_v1.0.0/libA.so': elf(b'old'),
                     R + '/Configs/A.json': b'user config', R + '/CustomLevels/own/song.egg': b'own song',
                     '/data/user/0/' + m.PACKAGE + '/files/PlayerData.dat': b'user save',
                     '/data/app/owner/base.apk': b'owner apk'}
        self.initial = copy.deepcopy(self.data)
        self.directories = m.parent_dirs(self.data, '/sdcard') | {R, R+'/Modloader', R+'/Packages'}
        self.events = []
        self.fail_move = None
        self.moves = 0
        self.fail_push = None
        self.pushes = 0
        self.corrupt_backup = False
        self.foreign_change = False
        self.fail_delete = False
        self.link = False
        self.bad_stage = False

    def validate_game(self, pins):
        self.events.append(('validate',))
        return {'verified': True}

    def exists(self, path):
        return path in self.data or path in self.directories

    def no_links(self, path):
        if self.link:
            raise ValueError('Remote symlink rejected')

    def files(self, path):
        self.no_links(path)
        return {p for p in self.data if p.startswith(path + '/')}

    def file_hash(self, path):
        return m.digest(self.data[path]) if path in self.data else None

    def pull(self, remote, local):
        self.events.append(('pull', remote))
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(b'corrupt' if self.corrupt_backup else self.data[remote])

    def read_bytes(self, command):
        args = shlex.split(command)
        assert args[0] == 'cat', command
        return self.data[args[1]]

    def mkdir(self, path):
        self.events.append(('mkdir', path))
        self.directories |= m.parent_dirs([path + '/placeholder'], '/sdcard')

    def push(self, local, remote):
        self.events.append(('push', remote))
        self.pushes += 1
        self.data[remote] = b'partial' if self.pushes == self.fail_push or self.bad_stage else local.read_bytes()
        if self.pushes == self.fail_push:
            raise RuntimeError('Mock ADB disconnected mid-push')

    def move(self, source, destination):
        self.events.append(('move', source, destination))
        self.moves += 1
        self.data[destination] = self.data.pop(source)
        if self.moves == self.fail_move:
            if self.foreign_change:
                self.data[R + '/Modloader/early_mods/libA.so'] = b'foreign update'
            raise RuntimeError('Mock ADB lost reply after successful move')

    def remove(self, remote):
        self.events.append(('remove', remote))
        self.data.pop(remote, None)
        if self.fail_delete and '/A_v1.0.0/' in remote:
            self.fail_delete = False
            raise RuntimeError('Mock deletion succeeded but response failed')

    def rmdir(self, remote):
        self.events.append(('rmdir', remote))
        if not any(p.startswith(remote + '/') for p in self.data):
            self.directories.discard(remote)

    def chmod(self, remote):
        self.events.append(('chmod', remote))

    def stop(self):
        self.events.append(('stop',))

    def mutations(self):
        return [e for e in self.events if e[0] not in ('pull', 'validate')]


class PatchedAPKMock(m.Device):
    def __init__(self):
        self.bootstrap, self.loader = elf(b'bootstrap'), elf(b'loader')
        self.marker = {'modloaderName':'Scotland2','modloaderVersion':'0.1.7'}
        self.version = m.VERSION
        self.fallback = False
        self.pulled = None

    def pins(self):
        return {'apk_libmain_sha256': m.digest(self.bootstrap), 'loader_sha256': m.digest(self.loader)}

    def shell(self, command, check=True):
        if command.startswith('dumpsys'): return '  versionName=' + self.version + '\n  versionCode=3071 minSdk=24\n'
        if command.startswith('pm path'): return 'package:/data/app/owner/base.apk'
        raise AssertionError(command)

    def read_bytes(self, command):
        args = shlex.split(command)
        if args[0] == 'unzip':
            if self.fallback: raise subprocess.CalledProcessError(1, args)
            return json.dumps(self.marker).encode() if args[-1] == 'modded.json' else self.bootstrap
        if args[0] == 'cat': return self.loader
        raise AssertionError(command)

    def no_links(self, path): pass

    def pull(self, remote, local):
        self.pulled = local
        with zipfile.ZipFile(local, 'w') as z:
            z.writestr('modded.json', json.dumps(self.marker))
            z.writestr('lib/arm64-v8a/libmain.so', self.bootstrap)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.qmods = [package_tuple(make_qmod(self.root))]
        self.device = MockADB()

    def tearDown(self): self.temp.cleanup()

    def run_install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return m.install(self.device, self.qmods, self.root/'backups', {})

    def receipt(self):
        return json.loads(next((self.root/'backups').glob('*/receipt.json')).read_text())

    def test_success_replaces_old_registration_preserves_user_files(self):
        backup = self.run_install()
        self.assertTrue(self.receipt()['complete'])
        self.assertFalse(any('/A_v1.0.0/' in p for p in self.device.data))
        self.assertIn(R+'/Packages/'+m.VERSION+'/A_v2.0.0/mod.json', self.device.data)
        for p, b in self.device.initial.items():
            if '/Modloader/early_mods/' not in p and '/Packages/' not in p:
                self.assertEqual(self.device.data[p], b)
        for p, pin in self.receipt()['before'].items():
            if pin:
                local = backup.joinpath(*PurePosixPath(p).relative_to(R).parts)
                self.assertEqual(m.digest(local.read_bytes()), pin)
        self.assertFalse(any('.modpack-staging-' in p for p in self.device.data))
        for event in self.device.mutations():
            if len(event)>1:
                self.assertTrue(event[1].startswith(R+'/Modloader/') or event[1].startswith(R+'/Packages')
                                or event[1].startswith(R+'/.modpack-staging-'), event)

    def test_ambiguous_partial_commit_rolls_back_original_bytes(self):
        self.device.fail_move = 2
        with self.assertRaisesRegex(RuntimeError, 'rolled_back'): self.run_install()
        self.assertEqual(self.device.data, self.device.initial)
        self.assertEqual(self.receipt()['status'], 'rolled_back')

    def test_failure_after_deleting_registration_restores_it(self):
        self.device.fail_delete = True
        with self.assertRaisesRegex(RuntimeError, 'rolled_back'): self.run_install()
        self.assertEqual(self.device.data, self.device.initial)

    def test_partial_push_never_changes_active_files(self):
        self.device.fail_push = 2
        with self.assertRaisesRegex(RuntimeError, 'rolled_back'): self.run_install()
        self.assertEqual(self.device.data, self.device.initial)
        self.assertEqual(self.receipt()['journal'], [])

    def test_bad_stage_hash_never_commits(self):
        self.device.bad_stage = True
        with self.assertRaisesRegex(RuntimeError, 'rolled_back'): self.run_install()
        self.assertEqual(self.device.data, self.device.initial)
        self.assertEqual(self.device.moves, 0)

    def test_concurrent_foreign_change_is_not_overwritten_by_rollback(self):
        self.device.fail_move, self.device.foreign_change = 2, True
        with self.assertRaisesRegex(RuntimeError, 'rollback_incomplete'): self.run_install()
        self.assertEqual(self.device.data[R+'/Modloader/early_mods/libA.so'], b'foreign update')
        self.assertTrue(self.receipt()['rollback_errors'])
        self.assertFalse(any('/A_v2.0.0/' in p for p in self.device.data))

    def test_backup_failure_is_before_any_device_mutation(self):
        self.device.corrupt_backup = True
        with self.assertRaisesRegex(ValueError, 'Backup verification'): self.run_install()
        self.assertEqual(self.device.mutations(), [])
        self.assertEqual(self.device.data, self.device.initial)

    def test_unknown_native_rejected_before_any_device_mutation(self):
        self.device.data[R+'/Modloader/mods/libOther.so'] = elf()
        with self.assertRaisesRegex(ValueError, 'Other or misplaced'): self.run_install()
        self.assertEqual(self.device.mutations(), [])

    def test_same_name_wrong_folder_is_not_silently_mixed(self):
        self.device.data[R+'/Modloader/mods/libA.so'] = elf()
        with self.assertRaisesRegex(ValueError, 'Other or misplaced'): self.run_install()
        self.assertEqual(self.device.mutations(), [])

    def test_remote_symlink_rejected_before_mutations(self):
        self.device.link = True
        with self.assertRaisesRegex(ValueError, 'symlink'): self.run_install()
        self.assertEqual(self.device.mutations(), [])

    def test_new_foreign_native_during_commit_survives_rollback(self):
        original=self.device.files
        count=0
        foreign=R+'/Modloader/mods/libForeign.so'
        def files(path):
            nonlocal count
            if path==R+'/Modloader':
                count+=1
                if count==2:self.device.data[foreign]=elf(b'foreign')
            return original(path)
        self.device.files=files
        with self.assertRaisesRegex(RuntimeError,'rolled_back'):self.run_install()
        expected=dict(self.device.initial);expected[foreign]=elf(b'foreign')
        self.assertEqual(self.device.data,expected)

    def test_duplicate_casefolded_package_ids_rejected(self):
        manifest={'profiles':{'p':['A']},'packages':[{'id':'A','version':'1.0.0'},{'id':'a','version':'1.0.0'}]}
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.select_packages(manifest,'p')

    def test_tampered_qmod_before_install_is_rejected_without_adb(self):
        self.qmods[0][0].write_bytes(b'tampered')
        with self.assertRaises(ValueError): self.run_install()
        self.assertEqual(self.device.events, [])

    def test_actual_qmod_dependency_missing_despite_manifest_omission(self):
        p,e=make_qmod(self.root, deps=[{'id':'B','version':'^1.0.0'}]); e['dependencies']=[]
        self.qmods=[package_tuple((p,e))]
        with self.assertRaisesRegex(ValueError, 'Unsatisfied dependency'): self.run_install()
        self.assertEqual(self.device.events, [])

    def test_dependency_range_is_checked(self):
        a=package_tuple(make_qmod(self.root,deps=[{'id':'B','version':'^1.0.0'}]))
        b=package_tuple(make_qmod(self.root,ident='B',version='2.0.0'))
        with self.assertRaisesRegex(ValueError, 'Unsatisfied'): m.validate_dependencies([a,b])
        b=package_tuple(make_qmod(self.root,ident='B',version='1.2.3+local.1451'))
        m.validate_dependencies([a,b])
        self.assertFalse(m.satisfies('0.6.0','^0.5.8'))
        self.assertTrue(m.satisfies('0.5.9+local.1451','^0.5.8'))

    def test_semver_prerelease_order_and_range_gates(self):
        v='0.25.5-1.45.1-dev.3'
        self.assertTrue(m.satisfies(v,'='+v))
        self.assertTrue(m.satisfies(v,'^0.25.5-1.45.1-dev.2'))
        self.assertFalse(m.satisfies(v,'^0.25.0'))
        self.assertFalse(m.satisfies(v,'*'))
        self.assertTrue(m.satisfies('0.25.5','^0.25.5-1.45.1-dev.3'))
        self.assertTrue(m.version_tuple('1.0.0-alpha.2') < m.version_tuple('1.0.0-alpha.11'))
        self.assertTrue(m.version_tuple('1.0.0-alpha.11') < m.version_tuple('1.0.0-alpha.beta'))
        with self.assertRaises(ValueError):m.version_tuple('1.0.0-alpha.01')

    def test_untargeted_and_legacy_packages_need_explicit_approval(self):
        p,e=make_qmod(self.root,overrides={'packageVersion':None})
        with self.assertRaisesRegex(ValueError,'missing game version'):m.read_qmod(p,e)
        e['verified_untargeted_library']=True
        m.read_qmod(p,e)
        p,e=make_qmod(self.root,overrides={'packageVersion':'1.29.0_4711'})
        with self.assertRaisesRegex(ValueError,'game version'):m.read_qmod(p,e)
        e['allowed_package_versions']=['1.29.0_4711']
        m.read_qmod(p,e)

    def test_local_receipt_requires_matching_pinned_inputs(self):
        entry=dict(self.qmods[0][1],local_build={'inputs_sha256':'1'*64})
        receipt={'packages':{'A':{'version':'2.0.0','inputs_sha256':'2'*64,'qmod_sha256':'3'*64,'native_sha256':{'libA.so':'4'*64}}}}
        with self.assertRaisesRegex(ValueError,'receipt'): m.effective_entry(entry,receipt)
        receipt['packages']['A']['inputs_sha256']='1'*64
        self.assertEqual(m.effective_entry(entry,receipt)['sha256'],'3'*64)

    def test_receipt_cannot_override_download_pin(self):
        entry=dict(self.qmods[0][1],url='https://example.test/A.qmod',local_build={'inputs_sha256':'1'*64})
        receipt={'packages':{'A':{'version':'2.0.0','inputs_sha256':'1'*64,'qmod_sha256':'3'*64,'native_sha256':{'libA.so':'4'*64}}}}
        self.assertEqual(m.effective_entry(entry,receipt)['sha256'],entry['sha256'])

    def test_archive_traversal_case_alias_and_symlink_rejected(self):
        link=zipfile.ZipInfo('link'); link.external_attr=(0o120777<<16)
        for item in ('../outside','/absolute','a\\b','C:stream','a/./b','CON','a.','bad\nname','bad\x00hidden','MOD.JSON',link):
            with self.subTest(item=str(item)):
                p,e=make_qmod(self.root,extra=[(item,b'x')])
                if isinstance(item, str):
                    self.assertIn(item.encode('utf-8'), p.read_bytes())
                with self.assertRaises(ValueError): m.read_qmod(p,e)

    def test_archive_original_name_checked_before_windows_normalization(self):
        p,e=make_qmod(self.root,extra=[('a\\b',b'x')])
        self.assertIn(b'a\\b',p.read_bytes())
        original_init=zipfile.ZipInfo.__init__
        normalized=[]
        def windows_init(info,*args,**kwargs):
            original_init(info,*args,**kwargs)
            info.filename=info.filename.replace('\\','/')
            if info.orig_filename=='a\\b':
                normalized.append(info.filename)
        with patch.object(zipfile.ZipInfo,'__init__',windows_init):
            with self.assertRaisesRegex(ValueError,'Unsafe or normalized'):
                m.read_qmod(p,e)
        self.assertEqual(normalized,['a/b'])

    def test_archive_normal_forward_slash_member_accepted(self):
        p,e=make_qmod(self.root,extra=[('assets/safe.txt',b'x')])
        mod,_=m.read_qmod(p,e)
        self.assertEqual(mod['id'],'A')

    def test_wrong_arch_and_truncated_elf_rejected(self):
        values=[b'\x7fELF',elf()[:63]]
        arm32=bytearray(elf()); arm32[4]=1; values.append(arm32)
        x86=bytearray(elf()); struct.pack_into('<H',x86,18,62); values.append(x86)
        for binary in values:
            p,e=make_qmod(self.root,native=binary)
            with self.assertRaisesRegex(ValueError,'ARM64'): m.read_qmod(p,e)

    def test_missing_native_pin_and_filecopies_rejected(self):
        p,e=make_qmod(self.root); e['native_sha256']={}
        with self.assertRaises(ValueError): m.read_qmod(p,e)
        p,e=make_qmod(self.root,overrides={'fileCopies':[{'name':'x','destination':'/sdcard/x'}]})
        with self.assertRaisesRegex(ValueError,'Auxiliary'):m.read_qmod(p,e)

    def test_unpatched_wrong_version_and_wrong_bootstrap_rejected(self):
        d=PatchedAPKMock(); pins=d.pins()
        self.assertEqual(d.validate_game(pins)['modded']['modloaderName'],'Scotland2')
        d.marker['modloaderVersion']=None
        d.validate_game(pins)
        d.marker={}
        with self.assertRaisesRegex(ValueError,'marker'):d.validate_game(pins)
        d=PatchedAPKMock();d.version=m.VERSION+'-other'
        with self.assertRaisesRegex(ValueError,'requires'):d.validate_game(pins)
        d=PatchedAPKMock();d.bootstrap=elf(b'wrong')
        with self.assertRaisesRegex(ValueError,'bootstrap'):d.validate_game(pins)
        d=PatchedAPKMock();d.loader=elf(b'wrong')
        with self.assertRaisesRegex(ValueError,'loader'):d.validate_game(pins)

    def test_private_apk_pull_fallback_is_deleted(self):
        d=PatchedAPKMock();d.fallback=True
        d.validate_game(d.pins())
        self.assertFalse(d.pulled.exists())
        self.assertFalse(d.pulled.parent.exists())

    def test_plan_and_verify_never_construct_adb(self):
        manifest={'target':m.VERSION,'packages':[self.qmods[0][1]],'profiles':{'recommended':['A']}}
        path=self.root/'modpack.json';path.write_text(json.dumps(manifest))
        with patch.object(m,'Device',side_effect=AssertionError('ADB must not run')):
            with contextlib.redirect_stdout(io.StringIO()):
                m.main(['--manifest',str(path)])
                m.main(['verify','--manifest',str(path),'--qmods',str(self.root)])

    def test_exec_out_passes_raw_shell_script_without_double_quoting(self):
        d=object.__new__(m.Device);d.command=['adb','-s','serial']
        command="cat '/sdcard/path with spaces/file.so'"
        with patch.object(subprocess,'check_output',return_value=b'ok') as call:
            self.assertEqual(d.read_bytes(command),b'ok')
        call.assert_called_once_with(['adb','-s','serial','exec-out','sh','-c',command])

    def test_download_is_local_only_and_never_constructs_adb(self):
        entry=dict(self.qmods[0][1],url='https://example.test/A.qmod')
        manifest={'target':m.VERSION,'packages':[entry],'profiles':{'recommended':['A']}}
        path=self.root/'modpack.json';path.write_text(json.dumps(manifest))
        with patch.object(m,'Device',side_effect=AssertionError('ADB must not run')):
            with contextlib.redirect_stdout(io.StringIO()):
                m.main(['download','--manifest',str(path),'--qmods',str(self.root)])


if __name__ == '__main__': unittest.main()
