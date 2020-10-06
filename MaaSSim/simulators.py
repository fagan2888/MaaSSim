################################################################################
# Module: runners.py
# Description: Wrappers to prepare and run simulations
# Rafal Kucharski @ TU Delft
################################################################################


from MaaSSim.maassim import Simulator
from MaaSSim.shared import prep_shared_rides
from MaaSSim.utils import get_config, load_G, generate_demand, generate_vehicles, initialize_df, empty_series, \
    slice_space, test_space, dummy_False, read_requests_csv
import numpy as np
import pandas as pd
from scipy.optimize import brute
import logging



def single_pararun(one_slice, *args):
    # function to be used with optimize brute
    inData, params, search_space = args  # read static input
    _inData = inData.copy()
    _params = params.copy()
    stamp = dict()
    # parameterize
    for i, key in enumerate(search_space.keys()):
        val = search_space[key][int(one_slice[int(i)])]
        stamp[key] = val
        _params[key] = val

    stamp['dt'] = pd.Timestamp.now()
    filename = "".join([c for c in str(stamp) if c.isalpha() or c.isdigit() or c == ' ']).rstrip().replace(" ", "_")

    sim = simulate(inData=inData, params=_params, logger_level=logging.WARNING)
    sim.dump(id=filename)  # store results

    print(filename, pd.Timestamp.now(), 'end')
    return 0


def simulate_parallel(config="../data/config/default.json", inData=None, params=None, search_space=None, **kwargs):
    if inData is None:  # othwerwise we use what is passed
        from MaaSSim.data_structures import structures
        inData = structures.copy()  # fresh data
    if params is None:
        params = get_config(config, root_path = kwargs.get('root_path'))  # load from .json file

    if len(inData.G) == 0:  # only if no graph in input
        inData = load_G(inData, params, stats=True)  # download graph for the 'params.city' and calc the skim matrices
    if len(inData.passengers) == 0:  # only if no passengers in input
        inData = generate_demand(inData, params, avg_speed=True)
    if len(inData.vehicles) == 0:  # only if no vehicles in input
        inData.vehicles = generate_vehicles(inData, params.nV)
    if len(inData.platforms) == 0:  # only if no platforms in input
        inData.platforms = initialize_df(inData.platforms)
        inData.platforms.loc[0] = empty_series(inData.platforms)
        inData.vehicles.platform = 0
        inData.passengers.platforms = inData.passengers.apply(lambda x: [0], axis=1)


    inData = prep_shared_rides(inData, params.shareability, sblt = None)  # obligatory to prepare schedules


    brute(func=single_pararun,
          ranges=slice_space(search_space, replications=params.parallel.nReplications),
          args=(inData, params, search_space),
          full_output=True,
          finish=None,
          workers=params.parallel.nThread)


def simulate(config="../data/config/default.json", inData=None, params=None, **kwargs):
    """
    main runner and wrapper
    loads or uses json config to prepare the data for simulation, run it and process the results
    :param config: .json file path
    :param inData: optional input data
    :param params: loaded json file
    :param kwargs: optional arguments
    :return: simulation object with results
    """

    if inData is None:  # otherwise we use what is passed
        from MaaSSim.data_structures import structures
        inData = structures.copy()  # fresh data
    if params is None:
            params = get_config(config, root_path = kwargs.get('root_path'))  # load from .json file

    if params.paths.get('requests', False):
        inData.requests, inData.passengers = read_requests_csv(params.paths.requests)

    if params.paths.get('vehicles',False):
        inData.vehicles = pd.read_csv(params.paths.vehicles, index_col=1)

    if len(inData.G) == 0:  # only if no graph in input
        inData = load_G(inData, params, stats=True)  # download graph for the 'params.city' and calc the skim matrices
    if len(inData.passengers) == 0:  # only if no passengers in input
        inData = generate_demand(inData, params, avg_speed=True)
    if len(inData.vehicles) == 0:  # only if no vehicles in input
        inData.vehicles = generate_vehicles(inData, params.nV)
    if len(inData.platforms) == 0:  # only if no platforms in input
        inData.platforms = initialize_df(inData.platforms)
        inData.platforms.loc[0] = empty_series(inData.platforms)

    inData = prep_shared_rides(inData, params.shareability, sblt=None)  # prepare schedules


    sim = Simulator(inData, params=params, **kwargs)  # initialize

    for day in range(params.get('nD', 1)):  # run iterations
        sim.make_and_run(run_id=day)  # prepare and SIM
        sim.output()  # calc results
        if sim.functions.f_stop_crit(sim=sim):
            break
    return sim


if __name__ == "__main__":
    simulate()
    from dotmap import DotMap
    search_space = DotMap()
    search_space.nP = [20, 40]
    search_space.nV = [20, 40]
    simulate_parallel(search_space = search_space)

