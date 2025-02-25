"""Implement unit tests for Snowfall class."""

import os
import pytest
from ethz_snow.snowfall import Snowfall
from ethz_snow.snowflake import Snowflake
from ethz_snow.operatingConditions import OperatingConditions

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def test_passSnowflakeArgs():
    """Test that Snowflake arguments are passed correctly."""
    config = THIS_DIR + "/data/square.yaml"
    S = Snowfall(
        N_vials=(3, 3, 1),
        dt=5,
        seed=121,
        solidificationThreshold=0.5,
        configPath=config,
    )
    Sf = Snowflake()

    # seed input is deleted
    assert S.Sf_template.seed == Sf.seed
    assert S.Sf_template.dt == 5
    assert S.Sf_template.N_vials == (3, 3, 1)
    assert S.Sf_template.solidificationThreshold == 0.5


@pytest.fixture(scope="module")
def myOpcond():
    """Fixture to share operating conditions across tests."""
    cooling = {"start": 20, "end": -20, "rate": 1}
    myOpcond = OperatingConditions(t_tot=10000, cooling=cooling)

    return myOpcond


@pytest.fixture(scope="module")
def S_seq(myOpcond):
    """Fixture to only calculate S_seq once."""
    config = THIS_DIR + "/data/square.yaml"
    S_seq = Snowfall(
        N_vials=(3, 3, 1), dt=5, opcond=myOpcond, Nrep=5, configPath=config
    )
    S_seq.run(how="sequential")

    return S_seq


@pytest.mark.slow
def test_runTypesIdentical(S_seq, myOpcond):
    """Test that output is independent of parallelization."""
    config = THIS_DIR + "/data/square.yaml"
    S_async = Snowfall(
        N_vials=(3, 3, 1), dt=5, opcond=myOpcond, Nrep=5, configPath=config
    )
    S_async.run(how="async")
    t_nuc_async = np.concatenate(
        [S_async.stats[key]["t_nucleation"] for key in S_async.stats]
    )
    # need to sort because order of seeds might change in parallelization
    t_nuc_async.sort()

    S_sync = Snowfall(
        N_vials=(3, 3, 1), dt=5, opcond=myOpcond, Nrep=5, configPath=config
    )
    S_sync.run(how="sync")
    t_nuc_sync = np.concatenate(
        [S_sync.stats[key]["t_nucleation"] for key in S_sync.stats]
    )
    t_nuc_sync.sort()

    t_nuc_seq = np.concatenate(
        [S_seq.stats[key]["t_nucleation"] for key in S_seq.stats]
    )
    t_nuc_seq.sort()

    assert len(t_nuc_async) == 5 * 9
    assert all(t_nuc_async == t_nuc_sync)
    assert all(t_nuc_seq == t_nuc_sync)


@pytest.mark.slow
def test_statsComputation(S_seq):
    """Test that to_frame doesn't mix things up."""
    df = S_seq.to_frame()

    assert (
        df.loc[
            (df.seed == 0) & (df.vial == 1) & (df.variable == "T_nucleation"), "value"
        ].squeeze()
        == S_seq.stats[0]["T_nucleation"][1]
    )

    stats_df_slow = pd.DataFrame(columns=["group", "vial", "variable", "value", "seed"])
    for i in range(S_seq.Nrep):
        S_seq.Sf_template.stats = S_seq.stats[i]
        loc_stats_df, _ = S_seq.Sf_template.to_frame()
        loc_stats_df["seed"] = i
        stats_df_slow = pd.concat((stats_df_slow, loc_stats_df))

    # ensure same dtype
    # otherwise equals will fail
    for col in df.columns:
        stats_df_slow[col] = stats_df_slow[col].astype(df[col].dtype)

    # clean up
    S_seq.Sf_template.stats = dict()

    assert df.equals(stats_df_slow)


@pytest.mark.slow
def test_statsServers(S_seq):
    df = S_seq.to_frame()

    tsol = S_seq.solidificationTimes()
    tnuc = S_seq.nucleationTimes(seed=3)
    Tnuc = S_seq.nucleationTemperatures(group="corner", seed=7)

    assert (
        df.loc[(df.variable == "t_solidification"), "value"].to_numpy() == tsol
    ).all()

    assert (
        df.loc[(df.variable == "t_nucleation") & (df.seed == 3), "value"].to_numpy()
        == tnuc
    ).all()

    assert (
        df.loc[
            (df.variable == "T_nucleation") & (df.seed == 7) & (df.group == "corner"),
            "value",
        ].to_numpy()
        == Tnuc
    ).all()
