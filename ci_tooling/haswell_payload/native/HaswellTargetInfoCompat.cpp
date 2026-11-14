// Native replacement for the verified LLDB target-info repair. No disk writes.
#include "HaswellLocalProfile.h"
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach.h>
#include <sys/mman.h>
#include <cstdio>
#include <cstdint>

using BuilderFunction = void *(*)(void *, const void *);
static BuilderFunction original;
static const unsigned char prologue[] = {0x55,0x48,0x89,0xe5,0x41,0x56,0x53,0x49,0x89,0xf6,0x48,0x89,0xfb};

static unsigned repairBound(void *builder) {
    if (!builder || !haswellLocalProfile()) return 0;
    void *target = *reinterpret_cast<void **>(static_cast<char *>(builder) + 0x30);
    if (!target) return 0;
    auto *bound = reinterpret_cast<uint32_t *>(static_cast<char *>(target) + 0x18);
    if (*bound != 1) return 0;
    *bound = 16;
    return 1;
}

static void *withHaswellBound(void *builder, const void *module) {
    void *result = original(builder, module);
    if (result == builder && repairBound(builder) && getenv("INTELTEX_LOG"))
        fprintf(stderr, "[haswell-local] sampler target bound 1 -> 16\n");
    return result;
}

static void absoluteJump(unsigned char *where, const void *destination) {
    where[0] = 0x48; where[1] = 0xb8;
    uintptr_t value = reinterpret_cast<uintptr_t>(destination);
    memcpy(where + 2, &value, sizeof value);
    where[10] = 0xff; where[11] = 0xe0;
}

static bool knownUUID(const mach_header_64 *header) {
    static const unsigned char accepted[][16] = {
        {0xd5,0xcf,0x00,0x07,0x0d,0xb7,0x30,0x29,0x84,0x7a,0xa6,0xa8,0xa5,0xfd,0xdf,0xff},
        {0xd5,0xce,0x00,0x07,0xf4,0x60,0x35,0x0f,0xad,0xe9,0x54,0xbd,0x35,0x0a,0xe6,0xf6},
    };
    auto *command = reinterpret_cast<const load_command *>(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        if (command->cmd == LC_UUID) {
            auto *uuid = reinterpret_cast<const uuid_command *>(command);
            for (const auto &value : accepted) if (!memcmp(uuid->uuid, value, 16)) return true;
            return false;
        }
        command = reinterpret_cast<const load_command *>(reinterpret_cast<const char *>(command) + command->cmdsize);
    }
    return false;
}

static void loaded(const mach_header *raw, intptr_t slide) {
    if (original || !haswellLocalProfile() || raw->magic != MH_MAGIC_64) return;
    auto *header = reinterpret_cast<const mach_header_64 *>(raw);
    if (!knownUUID(header)) return;
    Dl_info image = {};
    if (!dladdr(raw, &image) || !image.dli_fname || !strstr(image.dli_fname, "/GPUCompiler.framework/Versions/31001/Libraries/libGPUCompilerImpl.dylib")) return;
    void *handle = dlopen(image.dli_fname, RTLD_NOLOAD | RTLD_LAZY);
    auto *entry = handle ? static_cast<unsigned char *>(dlsym(handle, "_ZN4llvm3air20AIRTargetInfoBuilder14setMaxBindingsERKNS_6ModuleE")) : nullptr;
    if (!entry || memcmp(entry, prologue, sizeof prologue)) return;
    // Exactly 13 bytes of register-only instructions; the following RIP-relative
    // LEA remains at its original address. RAX is undefined until the later call.
    auto *trampoline = static_cast<unsigned char *>(mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0));
    if (trampoline == MAP_FAILED) return;
    memcpy(trampoline, entry, sizeof prologue);
    absoluteJump(trampoline + sizeof prologue, entry + sizeof prologue);
    if (mprotect(trampoline, 4096, PROT_READ | PROT_EXEC)) { munmap(trampoline, 4096); return; }
    vm_address_t page = reinterpret_cast<vm_address_t>(entry) & ~(static_cast<vm_address_t>(vm_page_size) - 1);
    vm_size_t length = ((reinterpret_cast<vm_address_t>(entry) + sizeof prologue - page + vm_page_size - 1) / vm_page_size) * vm_page_size;
    if (vm_protect(mach_task_self(), page, length, false, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY)) { munmap(trampoline, 4096); return; }
    original = reinterpret_cast<BuilderFunction>(trampoline);
    unsigned char replacement[sizeof prologue]; memset(replacement, 0x90, sizeof replacement);
    absoluteJump(replacement, reinterpret_cast<void *>(withHaswellBound));
    memcpy(entry, replacement, sizeof replacement);
    vm_protect(mach_task_self(), page, length, false, VM_PROT_READ | VM_PROT_EXECUTE);
    if (getenv("INTELTEX_LOG")) fprintf(stderr, "[haswell-local] native target-info repair installed in memory\n");
}

__attribute__((constructor)) static void install() {
    if (haswellLocalProfile()) _dyld_register_func_for_add_image(loaded);
}

#ifdef HASWELL_COMPAT_TEST
extern "C" unsigned HaswellRepairBoundForTesting(void *builder) { return repairBound(builder); }
extern "C" bool HaswellTargetHookInstalledForTesting() { return original != nullptr; }
#endif
