// Additional simulator fixes are enabled only on the machine family validated here.
#pragma once
#include <cstdlib>
#include <cstring>
#include <sys/sysctl.h>

static bool haswellLocalProfile() {
    if (const char *setting = getenv("INTEL_HASWELL_PROFILE"); setting && !strcmp(setting, "0")) return false;
    static const bool matches = [] {
        char model[64] = {}, release[64] = {};
        size_t size = sizeof model;
        if (sysctlbyname("hw.model", model, &size, nullptr, 0)) return false;
        size = sizeof release;
        return !sysctlbyname("kern.osrelease", release, &size, nullptr, 0)
            && !strcmp(model, "MacBookPro11,2") && !strncmp(release, "25.", 3);
    }();
    return matches;
}
