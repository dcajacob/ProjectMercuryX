// SPDX-License-Identifier: GPL-3.0-or-later
#include "MercurySound.h"
#include "XRSoundEngine10.h"
#include <filesystem>
#include <map>
#include <string>
#ifndef _WIN32
#include <dlfcn.h>
#else
#include <windows.h>
#endif

namespace {
struct Wave { std::string path; MercurySoundPlayback mode; bool loaded=false; };
struct VesselSound {
    OBJHANDLE vessel;
    XRSoundEngine10* engine=nullptr; // Borrowed until the vessel/session is destroyed.
    std::map<int,Wave> waves;
    bool rcsEnabled=true;
    int radio=-1;
};
std::map<int,VesselSound> vessels;
std::string directory="Sound/_CustomVesselsSounds/ProjectMercuryX";
int nextId=1;
using Acquire=XRSoundEngine10* (*)(OBJHANDLE,const char*,const char*);

Acquire FindBridge()
{
#ifndef _WIN32
    Dl_info info{};
    if(!dladdr(reinterpret_cast<void*>(&FindBridge),&info) || !info.dli_fname) return nullptr;
    auto root=std::filesystem::path(info.dli_fname).parent_path().parent_path().parent_path();
#ifdef __APPLE__
    auto path=root/"Plugin/XRSound.dylib";
#else
    auto path=root/"Plugin/XRSound.so";
#endif
    // Only use the plugin after the engine has admitted and initialized it.
    void* library=dlopen(path.c_str(),RTLD_LAZY|RTLD_NOLOAD);
    if(!library) return nullptr;
    auto acquire=reinterpret_cast<Acquire>(dlsym(library,"OrbiterNativeXRSoundVessel"));
    dlclose(library);
    return acquire;
#else
    auto library=GetModuleHandleW(L"XRSound.dll");
    return library?reinterpret_cast<Acquire>(GetProcAddress(library,"OrbiterNativeXRSoundVessel")):nullptr;
#endif
}
VesselSound* Ready(int id)
{
    auto found=vessels.find(id);
    if(found==vessels.end()) return nullptr;
    auto& sound=found->second;
    if(!sound.engine) {
        auto acquire=FindBridge();
        if(acquire) sound.engine=acquire(sound.vessel,ORBITER_NATIVE_SDK_BUILD,ORBITER_NATIVE_CPP_ABI);
        if(!sound.engine) return nullptr;
        sound.engine->SetDefaultSoundEnabled(XRSound::RCSSustain,sound.rcsEnabled);
        for(int slot=XRSound::RCSAttackPlusX;slot<=XRSound::RCSCloseMinusZ;++slot)
            sound.engine->SetDefaultSoundEnabled(static_cast<XRSound::DefaultSoundID>(slot),sound.rcsEnabled);
        oapiWriteLog("Mercury X: connected custom audio to native XRSound");
    }
    return &sound;
}
}

int ConnectToOrbiterSoundDLL(OBJHANDLE vessel)
{
    int id=nextId++;
    vessels.emplace(id,VesselSound{vessel});
    return id;
}
void SetMyDefaultWaveDirectory(const char* path)
{
    directory=path;
    std::replace(directory.begin(),directory.end(),'\\','/');
}
bool RequestLoadVesselWave(int vessel,int id,const char* filename,MercurySoundPlayback mode)
{
    auto found=vessels.find(vessel);
    if(found==vessels.end()) return false;
    std::string file=filename;
    std::replace(file.begin(),file.end(),'\\','/');
    auto path=(std::filesystem::path(directory)/file).lexically_normal().generic_string();
    // These two effects belonged to OrbiterSound, rather than the Mercury pack.
    if(path=="Sound/Vessel/attsustain.wav") path="XRSound/Default/RCS Sustain.wav";
    if(path=="Sound/Vessel/retro.wav") path="XRSound/Default/Main.wav";
    found->second.waves.insert_or_assign(id,Wave{path,mode});
    return true; // Loading is deferred until the native sound plugin starts.
}
bool PlayVesselWave(int vessel,int id,bool loop,int volume,int)
{
    auto* sound=Ready(vessel);
    if(!sound) return false;
    auto found=sound->waves.find(id);
    if(found==sound->waves.end()) return false;
    auto& wave=found->second;
    if(!wave.loaded) wave.loaded=sound->engine->LoadWav(id,wave.path.c_str(),
        wave.mode==INTERNAL_ONLY?XRSound::PlaybackType::InternalOnly:XRSound::PlaybackType::Radio);
    return wave.loaded && sound->engine->PlayWav(id,loop,std::clamp(volume/255.0f,0.0f,1.0f));
}
bool PlayVesselRadioExclusiveWave(int vessel,int id,int volume)
{
    auto* sound=Ready(vessel);
    if(!sound) return false;
    if(sound->radio>=0 && sound->radio!=id) sound->engine->StopWav(sound->radio);
    sound->radio=id;
    return PlayVesselWave(vessel,id,false,volume);
}
bool StopVesselWave(int vessel,int id)
{
    auto* sound=Ready(vessel);
    return sound && sound->engine->StopWav(id);
}
void SoundOptionOnOff(int vessel,int option,bool enabled)
{
    auto found=vessels.find(vessel);
    if(found==vessels.end() || option!=PLAYATTITUDETHRUST) return;
    found->second.rcsEnabled=enabled;
    if(auto* sound=Ready(vessel)) sound->engine->SetDefaultSoundEnabled(XRSound::RCSSustain,enabled);
}
void MercurySoundRelease(OBJHANDLE vessel)
{
    for(auto it=vessels.begin();it!=vessels.end();)
        if(it->second.vessel==vessel) it=vessels.erase(it); else ++it;
}
