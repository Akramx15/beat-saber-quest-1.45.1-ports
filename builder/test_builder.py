#!/usr/bin/env python3
"""Host-only integrity and portability checks. No network, builds, or device access."""
import hashlib, importlib.util, json, os, pathlib, tempfile, unittest, zipfile
import build, clang_ndk, bootstrap, integrity, subprocess
from unittest.mock import patch
class BuilderChecks(unittest.TestCase):
    def test_locked_recipe(self):build.verify_recipe()
    def test_native_manifest_accepts_each_single_load_folder(self):
        for key in ['modFiles','lateModFiles','libraryFiles']:
            with self.subTest(folder=key):build.verify_manifest({'binary':'libtest.so'},{key:['libtest.so']})
    def test_native_manifest_rejects_duplicate_missing_or_wrong_registration(self):
        cases=[{'lateModFiles':['libtest.so'],'libraryFiles':['libtest.so']},
               {'modFiles':['libtest.so','libtest.so']},{},{'modFiles':['wrong.so']},
               {'modFiles':'libtest.so'},{'libraryFiles':[None]}]
        for manifest in cases:
            with self.subTest(manifest=manifest),self.assertRaises(RuntimeError):build.verify_manifest({'binary':'libtest.so'},manifest)
    def test_receipt_inputs_change_on_dependency_change(self):
        name=next(iter(build.LOCK['targets']));before=build.fingerprint(name)
        old=build.LOCK['rust_toolchain'];build.LOCK['rust_toolchain']='changed'
        try:self.assertNotEqual(before,build.fingerprint(name))
        finally:build.LOCK['rust_toolchain']=old
    def test_informational_state_does_not_change_fingerprint(self):
        name=next(iter(build.LOCK['targets']));before=build.fingerprint(name)
        old=build.LOCK['state'];build.LOCK['state']='checked'
        try:self.assertEqual(before,build.fingerprint(name))
        finally:build.LOCK['state']=old
    def test_archive_path_guards(self):
        for name in ['/absolute','../escape','a/../../escape',r'a\escape','C:/escape']:
            with self.subTest(name=name),self.assertRaises(RuntimeError):build.safe_member(name)
        self.assertEqual(str(build.safe_member('shared/file.hpp')),'shared/file.hpp')
    def test_mod_archive_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);zpath=p/'input.zip'
            with zipfile.ZipFile(zpath,'w') as z:
                i=zipfile.ZipInfo('sym');i.external_attr=(0o120777<<16);z.writestr(i,'target')
            with self.assertRaises(RuntimeError):build.unzip(zpath,p/'out')
    def test_wrong_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'file';p.write_bytes(b'abc')
            with self.assertRaises(RuntimeError):build.check_file(p,'0'*64)
            build.check_file(p,hashlib.sha256(b'abc').hexdigest())
    def test_codegen_wrong_version_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError):build.verify_headers(pathlib.Path(td))
    def test_toolchain_symlink_inside_root(self):
        self.assertTrue(bootstrap.link_is_internal('root/bin/clang++','clang'))
        self.assertTrue(bootstrap.link_is_internal('root/lib/alias','../real'))
        for target in ['/elsewhere','../../elsewhere']:
            self.assertFalse(bootstrap.link_is_internal('root/bin/alias',target))
    def test_launcher_preserves_ndk_arguments(self):
        env={'BEAT_SABER_NDK':'/ndk','BEAT_SABER_CLANG':'cc22','BEAT_SABER_CLANGXX':'cxx22','BEAT_SABER_CXX26':'1','BEAT_SABER_BUILD_ROOT':'/build/اختبار'}
        cmd=clang_ndk.command(['/ndk/bin/clang++','--target=aarch64-linux-android24','--sysroot=/ndk/sysroot','-c','a.cpp','-std=c++23'],env)
        self.assertEqual(cmd[0],'cxx22');self.assertIn('--target=aarch64-linux-android24',cmd);self.assertIn('-std=c++2c',cmd)
        self.assertFalse(any('libunwind.a' in x for x in cmd))
        mapping=next(x for x in cmd if x.startswith('-ffile-prefix-map='))[len('-ffile-prefix-map='):].split('=')
        self.assertEqual(len(mapping[0].encode()),len(mapping[1].encode()))
    def test_launcher_adds_android_unwind_for_link(self):
        cmd=clang_ndk.command(['/ndk/bin/clang','a.o','-o','a.so'],{'BEAT_SABER_NDK':'/ndk'})
        self.assertEqual(cmd[0],'clang-22');self.assertIn('/ndk/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/18/lib/linux/aarch64/libunwind.a',cmd)
    def test_project_order_satisfies_declared_local_prerequisites(self):
        done=set()
        for name,t in build.LOCK['targets'].items():
            self.assertTrue(set(t.get('build_after',[]))<=done,name);done.add(name)
    def fixture_repo(self, root):
        root.mkdir(parents=True,exist_ok=True)
        (root/'shared').mkdir(exist_ok=True);(root/'shared/a.hpp').write_text('original\n')
        for cmd in [['git','init','-q'],['git','add','.'],['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','baseline']]:
            subprocess.run(cmd,cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    def test_dirty_unpatched_source_and_untracked_cpp_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);self.fixture_repo(p);integrity.git_tree(p)
            f=p/'shared/a.hpp';f.write_text('changed\n')
            with self.assertRaisesRegex(RuntimeError,'Changed pinned source'):integrity.git_tree(p)
            f.write_text('original\n');(p/'extra.cpp').write_text('void surprise() {}')
            with self.assertRaisesRegex(RuntimeError,'Unpinned additional'):integrity.git_tree(p)
    def test_declared_patch_checked_not_just_marker(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);self.fixture_repo(p);f=p/'shared/a.hpp';f.write_text('reviewed\n');expected={'shared/a.hpp':build.sha(f)}
            integrity.git_tree(p,expected);f.write_text('poisoned\n')
            with self.assertRaisesRegex(RuntimeError,'Patched source mismatch'):integrity.git_tree(p,expected)
    def test_overlay_source_reverified(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);commit=self.fixture_repo(p);name='_test_overlay';build.LOCK['targets'][name]={'commit':commit,'source_file_hashes':{}}
            try:
                build.verify_project_source(name,p);(p/'shared/a.hpp').write_text('poisoned\n')
                with self.assertRaisesRegex(RuntimeError,'Changed pinned source'):build.verify_project_source(name,p)
            finally:del build.LOCK['targets'][name]
    def test_full_header_tree_catches_nonsentinel_change(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);(p/'sentinel.hpp').write_text('ok');(p/'another.hpp').write_text('reviewed')
            original=integrity.tree_sha(p);(p/'another.hpp').write_text('wrong layout')
            self.assertNotEqual(original,integrity.tree_sha(p))
    def test_extra_external_library_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);target=p/'expected.so';target.write_bytes(b'ELF');ext=p/'extern';ext.mkdir();(ext/'a.so').symlink_to(target)
            integrity.exact_links(ext,{'a.so':target});(ext/'surprise.so').write_bytes(b'wrong')
            with self.assertRaisesRegex(RuntimeError,'Unexpected external'):integrity.exact_links(ext,{'a.so':target})
    def test_cached_local_native_hash_rechecked(self):
        with tempfile.TemporaryDirectory() as td:
            work=pathlib.Path(td);key='_test_native';dep=work/'dependency-sources'/key;commit=self.fixture_repo(dep)
            build.LOCK['dependencies'][key]={'id':'beatsaber-hook','version':'test','repo':'unused','commit':commit,'shared_dir':'shared'}
            build.LOCK['targets']['_test_project']={};project=work/'sources/_test_project';project.mkdir(parents=True)
            library=work/'core-qmods/native/beatsaber-hook-1451/libbeatsaber-hook.so';library.parent.mkdir(parents=True);library.write_bytes(b'wrong cached native')
            args=__import__('argparse').Namespace(qpm_cache=None)
            try:
                with self.assertRaisesRegex(RuntimeError,'Integrity mismatch'):build.dependency(key,project,args,work)
            finally:del build.LOCK['dependencies'][key];del build.LOCK['targets']['_test_project']
    def test_poisoned_archive_extraction_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            work=pathlib.Path(td);key='_test_archive';dep=work/'dependency-sources'/key;dep.mkdir(parents=True);(dep/'a.hpp').write_text('good');digest=integrity.tree_sha(dep)
            archive=work/'downloads'/('_test_archive.zip');archive.parent.mkdir();
            with zipfile.ZipFile(archive,'w') as z:z.writestr('a.hpp','good')
            build.LOCK['dependencies'][key]={'id':'archive','version':'test','shared_dir':'shared','archive':{'url':'unused','sha256':build.sha(archive)},'archive_tree_sha256':digest};build.LOCK['targets']['_test_project']={}
            (dep/'a.hpp').write_text('poisoned')
            try:
                with self.assertRaisesRegex(RuntimeError,'Changed extracted dependency'):build.dependency(key,work/'sources/_test_project',__import__('argparse').Namespace(qpm_cache=None),work)
            finally:del build.LOCK['dependencies'][key];del build.LOCK['targets']['_test_project']
    def test_same_dependency_preparation_serialized_between_processes(self):
        import multiprocessing, time
        ctx=multiprocessing.get_context('fork')
        with tempfile.TemporaryDirectory() as td:
            work=pathlib.Path(td);events=work/'events';start=ctx.Event()
            def inner(*args):
                with events.open('a') as f:f.write('begin\n')
                time.sleep(0.08)
                with events.open('a') as f:f.write('end\n')
            def worker():
                start.wait(3);build.dependency('same-dependency',work,None,work)
            with patch.object(build,'prepare_dependency',inner):
                children=[ctx.Process(target=worker) for _ in range(2)]
                for child in children:child.start()
                start.set()
                for child in children:child.join(5);self.assertEqual(child.exitcode,0)
            self.assertEqual(events.read_text().splitlines(),['begin','end','begin','end'])
    def test_identical_native_import_keeps_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'native.so';build.install_bytes(p,b'exact')
            os.utime(p,ns=(1_000_000_000,1_000_000_000));build.install_bytes(p,b'exact')
            self.assertEqual(p.stat().st_mtime_ns,1_000_000_000)
    def test_native_import_replaces_link_without_writing_outside(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);outside=root/'outside';outside.write_bytes(b'keep')
            dest=root/'native.so';dest.symlink_to(outside);build.install_bytes(dest,b'new')
            self.assertEqual(outside.read_bytes(),b'keep');self.assertFalse(dest.is_symlink());self.assertEqual(dest.read_bytes(),b'new')
if __name__=='__main__':unittest.main(verbosity=2)
