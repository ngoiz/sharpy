import dill as pickle
import sharpy.utils.cout_utils as cout


def main(args=None, sharpy_input_dict=None):
    """
    Main ``SHARPy`` routine

    This is the main ``SHARPy`` routine.
    It starts the solution process by reading the settings that are
    included in the ``.solver.txt`` file that is parsed
    as an argument, or an equivalent dictionary given as ``sharpy_input_dict``.
    It reads the solvers specific settings and runs them in order

    Args:
        args (str): ``.solver.txt`` file with the problem information and settings
        sharpy_input_dict (dict): ``dict`` with the same contents as the
            ``solver.txt`` file would have.

    Returns:
        ``PreSharpy`` class object

    """
    import time
    import argparse

    import sharpy.utils.input_arg as input_arg
    import sharpy.utils.solver_interface as solver_interface
    from sharpy.presharpy.presharpy import PreSharpy
    from sharpy.utils.cout_utils import start_writer, finish_writer
    # Loading solvers and postprocessors
    import sharpy.solvers
    import sharpy.postproc
    import sharpy.generators
    import sharpy.controllers
    # ------------

    # output writer
    start_writer()
    # timing
    t = time.process_time()
    t0_wall = time.perf_counter()

    if sharpy_input_dict is None:
        parser = argparse.ArgumentParser(prog='SHARPy', description=
        """This is the executable for Simulation of High Aspect Ratio Planes.\n
        Imperial College London 2019""")
        parser.add_argument('input_filename', help='path to the *.solver.txt input file', type=str, default='')
        parser.add_argument('-r', '--restart', help='restart the solution with a given snapshot', type=str, default=None)
        parser.add_argument('-d', '--docs', help='generates the solver documentation in the specified location. Code does not execute if running this flag', action='store_true')
        if args is not None:
            args = parser.parse_args(args[1:])
        else:
            args = parser.parse_args()

    if args.docs:
        import sharpy.utils.docutils as docutils
        docutils.generate_documentation()
        return 0

        if args.input_filename == '':
            parser.error('input_filename is a required argument of sharpy.')
        settings = input_arg.read_settings(args)
        if args.restart is None:
            # run preSHARPy
            data = PreSharpy(settings)
        else:
            try:
                with open(args.restart, 'rb') as restart_file:
                    data = pickle.load(restart_file)
            except FileNotFoundError:
                raise FileNotFoundError('The file specified for the snapshot \
                    restart (-r) does not exist. Please check.')

            # update the settings
            data.update_settings(settings)
    else:
        # Case for input from dictionary
        settings = input_arg.read_settings(args)
        # run preSHARPy
        data = PreSharpy(settings)

    # Loop for the solvers specified in *.solver.txt['SHARPy']['flow']
    for solver_name in settings['SHARPy']['flow']:
        solver = solver_interface.initialise_solver(solver_name)
        solver.initialise(data)
        data = solver.run()

    cpu_time = time.process_time() - t
    wall_time = time.perf_counter() - t0_wall
    cout.cout_wrap('FINISHED - Elapsed time = %f6 seconds' % wall_time, 2)
    cout.cout_wrap('FINISHED - CPU process time = %f6 seconds' % cpu_time, 2)
    finish_writer()
    return data
