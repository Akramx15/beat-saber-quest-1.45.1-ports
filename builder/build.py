#!/usr/bin/env python3
"""Experimental exact-version Quest native builder. Never accesses a device."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, pathlib, platform, re, shutil, subprocess, sys, tempfile, zipfile
import fcntl
from integrity import git_tree, tree_sha, exact_links
ROOT=pathlib.Path(__file__).resolve().parent
LOCK=json.loads((ROOT/'build-lock.json').read_text())
LOCAL={'beatsaber-hook':('beatsaber-hook-1451','libbeatsaber-hook.so'),'songcore':('songcore-1451','libsongcore.so'),'bsml':('bsml-1451','libbsml.so'),'metacore':('metacore-1451','libmetacore.so'),'metacore-bs':('metacore-bs-1451','libmetacore-bs.so'),'custom-json-data':('custom-json-data-1451','libcustom-json-data.so'),'tracks':('tracks-1451','libtracks.so'),'playlistcore':('playlistcore-1451','libplaylistcore.so')}

def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def fingerprint(name):
    # One complete locked closure; informational validation/state fields are excluded.
    data=json.loads(json.dumps(LOCK))
    for k in ['state','validation']:data.pop(k,None)
    for t in data['targets'].values():
        for k in ['inputs_sha256','state','previous_local_native_sha256']:t.pop(k,None)
    return hashlib.sha256(canonical({'target':name,'recipe':data})).hexdigest()

def verify_recipe():
    for rel,h in LOCK['recipe_files'].items():check_file(ROOT/rel,h)
    for pin in [LOCK['generator']['patch'],*LOCK['generator'].get('additional_patches',[])]:check_file(ROOT/pin['path'],pin['sha256'])
    for name,t in LOCK['targets'].items():
        if fingerprint(name)!=t['inputs_sha256']:raise RuntimeError('Recipe fingerprint mismatch: '+name)
        check_file(ROOT/t['patch']['path'],t['patch']['sha256'])
        check_file(ROOT/t['manifest'],t['manifest_sha256'])
        verify_manifest(t,json.loads((ROOT/t['manifest']).read_text()))
        for pin in t.get('dependency_patches',{}).values():check_file(ROOT/pin['path'],pin['sha256'])
def verify_manifest(target,manifest):
    natives=[]
    for key in ['modFiles','lateModFiles','libraryFiles']:
        entries=manifest.get(key,[])
        if not isinstance(entries,list) or any(not isinstance(x,str) for x in entries):raise RuntimeError('Native manifest entries must be arrays of filenames: '+key)
        natives.extend(entries)
    if natives!=[target['binary']]:raise RuntimeError('Manifest must register its one built native exactly once: '+target['binary'])
def run(argv,cwd=None,env=None):
    print('+',' '.join(map(str,argv)),flush=True)
    subprocess.run(list(map(str,argv)),cwd=cwd,env=env,check=True)
def output(argv,cwd=None):return subprocess.check_output(list(map(str,argv)),cwd=cwd,text=True).strip()
def check_file(p,expected):
    if not pathlib.Path(p).is_file() or sha(p)!=expected:raise RuntimeError(f'Integrity mismatch: {p}')
def write_json(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def install_bytes(dest,blob):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_file() and not dest.is_symlink() and sha(dest)==hashlib.sha256(blob).hexdigest():return
    fd,tmp=tempfile.mkstemp(prefix='.native-',dir=dest.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def record_package(receipt,id,entry):
    with (receipt.parent/'.receipt.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        data=json.loads(receipt.read_text()) if receipt.exists() else {'schema':1,'target_game':LOCK['target_game'],'packages':{}}
        if data.get('schema')!=1 or data.get('target_game')!=LOCK['target_game']:raise RuntimeError('Incompatible existing build receipt')
        data['packages'][id]=entry
        fd,tmp=tempfile.mkstemp(prefix='.receipt-',dir=receipt.parent)
        try:
            with os.fdopen(fd,'w') as f:
                f.write(json.dumps(data,indent=2)+'\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,receipt)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
def safe_member(name):
    p=pathlib.PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise RuntimeError('Unsafe archive member: '+name)
    return p

def unzip(archive,dest):
    dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for i in z.infolist():
            safe_member(i.filename)
            if (i.external_attr >>16)&0o170000==0o120000:raise RuntimeError('Archive symlinks are not accepted')
        z.extractall(dest)

def fetch(pin,dest):
    if dest.exists():check_file(dest,pin['sha256']);return dest
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+'.partial')
    try:
        run(['curl','--fail','--location','--retry','3','--user-agent','qpm/1.5.11',pin['url'],'--output',tmp])
        check_file(tmp,pin['sha256']);tmp.replace(dest)
    finally:
        if tmp.exists():tmp.unlink()
    return dest

def clone(repo,commit,dest,cache=None,submodules=True):
    if dest.exists():
        if output(['git','rev-parse','HEAD'],dest)!=commit:raise RuntimeError(f'Wrong checkout in {dest}; choose a new work directory')
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    if cache and (cache/'.git').exists():
        run(['git','clone','--no-hardlinks','--no-checkout',cache,dest]);run(['git','remote','set-url','origin',repo],dest)
    else:
        run(['git','init',dest]);run(['git','remote','add','origin',repo],dest)
    if subprocess.run(['git','cat-file','-e',commit+'^{commit}'],cwd=dest,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        run(['git','fetch','--depth','1','origin',commit],dest)
    run(['git','checkout','--detach',commit],dest)
    if submodules:run(['git','submodule','update','--init','--recursive','--depth','1'],dest)
    # Avoid embedding a personal global Git identity in projects which generate git_info.h.
    run(['git','config','user.name','Local builder'],dest)

def apply_patch(dest,pin):
    p=ROOT/pin['path'];check_file(p,pin['sha256'])
    if p.stat().st_size==0:return
    marker=dest/('.builder-patch-'+pin['sha256'])
    if marker.exists():return
    run(['git','apply','--check','--unidiff-zero',p],dest)
    run(['git','apply','--unidiff-zero',p],dest);marker.write_text(pin['sha256']+'\n')

def link(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_symlink():
        if dest.resolve()==source.resolve():return
        dest.unlink()
    elif dest.exists():raise RuntimeError(f'Refusing to overwrite existing non-link: {dest}')
    dest.symlink_to(source.resolve(),target_is_directory=source.is_dir())

def doctor(args):
    if platform.system()!='Linux' or platform.machine() not in ['x86_64','AMD64']:raise RuntimeError('Use x86_64 Linux or Ubuntu under Windows WSL2')
    for tool in ['git','curl','cmake','ninja','python3']:
        if not shutil.which(tool):raise RuntimeError('Missing tool: '+tool)
    ndk=pathlib.Path(os.environ.get('BEAT_SABER_NDK','')).expanduser().resolve()
    props=ndk/'source.properties'
    if not props.exists() or not re.search(r'Pkg.Revision\s*=\s*'+re.escape(LOCK['ndk_revision'])+r'\s*$',props.read_text(),re.M):raise RuntimeError('BEAT_SABER_NDK must name Android NDKr27c ('+LOCK['ndk_revision']+')')
    for env,name in [('BEAT_SABER_CLANG','clang-22'),('BEAT_SABER_CLANGXX','clang++-22')]:
        cmd=os.environ.get(env,name)
        if not shutil.which(cmd) or not re.search(r'clang version 22\.1\.8\b',output([cmd,'--version'])):raise RuntimeError(env+' must select Clang22.1.8')
        lld=pathlib.Path(shutil.which(cmd)).resolve().parent/'ld.lld'
        if not lld.is_file() or not re.search(r'LLD 22\.1\.8\b',output([lld,'--version'])):raise RuntimeError('Install the matching LLVM22.1.8 linker beside Clang: '+str(lld))
    if args.rust or args.command=='generate' or args.apk or args.command=='build' and (not args.targets or 'Tracks' in args.targets):
        for tool in ['cargo','rustup']:
            if not shutil.which(tool):raise RuntimeError('Missing '+tool+'; install Rust and source "$HOME/.cargo/env"')
        run(['rustup','run',LOCK['rust_toolchain'],'rustc','--version'])
    return ndk

def verify_headers(p):
    for rel,h in LOCK['headers_sentinels'].items():check_file(p/rel,h)
    digest=tree_sha(p)
    if digest not in LOCK['headers_tree_sha256']:raise RuntimeError('Complete generated API tree does not match this recipe: '+str(p))
    return p

def headers(args,work):
    p=pathlib.Path(args.headers).expanduser().resolve() if args.headers else work/'toolchain/codegen/include'
    verify_headers(p)
    if p!=work/'toolchain/codegen/include':link(p,work/'toolchain/codegen/include')
    return p

def generate(args,work):
    if not args.apk:raise RuntimeError('generate requires --apk pointing to your own exact1.45.1 APK')
    game=work/'private-game';game.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(pathlib.Path(args.apk).expanduser()) as z:
        for member,pin in LOCK['game_files'].items():
            if member.endswith('libunity.so'):continue
            p=game/pathlib.PurePosixPath(member).name
            with z.open(member) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
            check_file(p,pin['sha256'])
    g=LOCK['generator'];tool=work/'toolchain';repo=tool/'cordl';broco=tool/'brocolib-src'
    clone(g['brocolib_repo'],g['brocolib_commit'],broco,submodules=False);git_tree(broco,missing_test_submodules=['tests/binaries'])
    clone(g['repo'],g['commit'],repo,submodules=False);apply_patch(repo,g['patch'])
    for patch in g.get('additional_patches',[]):apply_patch(repo,patch)
    git_tree(repo,g['source_file_hashes'],allowed_untracked=['codegen/'])
    env=os.environ.copy();env['CARGO_TARGET_DIR']=str(work/'cargo/cordl');env['CARGO_BUILD_JOBS']='1';env['RAYON_NUM_THREADS']='1'
    run(['cargo','+'+LOCK['rust_toolchain'],'build','--release','--locked','--no-default-features','--features','il2cpp_v39,cpp,json','-j1'],repo,env)
    # Runtime assets/cordl_internals are resolved from the generator checkout.
    run([work/'cargo/cordl/release/cordl','--metadata',game/'global-metadata.dat','--libil2cpp',game/'libil2cpp.so','cpp'],repo,env)
    produced=repo/'codegen/include';verify_headers(produced);link(produced,tool/'codegen/include')
    write_json(tool/'generated-provenance.json',{'target_game':LOCK['target_game'],'generator_commit':g['commit'],'patch_sha256':g['patch']['sha256'],'additional_patch_sha256':[p['sha256'] for p in g.get('additional_patches',[])],'verified_game_sha256':{m:x['sha256'] for m,x in LOCK['game_files'].items() if not m.endswith('libunity.so')},'headers_tree_sha256':tree_sha(produced),'private_files_uploaded':False})

def local_libraries(args,work):
    if not args.dependency_qmods:return
    for file in sorted(pathlib.Path(args.dependency_qmods).expanduser().glob('*.qmod')):
        with zipfile.ZipFile(file) as z:
            mod=json.loads(z.read('mod.json'));id=mod['id']
            if id not in LOCK['required_local_dependencies']:continue
            p=LOCK['required_local_dependencies'][id];blob=z.read(p['binary'])
            if hashlib.sha256(blob).hexdigest()!=p['sha256']:raise RuntimeError('Wrong exact-target dependency: '+id)
            dest=work/'core-qmods/native'/LOCAL[id][0]/p['binary'];install_bytes(dest,blob)

def dependency(key,project,args,work):
    locks=work/'.dependency-locks';locks.mkdir(parents=True,exist_ok=True)
    with (locks/(hashlib.sha256(key.encode()).hexdigest()+'.lock')).open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        return prepare_dependency(key,project,args,work)

def prepare_dependency(key,project,args,work):
    d=LOCK['dependencies'][key];dest=project/'extern/includes'/d['id']
    if d.get('local_generated'):link(work/'toolchain/codegen/include',dest/'include');return None
    cache=pathlib.Path(args.qpm_cache).expanduser()/d['id']/d['version']/'src' if args.qpm_cache else None
    dep=work/'dependency-sources'/key
    if d.get('archive'):
        archive=fetch(d['archive'],work/'downloads'/(key+'.zip'))
        if not dep.exists():unzip(archive,dep)
        if tree_sha(dep)!=d['archive_tree_sha256']:raise RuntimeError('Changed extracted dependency: '+key)
    else:clone(d['repo'],d['commit'],dep,cache)
    extra=LOCK['targets'][project.name].get('dependency_patches',{}).get(key)
    if extra:
        private=work/'dependency-sources'/(project.name+'-'+key)
        clone(d['repo'],d['commit'],private,dep);dep=private;apply_patch(dep,extra)
    if not d.get('archive'):git_tree(dep,extra.get('source_file_hashes',{}) if extra else {})
    # Mirror QPM's sharedDir path rather than exposing unrelated source folders.
    shared=d['shared_dir'];link(dep/shared,dest/shared)
    binary=d.get('binary')
    if d['id'] in LOCAL:
        folder,name=LOCAL[d['id']];lib=work/'core-qmods/native'/folder/name
        if not lib.is_file():raise RuntimeError('Build/import exact local dependency first: '+d['id'])
        if d['id'] in LOCK['required_local_dependencies']:
            check_file(lib,LOCK['required_local_dependencies'][d['id']]['sha256'])
        else:
            receipt=work/'output/build-receipt.json'
            records=json.loads(receipt.read_text()) if receipt.exists() else {}
            if records.get('schema')!=1 or records.get('target_game')!=LOCK['target_game']:raise RuntimeError('Missing matching local build receipt: '+d['id'])
            entry=records.get('packages',{}).get(d['id'],{})
            owner=next((n for n,t in LOCK['targets'].items() if t['binary']==name),None)
            if not owner or entry.get('inputs_sha256')!=LOCK['targets'][owner]['inputs_sha256']:raise RuntimeError('Rebuild local dependency with this recipe: '+d['id'])
            check_file(lib,entry.get('native_sha256',{}).get(name,''))
        link(lib,project/'extern/libs'/name)
    elif binary:
        lib=fetch(binary,work/'downloads'/key/binary['name']);link(lib,project/'extern/libs'/binary['name'])
        link(lib,work/'core-qmods/native'/d['id']/binary['name'])
    return dep

def setup_cmake(project,target):
    qinfo=target['qpm_info'];defs=f'''# Generated locally from pinned build-lock.json, no QPM scripts executed.
set(MOD_VERSION "{qinfo['version']}")
set(MOD_ID "{qinfo['name'].replace(' ','')}")
set(COMPILE_ID "{target['target']}")
set(CODEGEN_ID "bs-cordl")
set(EXTERN_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}/extern")
set(SHARED_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}/shared")
macro(RECURSE_FILES name pattern)
  file(GLOB_RECURSE ${{name}} CONFIGURE_DEPENDS "${{pattern}}")
endmacro()
'''
    (project/'qpm_defines.cmake').write_text(defs)
    lines=['# Generated from locked dependency compile options.','target_include_directories(${COMPILE_ID} PRIVATE ${EXTERN_DIR}/includes)','target_include_directories(${COMPILE_ID} SYSTEM PRIVATE ${EXTERN_DIR}/includes/libil2cpp/il2cpp/libil2cpp)']
    for key in target['dependencies']:
        d=LOCK['dependencies'][key];opts=d.get('compile_options',{});pre='${EXTERN_DIR}/includes/'+d['id']+'/'
        for item in opts.get('includePaths',[]):lines.append('target_include_directories(${COMPILE_ID} PRIVATE "'+pre+item+'")')
        for item in opts.get('systemIncludes',[]):lines.append('target_include_directories(${COMPILE_ID} SYSTEM PRIVATE "'+pre+item+'")')
        for flag in opts.get('cppFlags',[]):lines.append('target_compile_options(${COMPILE_ID} PRIVATE "'+flag+'")')
        for flag in opts.get('cppFeatures',[]):lines.append('target_compile_features(${COMPILE_ID} PRIVATE "'+flag+'")')
    lines+=['file(GLOB local_shared_libraries "${EXTERN_DIR}/libs/*.so" "${EXTERN_DIR}/libs/*.a")','target_link_directories(${COMPILE_ID} PRIVATE ${EXTERN_DIR}/libs)','target_link_libraries(${COMPILE_ID} PRIVATE ${local_shared_libraries})']
    (project/'extern.cmake').write_text('\n'.join(lines)+'\n')

def verify_project_source(name,p):
    t=LOCK['targets'][name]
    if output(['git','rev-parse','HEAD'],p)!=t['commit']:raise RuntimeError('Wrong local source dependency commit: '+name)
    for file,h in t['source_file_hashes'].items():check_file(p/file,h)
    allow=['extern/','qpm_defines.cmake','extern.cmake']
    if name=='Quest-BSML':allow+=['include/git_info.h']
    if name=='MetaCore-1451':allow+=['tests/lifecycle.cpp']
    git_tree(p,t['source_file_hashes'],allow)

def prepare(name,args,work):
    t=LOCK['targets'][name];p=work/'sources'/name;cache=pathlib.Path(args.source_cache).expanduser()/name if args.source_cache else None
    clone(t['repo'],t['commit'],p,cache);apply_patch(p,t['patch'])
    verify_project_source(name,p)
    # MetaCore's optional integration-test target is never built/shipped by this recipe.
    if name=='MetaCore-1451':
        tests=p/'tests/lifecycle.cpp'
        if not tests.exists():tests.parent.mkdir(exist_ok=True);tests.write_text('// Integration fixture omitted from runtime-only local build.\n')
    expected_extern={}
    for key in t['dependencies']:
        dep=dependency(key,p,args,work);d=LOCK['dependencies'][key]
        if d.get('local_generated'):expected_extern['includes/'+d['id']+'/include']=work/'toolchain/codegen/include';continue
        expected_extern['includes/'+d['id']+'/'+d['shared_dir']]=dep/d['shared_dir']
        if d['id'] in LOCAL:
            folder,native=LOCAL[d['id']];expected_extern['libs/'+native]=work/'core-qmods/native'/folder/native
        elif d.get('binary'):
            native=d['binary']['name'];expected_extern['libs/'+native]=work/'downloads'/key/native
    for dependency_id,source in t.get('local_header_overlays',{}).items():
        shared=work/'sources'/source/'shared'
        if not shared.exists():raise RuntimeError('Prepare/build local header dependency first: '+source)
        verify_project_source(source,work/'sources'/source)
        link(shared,p/'extern/includes'/dependency_id/'shared')
        expected_extern['includes/'+dependency_id+'/shared']=shared
    exact_links(p/'extern',expected_extern)
    # This generated header is overwritten by the upstream CMake template.
    run(['git','config','user.name','Local builder'],p)
    if subprocess.run(['git','symbolic-ref','-q','HEAD'],cwd=p,stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('Builder source must remain a detached pinned checkout')
    setup_cmake(p,t)
    return p

def build(name,args,work,ndk):
    t=LOCK['targets'][name];project=prepare(name,args,work);b=work/'build'/name;env=os.environ.copy();env['BEAT_SABER_NDK']=str(ndk);env['BEAT_SABER_BUILD_ROOT']=str(work);env['BEAT_SABER_CXX26']='1' if name in ['Quest-BSML','MetaCore-1451'] else '0'
    extra=[]
    if name=='Tracks':
        nb=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin';rust=work/'cargo/tracks';env.update(CARGO_TARGET_DIR=str(rust),CARGO_BUILD_JOBS='1',CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=str(nb/'aarch64-linux-android24-clang'),CC_aarch64_linux_android=str(nb/'aarch64-linux-android24-clang'),CXX_aarch64_linux_android=str(nb/'aarch64-linux-android24-clang++'),AR_aarch64_linux_android=str(nb/'llvm-ar'))
        run(['cargo','+'+LOCK['rust_toolchain'],'build','--target','aarch64-linux-android','--release','--locked','-j1'],project/'tracks_rs_link',env);extra=['-DTRACKS_RS_LINK_PATH='+str(rust/'aarch64-linux-android/release')]
    launcher=ROOT/'clang_ndk.py'
    build_type='RELEASE' if name=='BetterSongList' else 'Release'
    cmd=['cmake','-S',project,'-B',b,'-G','Ninja','-DCMAKE_BUILD_TYPE='+build_type,'-DCMAKE_ANDROID_NDK='+str(ndk),'-DCMAKE_TOOLCHAIN_FILE='+str(ndk/'build/cmake/android.toolchain.cmake'),'-DANDROID_ABI=arm64-v8a','-DANDROID_PLATFORM=android-24','-DANDROID_STL=c++_static','-DBEAT_SABER_CODEGEN_INCLUDE='+str(work/'toolchain/codegen/include')]
    if name in ['BetterSongList','Chroma','CongXinJian']:cmd+=['-DCMAKE_UNITY_BUILD=ON','-DCMAKE_UNITY_BUILD_BATCH_SIZE=4']
    if name=='Chroma':
        compiler=pathlib.Path(shutil.which(env.get('BEAT_SABER_CLANG','clang-22'))).resolve()
        ar=env.get('BEAT_SABER_LLVM_AR') or shutil.which('llvm-ar-22') or str(compiler.parent/'llvm-ar')
        ranlib=env.get('BEAT_SABER_LLVM_RANLIB') or shutil.which('llvm-ranlib-22') or str(compiler.parent/'llvm-ranlib')
        for value in [ar,ranlib]:
            if not pathlib.Path(value).is_file():raise RuntimeError('Chroma requires LLVM22 ar/ranlib: set BEAT_SABER_LLVM_AR and BEAT_SABER_LLVM_RANLIB')
        cmd+=['-DCHROMA_LLVM_AR='+ar,'-DCHROMA_LLVM_RANLIB='+ranlib]
    cmd += [f'-DCMAKE_{lang}_{kind}_LAUNCHER={launcher}' for lang in ['C','CXX'] for kind in ['COMPILER','LINKER']]
    run(cmd+extra,project,env);run(['cmake','--build',b,'--target',t['target'],'-j1'],project,env)
    native=b/t['binary']
    if native.read_bytes()[:4]!=b'\x7fELF':raise RuntimeError('Build did not produce an ELF')
    manifest=json.loads((ROOT/t['manifest']).read_text());id=manifest['id']
    if id in LOCAL:
        folder,_=LOCAL[id];dest=work/'core-qmods/native'/folder/t['binary'];install_bytes(dest,native.read_bytes())
    out=work/'output';out.mkdir(exist_ok=True);qmod=out/(id+'-'+manifest['version']+'.qmod')
    provenance={'experimental':True,'target_game':LOCK['target_game'],'inputs_sha256':t['inputs_sha256'],'headers_tree_sha256':tree_sha(work/'toolchain/codegen/include'),'runtime_tested_this_build':False,'source_commit':t['commit'],'native_sha256':sha(native)}
    with zipfile.ZipFile(qmod,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('mod.json',json.dumps(manifest,indent=2)+'\n');z.write(native,t['binary']);z.writestr('LOCAL-BUILD.json',json.dumps(provenance,indent=2)+'\n')
    receipt=out/'build-receipt.json'
    record_package(receipt,id,{'version':manifest['version'],'qmod_sha256':sha(qmod),'native_sha256':{t['binary']:sha(native)},'inputs_sha256':t['inputs_sha256'],'headers_tree_sha256':provenance['headers_tree_sha256']})
    print('Built for local testing:',qmod)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['list','doctor','generate','prepare','build']);ap.add_argument('targets',nargs='*');ap.add_argument('--work-dir',default=str(pathlib.Path.home()/'.cache/bs1451-builder'));ap.add_argument('--headers');ap.add_argument('--apk');ap.add_argument('--dependency-qmods');ap.add_argument('--qpm-cache',help='Optional existing QPM source cache for faster verified cloning');ap.add_argument('--source-cache',help='Optional existing source checkouts, never modified');ap.add_argument('--rust',action='store_true');args=ap.parse_args();work=pathlib.Path(args.work_dir).expanduser().resolve()
    if args.command=='list':
        for name,t in LOCK['targets'].items():print(name,t['state'])
        for name,why in LOCK.get('pending',{}).items():print(name,'HELD:',why)
        return
    verify_recipe()
    ndk=doctor(args)
    if args.command=='doctor':print('Compiler/tool preflight passed. This does not validate mod runtime.');return
    work.mkdir(parents=True,exist_ok=True)
    if args.command=='generate':generate(args,work);return
    if args.apk and not args.headers and not (work/'toolchain/codegen/include').exists():generate(args,work)
    headers(args,work);local_libraries(args,work)
    names=args.targets or list(LOCK['targets'])
    for name in names:
        if name in LOCK.get('pending',{}):raise RuntimeError(name+': '+LOCK['pending'][name])
        if name not in LOCK['targets']:raise RuntimeError('Unknown target: '+name)
        if args.command=='prepare':prepare(name,args,work)
        else:build(name,args,work,ndk)

if __name__=='__main__':
    try:main()
    except (RuntimeError,subprocess.CalledProcessError,KeyError,FileNotFoundError) as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
