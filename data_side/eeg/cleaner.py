"""
cleans the raw EEG and flags unusable samples before analysis
used by calibration and gameplay analysis on the EEG from the collector

artifact_mask is if can implement, because bad contact with EEG sometimes still
gives data but those samples should not be used in the analysis since unstable readings (?)
"""

def clean(x):
    # TODO: clean raw EEG (filtering) into the necessary columns
    # (do we normalise or moving average or what, need hana input on this)
    pass


def artifact_mask(y):
    # TODO: detect blinks, movement and bad contact
    #should there be something to note when contact becomes loose halfway through game?
    pass
