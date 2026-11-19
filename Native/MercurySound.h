// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#ifdef MERCURY_NATIVE_ORBITER
#include "MercuryOrbiter.h"
enum MercurySoundPlayback { DEFAULT, INTERNAL_ONLY };
constexpr bool LOOP=true;
constexpr int PLAYATTITUDETHRUST=1;
int ConnectToOrbiterSoundDLL(OBJHANDLE);
void SetMyDefaultWaveDirectory(const char*);
bool RequestLoadVesselWave(int,int,const char*,MercurySoundPlayback);
bool PlayVesselWave(int,int,bool=false,int=255,int=0);
bool PlayVesselRadioExclusiveWave(int,int,int=255);
bool StopVesselWave(int,int);
void SoundOptionOnOff(int,int,bool);
void MercurySoundRelease(OBJHANDLE);
#else
#include "../../../Sound/OrbiterSound_SDK/VESSELSOUND_SDK/ShuttlePB_project/OrbiterSoundSDK50.h"
#endif
