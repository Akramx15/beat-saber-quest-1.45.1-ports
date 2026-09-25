#!/usr/bin/env python3
"""Download optional pinned Android/LLVM toolchains. No administrator access."""
import argparse, json, os, pathlib, shlex, shutil, subprocess, tarfile
from build import LOCK, fetch, safe_member, unzip
from integrity import tree_sha

def checked_install(folder,archive_sha,extract):
    stamp=folder.parent/(folder.name+'.tree.json')
    if folder.exists():
        if not stamp.exists():raise RuntimeError('Existing toolchain has no verified bootstrap record; choose a new --directory')
        record=json.loads(stamp.read_text())
        if record.get('archive_sha256')!=archive_sha or record.get('tree_sha256')!=tree_sha(folder):raise RuntimeError('Cached toolchain was modified; choose a new --directory')
    else:
        extract()
        stamp.write_text(json.dumps({'archive_sha256':archive_sha,'tree_sha256':tree_sha(folder)},indent=2)+'\n')

def link_is_internal(member,target):
    if pathlib.PurePosixPath(target).is_absolute():return False
    depth=0
    for part in (pathlib.PurePosixPath(member).parent/pathlib.PurePosixPath(target)).parts:
        if part=='..':depth-=1
        elif part not in ['.','']:depth+=1
        if depth<1:return False
    return True

def extract_ndk(archive,dest):
    with __import__('zipfile').ZipFile(archive) as z:
        links=[]
        for i in z.infolist():
            safe_member(i.filename)
            if (i.external_attr>>16)&0o170000==0o120000:
                target=z.read(i).decode()
                if not link_is_internal(i.filename,target):raise RuntimeError('Escaping toolchain symlink')
                links.append((i.filename,target))
            else:
                z.extract(i,dest)
                mode=(i.external_attr>>16)&0o777
                if mode and not i.is_dir():(dest/i.filename).chmod(mode)
        for name,target in links:
            p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.symlink_to(target)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=pathlib.Path,default=pathlib.Path.home()/'.cache/bs1451-tools')
    p.add_argument('--ndk',action='store_true');p.add_argument('--llvm',action='store_true');a=p.parse_args()
    dest=a.directory.expanduser().resolve();dest.mkdir(parents=True,exist_ok=True)
    if not(a.ndk or a.llvm):p.error('Choose --ndk and/or --llvm (approximately 0.66GB / 1.94GB downloads)')
    values={}
    if a.ndk:
        pin=LOCK['tools']['ndk'];archive=fetch(pin,dest/'downloads/android-ndk-r27c-linux.zip')
        folder=dest/'android-ndk-r27c'
        checked_install(folder,pin['sha256'],lambda:extract_ndk(archive,dest))
        values['BEAT_SABER_NDK']=str(folder)
    if a.llvm:
        pin=LOCK['tools']['llvm'];archive=fetch(pin,dest/'downloads/LLVM-22.1.8-Linux-X64.tar.xz')
        folder=dest/'LLVM-22.1.8-Linux-X64'
        def extract_llvm():
            with tarfile.open(archive) as t:
                # Trusted SHA-pinned official archive; still reject escaping link/member names.
                for member in t.getmembers():
                    safe_member(member.name)
                    if member.issym():
                        if not link_is_internal(member.name,member.linkname):raise RuntimeError('Unsafe toolchain archive link')
                    elif member.islnk():
                        safe_member(member.linkname)
                        if pathlib.PurePosixPath(member.linkname).parts[0]!=pathlib.PurePosixPath(member.name).parts[0]:raise RuntimeError('Unsafe toolchain archive hardlink')
                t.extractall(dest,filter='data')
        checked_install(folder,pin['sha256'],extract_llvm)
        values.update(BEAT_SABER_CLANG=str(folder/'bin/clang'),BEAT_SABER_CLANGXX=str(folder/'bin/clang++'),BEAT_SABER_LLVM_AR=str(folder/'bin/llvm-ar'),BEAT_SABER_LLVM_RANLIB=str(folder/'bin/llvm-ranlib'))
    envfile=dest/'environment.sh'
    # Preserve a previous bootstrap of the other toolchain.
    state=dest/'environment.json';existing=json.loads(state.read_text()) if state.exists() else {};existing.update(values)
    state.write_text(json.dumps(existing,indent=2)+'\n')
    envfile.write_text(''.join('export '+k+'='+shlex.quote(v)+'\n' for k,v in existing.items()))
    print('Run: source '+shlex.quote(str(envfile)))
if __name__=='__main__':main()
