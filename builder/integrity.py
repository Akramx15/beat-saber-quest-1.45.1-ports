"""Complete source-tree checks used before compiling a pinned local recipe."""
import hashlib, json, os, pathlib, re, subprocess

def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def tree_sha(root):
    root=pathlib.Path(root).resolve();records=[]
    for parent,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git']
        for name in [*files,*[d for d in dirs if pathlib.Path(parent,d).is_symlink()]]:
            p=pathlib.Path(parent,name);rel=p.relative_to(root).as_posix()
            if p.is_symlink():records.append([rel,'link',os.readlink(p)])
            elif p.is_file():records.append([rel,'file',file_sha(p)])
            else:raise RuntimeError('Unexpected special file: '+str(p))
    records.sort()
    return hashlib.sha256(json.dumps(records,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

def git_tree(repo,overrides=None,allowed_untracked=(),missing_test_submodules=()):
    repo=pathlib.Path(repo);overrides=overrides or {};allowed=set(allowed_untracked)
    entries=subprocess.check_output(['git','ls-tree','-rz','HEAD'],cwd=repo).split(b'\0')
    seen=set()
    for item in entries:
        if not item:continue
        header,rawpath=item.split(b'\t',1);mode,kind,oid=header.decode().split();name=rawpath.decode();p=repo/name;seen.add(name)
        if mode=='160000':
            if name in missing_test_submodules:
                if p.exists() and any(p.iterdir()):raise RuntimeError('Unexpected test submodule contents: '+str(p))
                continue
            actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip()
            if actual!=oid:raise RuntimeError('Wrong submodule commit: '+str(p))
            git_tree(p)
        elif name in overrides:
            if p.is_symlink() or not p.is_file() or file_sha(p)!=overrides[name]:raise RuntimeError('Patched source mismatch: '+str(p))
        else:
            if mode=='120000':
                if not p.is_symlink():raise RuntimeError('Changed source symlink: '+str(p))
                data=os.readlink(p).encode()
            else:
                if p.is_symlink() or not p.is_file():raise RuntimeError('Missing or redirected source: '+str(p))
                data=p.read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if actual!=oid:raise RuntimeError('Changed pinned source: '+str(p))
    for name,h in overrides.items():
        p=repo/name
        if p.is_symlink() or not p.is_file() or file_sha(p)!=h:raise RuntimeError('Patched source mismatch: '+str(p))
    # Include ignored files as they can still be found by recursive CMake globs.
    extra=subprocess.check_output(['git','ls-files','--others','-z'],cwd=repo).split(b'\0')
    for raw in extra:
        if not raw:continue
        name=raw.decode()
        if name in overrides or name in allowed:continue
        if any(x.endswith('/') and name.startswith(x) for x in allowed):continue
        if re.fullmatch(r'\.builder-patch-[0-9a-f]{64}',name):continue
        raise RuntimeError('Unpinned additional build input: '+str(repo/name))

def exact_links(root,expected):
    root=pathlib.Path(root);found=set()
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in [*files,*[d for d in dirs if pathlib.Path(parent,d).is_symlink()]]:
            p=pathlib.Path(parent,name);rel=p.relative_to(root).as_posix();found.add(rel)
            if rel not in expected or not p.is_symlink() or p.resolve()!=expected[rel].resolve():raise RuntimeError('Unexpected external build input: '+str(p))
    if found!=set(expected):raise RuntimeError('Missing external build inputs: '+str(set(expected)-found))
