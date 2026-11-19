#!/usr/bin/env python3
"""Add Mercury admission to the matching production host; preserve SDK admission."""
from pathlib import Path
import sys
source, output = map(Path, sys.argv[1:])
s = source.read_text()
anchor = '            if(apolloWorld && SupportedApolloVessel(*body,type))continue;'
start='            // Only original Mercury classes backed by their real native module.'
end='            const bool pb='
if start in s:
    a=s.index(start);b=s.index(end,a)
    s=s[:a]+s[b:]
if s.count(anchor) != 1:
    raise SystemExit('Unknown Orbiter host admission code: update the Mercury integration explicitly')
admission = '''
            // Only original Mercury classes backed by their real native module.
            // NativeModule has already checked the descriptor, SDK build and C++ ABI.
            auto mercuryClass=ResourceResolver::Normalize(type);
            if (mercuryClass.rfind("vessels/",0)==0) mercuryClass.erase(0,8);
            if (mercuryClass.rfind("projectmercury/",0)==0 && body->NativeModuleName()) {
                const auto mercuryModule=ResourceResolver::Normalize(body->NativeModuleName());
                static constexpr const char* mercuryModules[]={
                    "projectmercury/projectmercuryredstone", "projectmercury/projectmercuryatlas",
                    "projectmercury/mercury_atlascore", "projectmercury/mercury_redstonebooster",
                    "projectmercury/mercury_abort", "projectmercury/mercury_antennadrogue",
                    "projectmercury/mercury_mainchute", "projectmercury/mercury_genericinert",
                    "projectmercury/mercury_lc5", "projectmercury/mercury_lc14",
                    "projectmercury/projectmercurylittlejoe", "projectmercury/littlejoebooster",
                    "projectmercury/littlejoeramp", "projectmercury/projectmercuryscout",
                    "projectmercury/scoutstagegeneric"
                };
                if (std::any_of(std::begin(mercuryModules),std::end(mercuryModules),
                    [&](const char* name){ return mercuryModule==name; })) continue;
            }
'''
s=s.replace(anchor,anchor+admission)
prior_input='                // Running vessels get their normal Space command (Mercury retrosequence).\n                // Space still resumes a paused session; Ctrl-P always pauses.\n                if(spacePause && running && render.focus->ConsumeBufferedKey(code,true,eventKeys.data()))continue;\n'
s=s.replace(prior_input,'')
pause='                if(spacePause || keymap.IsLogicalKey(code,eventKeys.data(),OAPI_LKEY_Pause))'
if s.count(pause)!=1:raise SystemExit('Unknown Orbiter pause input code')
s=s.replace(pause,'                // Running vessels get their normal Space command (Mercury retrosequence).\n                // Space still resumes a paused session; Ctrl-P always pauses.\n                if(spacePause && running && render.focus->ConsumeBufferedKey(code,true,eventKeys.data()))continue;\n'+pause)
output.write_text(s)
