#!/usr/bin/env python3
"""CMake launcher: Clang22 frontend, exact NDKr27c headers/runtime/linker."""
import os, pathlib, sys

def command(args, env):
    if not args: raise ValueError('CMake must pass the original Android compiler')
    ndk=pathlib.Path(env['BEAT_SABER_NDK']).resolve()
    resource=ndk/'toolchains/llvm/prebuilt/linux-x86_64/lib/clang/18'
    compiler=env.get('BEAT_SABER_CLANGXX','clang++-22') if '++' in pathlib.Path(args[0]).name else env.get('BEAT_SABER_CLANG','clang-22')
    flags=args[1:]
    if env.get('BEAT_SABER_CXX26')=='1':
        flags=[x.replace('-std=gnu++23','-std=gnu++2c').replace('-std=c++23','-std=c++2c') for x in flags]
    workspace=env.get('BEAT_SABER_BUILD_ROOT')
    if workspace:
        # Preserve byte length: Paper logging indexes __FILE__ by source-root length.
        replacement='/'+'_'*max(0,len(workspace.encode())-6)+'build'
        flags += [f'-ffile-prefix-map={workspace}={replacement}',f'-fdebug-prefix-map={workspace}={replacement}']
    if not any(x in flags for x in ['-c','-E','-fsyntax-only']):
        flags += [str(resource/'lib/linux/aarch64/libunwind.a'),'-Wl,--exclude-libs,libunwind.a']
    return [compiler,'--no-default-config','-resource-dir='+str(resource),*flags]

if __name__=='__main__':
    argv=command(sys.argv[1:],os.environ);os.execvp(argv[0],argv)
