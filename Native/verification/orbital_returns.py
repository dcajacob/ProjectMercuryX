"""Pilot retrosequence planning for the linked native Mercury replay saves."""
import re

# NASA SP-4012 vol. II, tables 2-33 and 2-34. These two replays exercise
# historical command times. Faith 7 uses the capsule's geographic landing mode.
HISTORICAL_SEQUENCE_MET = {
    'aurora7': 4 * 3600 + 32 * 60 + 36.5,
    'sigma7': 8 * 3600 + 51 * 60 + 30,
}

CHECKPOINT_MET = {mission: int(met) - 300 for mission, met in HISTORICAL_SEQUENCE_MET.items()}
# On the verified orbit the preceding Pacific pass crosses the recovery area.
# This is the time to consult the panel, before commanding any retro motors.
CHECKPOINT_MET['faith7'] = 32 * 3600 + 21 * 60 + 40


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
    if minutes >= 60 or seconds >= 60 or not met < command < met + 5500:
        raise ValueError(f'{coast}: no upcoming recovery solution at MET {met}: {clocks[-1]}')
    return command
