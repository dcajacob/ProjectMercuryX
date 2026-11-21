"""Pilot retrosequence planning for the linked native Mercury replay saves."""
import re

# NASA SP-4012 vol. II, tables 2-33 and 2-34. These two replays exercise
# historical command times. Faith 7 uses the capsule's geographic landing mode.
HISTORICAL_SEQUENCE_MET = {
    'aurora7': 4 * 3600 + 32 * 60 + 36.5,
    'sigma7': 8 * 3600 + 51 * 60 + 30,
}

CHECKPOINT_MET = {mission: int(met) - 300 for mission, met in HISTORICAL_SEQUENCE_MET.items()}
# Consult the panel 30 seconds before the historical event (NASA SP-4012
# vol. II, table 2-35). Its earlier five-minute prediction is still changing.
FAITH7_HISTORICAL_MET = 33 * 3600 + 58 * 60 + 59
CHECKPOINT_MET['faith7'] = FAITH7_HISTORICAL_MET - 30


# Frequency of the normal OpenGL launcher. Use it on both powered legs of MA-9.
FAITH7_HZ = 60


def entry_hz(mission):
    return FAITH7_HZ if mission == 'faith7' else 16


def sequence_met(mission, coast):
    if mission in HISTORICAL_SEQUENCE_MET:
        return HISTORICAL_SEQUENCE_MET[mission]
    if mission != 'faith7':
        raise ValueError(f'Unknown Mercury return: {mission}')
    met = CHECKPOINT_MET[mission]
    log = (coast/'console.log').read_text(errors='replace')
    clocks = re.findall(rf'^Mercury recovery clock MA-9 MET {met} sequence (\d+):(\d+):(\d+)$', log, re.M)
    if not clocks:
        raise ValueError(f'{coast}: missing MA-9 panel recommendation at MET {met}')
    hours, minutes, seconds = map(int, clocks[-1])
    command = hours * 3600 + minutes * 60 + seconds
    if minutes >= 60 or seconds >= 60 or not met < command <= FAITH7_HISTORICAL_MET + 60:
        raise ValueError(f'{coast}: no upcoming recovery solution at MET {met}: {clocks[-1]}')
    return command
