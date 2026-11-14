// Exercise the actual AIRTargetInfoBuilder factory on a controlled module.
#include <dlfcn.h>
#include <cstdio>
#include <cstring>
#include <cstdint>

int main(int argc, char **argv) {
    if (argc < 2 || argc > 3) return 2;
    void *gpu = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!gpu) { fprintf(stderr,"GPUCompiler load: %s\n",dlerror());return 3; }
    bool automatic=argc==3 && !strcmp(argv[2],"--native");
    void *shim = argc == 3 && !automatic ? dlopen(argv[2], RTLD_NOW | RTLD_LOCAL) : nullptr;
    if (argc == 3 && !automatic && !shim) { fprintf(stderr,"Shim load: %s\n",dlerror());return 4; }
    auto createContext = reinterpret_cast<void*(*)()>(dlsym(gpu,"LLVMContextCreate"));
    auto makeBuffer = reinterpret_cast<void*(*)(const char*,size_t,const char*)>(dlsym(gpu,"LLVMCreateMemoryBufferWithMemoryRangeCopy"));
    auto parse = reinterpret_cast<int(*)(void*,void*,void**,char**)>(dlsym(gpu,"LLVMParseIRInContext"));
    auto factory = reinterpret_cast<void*(*)(void*,const void*)>(dlsym(gpu,"_ZN4llvm3air20AIRTargetInfoBuilder14setMaxBindingsERKNS_6ModuleE"));
    if (!createContext || !makeBuffer || !parse || !factory) { fprintf(stderr,"Missing frontend API\n");return 5; }
    const char *ir="!llvm.module.flags = !{!0}\n!0 = !{i32 1, !\"air.max_samplers\", i32 1}\n";
    void *module=nullptr;char *error=nullptr;
    if(parse(createContext(),makeBuffer(ir,strlen(ir),"haswell-target-test"),&module,&error)) {
        fprintf(stderr,"AIR parse: %s\n",error?error:"unknown");return 6;
    }
    alignas(16) unsigned char builder[64]={}, target[64];memset(target,0xa5,sizeof target);
    *reinterpret_cast<void**>(builder+0x30)=target;
    void *result=factory(builder,module);
    uint32_t bound;memcpy(&bound,target+0x18,sizeof bound);
    unsigned expected=argc==3?16:1;
    for(unsigned i=0;i<sizeof target;i++)if((i<0x18 || i>=0x1c) && target[i]!=0xa5){fprintf(stderr,"Other target fields changed\n");return 7;}
    bool installed=automatic;
    if(shim){auto check=reinterpret_cast<bool(*)()>(dlsym(shim,"HaswellTargetHookInstalledForTesting"));installed=check&&check();}
    bool passed=result==builder && bound==expected && (argc==2 || installed);
    printf("{\"passed\":%s,\"samplers\":%u,\"expected\":%u,\"hook_installed\":%s}\n",passed?"true":"false",bound,expected,installed?"true":"false");
    return passed?0:1;
}
