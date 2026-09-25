
// PRIVATE device diagnostic: calls real game trampolines and installed public
// entrypoints. It neither registers characteristics nor accesses player saves.
#include <fstream>
#include <array>
void RunCharacteristicNativeDiagnostic() {
    using C = GlobalNamespace::BeatmapCharacteristic;
    using E = GlobalNamespace::BeatmapCharacteristicExtensions;
    using S = hook_BeatmapCharacteristicExtensions_SerializedName;
    using P = hook_BeatmapCharacteristicExtensions_FromSerializedName;
    std::ofstream out("/sdcard/ModData/com.beatgames.beatsaber/Mods/SongCore/characteristic-native-diagnostic-v1.tsv", std::ios::trunc);
    auto originalSerialize = *S::trampoline();
    auto originalParse = *P::trampoline();
    out << "BEGIN\tnative-original-vs-installed-public\n" << std::flush;
    INFO("SC_NATIVE_PROBE begin: real original trampolines vs installed public entrypoints; no save access");
    if (!out || !originalSerialize || !originalParse) {
        ERROR("SC_NATIVE_PROBE missing output or installed trampoline");
        return;
    }
    out << "POINTERS\t" << reinterpret_cast<void*>(S::addr()->methodPointer)
        << '\t' << reinterpret_cast<void*>(originalSerialize)
        << '\t' << reinterpret_cast<void*>(P::addr()->methodPointer)
        << '\t' << reinterpret_cast<void*>(originalParse) << '\n' << std::flush;
    struct Named { int id; const char* name; };
    std::array<Named, 9> known{{{0,"Standard"},{1,"OneSaber"},{2,"Legacy"},
        {3,"NoArrows"},{4,"360Degree"},{5,"90Degree"},
        {100,"Lightshow"},{101,"Lawless"},{1000,"MissingCharacteristic"}}};
    for (auto& n : known) if (n.id >= 100) {
        auto info = SongCore::API::Characteristics::GetCharacteristic(C(n.id));
        bool valid = info && info->serializedName == n.name && info->sortingOrder == n.id;
        out << "REGISTRY\t" << n.id << '\t' << n.name << '\t' << valid << '\n' << std::flush;
        if (!valid) { ERROR("SC_NATIVE_PROBE registry precondition failed"); return; }
    }
    auto text = [](StringW s) { return s ? std::string(s) : std::string("<null>"); };
    int total = 0, failed = 0;
    auto record = [&](bool passed) { ++total; failed += !passed; out << '\t' << passed << '\n' << std::flush; };
    for (int id : {0,1,2,3,4,5,100,101,1000,-1,999}) {
        const char* expected = "Standard";
        for (auto& n : known) if (n.id == id) expected = n.name;
        auto native = originalSerialize(C(id));
        auto installed = E::SerializedName(C(id));
        auto nativeText = text(native), installedText = text(installed);
        out << "SERIALIZE\t" << id << '\t' << nativeText << '\t' << installedText;
        record(nativeText == (id >= 0 && id <= 5 ? expected : "Standard") && installedText == expected);
    }
    auto parse = [&](const char* name, int expected) {
        StringW input = name ? StringW(name) : StringW(nullptr);
        C nativeValue(-99), installedValue(-99);
        bool native = originalParse(input, by_ref<C>(nativeValue));
        bool installed = E::BeatmapCharacteristicFromSerializedName(input, by_ref<C>(installedValue));
        int nv = static_cast<int>(nativeValue), iv = static_cast<int>(installedValue);
        bool nativeExpected = expected >= 0 && expected <= 5;
        bool installedExpected = expected >= 0;
        out << "PARSE\t" << (name ? name : "<null>") << '\t' << native << '\t' << nv << '\t' << installed << '\t' << iv;
        record(native == nativeExpected && nv == (nativeExpected ? expected : 0) &&
            installed == installedExpected && iv == (installedExpected ? expected : 0));
    };
    for (auto& n : known) parse(n.name, n.id);
    for (const char* name : {"", "lawless", "Lawless ", "UnregisteredDiagnosticName"}) parse(name, -1);
    parse(nullptr, -1);
    for (auto& n : known) {
        auto nativeName = originalSerialize(C(n.id));
        auto installedName = E::SerializedName(C(n.id));
        C nativeValue(-99), installedValue(-99);
        bool native = originalParse(nativeName, by_ref<C>(nativeValue));
        bool installed = E::BeatmapCharacteristicFromSerializedName(installedName, by_ref<C>(installedValue));
        out << "ROUNDTRIP\t" << n.id << '\t' << text(nativeName) << '\t' << static_cast<int>(nativeValue)
            << '\t' << text(installedName) << '\t' << static_cast<int>(installedValue);
        record(native && installed && static_cast<int>(nativeValue) == (n.id <= 5 ? n.id : 0) &&
            static_cast<int>(installedValue) == n.id);
    }
    out << "COMPLETE\t" << total << '\t' << failed << "\tno-save-access\n" << std::flush;
    INFO("SC_NATIVE_PROBE complete: cases={} failed={} no-save-access", total, failed);
}
