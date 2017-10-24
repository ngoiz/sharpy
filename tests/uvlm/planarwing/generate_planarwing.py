import h5py as h5
import numpy as np
import configparser
import os

case_name = 'planarwing'
route = os.path.dirname(os.path.realpath(__file__)) + '/'

# flight conditions
u_inf = 25
rho = 1.225
alpha = 4
beta = 0
c_ref = 1
b_ref = 16
sweep = 0*np.pi/180.
aspect_ratio = 32 # = total wing span (chord = 1)

alpha_rad = alpha*np.pi/180

# main geometry data
main_span = aspect_ratio/2./np.cos(sweep)
main_chord = 1.0
main_ea = 0.5
main_sigma = 1
main_airfoil_P = 0
main_airfoil_M = 0

n_surfaces = 2

# discretisation data
import math
num_elem_main = 10

num_node_elem = 3
num_elem = num_elem_main + num_elem_main
num_node_main = num_elem_main*(num_node_elem - 1) + 1
num_node = num_node_main + (num_node_main - 1)

m_main = 10


def clean_test_files():
    fem_file_name = route + '/' + case_name + '.fem.h5'
    if os.path.isfile(fem_file_name):
        os.remove(fem_file_name)

    aero_file_name = route + '/' + case_name + '.aero.h5'
    if os.path.isfile(aero_file_name):
        os.remove(aero_file_name)

    solver_file_name = route + '/' + case_name + '.solver.txt'
    if os.path.isfile(solver_file_name):
        os.remove(solver_file_name)

    flightcon_file_name = route + '/' + case_name + '.flightcon.txt'
    if os.path.isfile(flightcon_file_name):
        os.remove(flightcon_file_name)


def generate_fem_file():
    # placeholders
    # coordinates
    global x, y, z
    x = np.zeros((num_node, ))
    y = np.zeros((num_node, ))
    z = np.zeros((num_node, ))
    # struct twist
    structural_twist = np.zeros_like(x)
    # beam number
    beam_number = np.zeros((num_elem, ), dtype=int)
    # frame of reference delta
    frame_of_reference_delta = np.zeros((num_elem, num_node_elem, 3))
    # connectivities
    conn = np.zeros((num_elem, num_node_elem), dtype=int)
    # stiffness
    num_stiffness = 1
    ea = 1e4
    ga = 1e4
    gj = 1e4
    eiy = 2e4
    eiz = 5e4
    sigma = 1
    base_stiffness = sigma*np.diag([ea, ga, ga, gj, eiy, eiz])
    stiffness = np.zeros((num_stiffness, 6, 6))
    stiffness[0, :, :] = main_sigma*base_stiffness
    elem_stiffness = np.zeros((num_elem,), dtype=int)
    # mass
    num_mass = 1
    m_base = 0.75
    j_base = 0.1
    base_mass = np.diag([m_base, m_base, m_base, j_base, j_base, j_base])
    mass = np.zeros((num_mass, 6, 6))
    mass[0, :, :] = np.sqrt(main_sigma)*base_mass
    elem_mass = np.zeros((num_elem,), dtype=int)
    # boundary conditions
    boundary_conditions = np.zeros((num_node, ), dtype=int)
    boundary_conditions[0] = 1
    # applied forces
    n_app_forces = 0
    node_app_forces = np.zeros((n_app_forces,), dtype=int)
    app_forces = np.zeros((n_app_forces, 6))

    # right wing (beam 0) --------------------------------------------------------------
    working_elem = 0
    working_node = 0
    beam_number[working_elem:working_elem + num_elem_main] = 0
    domain = np.linspace(0, 1.0, num_node_main)
    # x[working_node:working_node + num_node_main] = np.sin(sweep)*0.5*(1.0 - np.cos(domain*np.pi))*main_span
    # y[working_node:working_node + num_node_main] = np.cos(sweep)*0.5*(1.0 - np.cos(domain*np.pi))*main_span
    x[working_node:working_node + num_node_main] = np.sin(sweep)*np.linspace(0.0, main_span, num_node_main)
    y[working_node:working_node + num_node_main] = np.cos(sweep)*np.linspace(0.0, main_span, num_node_main)
    for ielem in range(num_elem_main):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_main):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1])
    elem_stiffness[working_elem:working_elem + num_elem_main] = 0
    elem_mass[working_elem:working_elem + num_elem_main] = 0
    boundary_conditions[0] = 1
    boundary_conditions[working_node + num_node_main - 1] = -1
    working_elem += num_elem_main
    working_node += num_node_main

    # left wing (beam 1) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_main] = 1
    domain = np.linspace(-1.0, 0.0, num_node_main)
    tempy = np.linspace(-main_span, 0.0, num_node_main)
    x[working_node:working_node + num_node_main - 1] = -np.sin(sweep)*tempy[0:-1]
    y[working_node:working_node + num_node_main - 1] = np.cos(sweep)*tempy[0:-1]
    for ielem in range(num_elem_main):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_main):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1]) + 1
    conn[working_elem + num_elem_main - 1, 1] = 0
    elem_stiffness[working_elem:working_elem + num_elem_main] = 0
    elem_mass[working_elem:working_elem + num_elem_main] = 0
    boundary_conditions[working_node] = -1
    working_elem += num_elem_main
    working_node += num_node_main - 1

    with h5.File(route + '/' + case_name + '.fem.h5', 'a') as h5file:
        coordinates = h5file.create_dataset('coordinates', data=np.column_stack((x, y, z)))
        conectivities = h5file.create_dataset('connectivities', data=conn)
        num_nodes_elem_handle = h5file.create_dataset(
            'num_node_elem', data=num_node_elem)
        num_nodes_handle = h5file.create_dataset(
            'num_node', data=num_node)
        num_elem_handle = h5file.create_dataset(
            'num_elem', data=num_elem)
        stiffness_db_handle = h5file.create_dataset(
            'stiffness_db', data=stiffness)
        stiffness_handle = h5file.create_dataset(
            'elem_stiffness', data=elem_stiffness)
        mass_db_handle = h5file.create_dataset(
            'mass_db', data=mass)
        mass_handle = h5file.create_dataset(
            'elem_mass', data=elem_mass)
        frame_of_reference_delta_handle = h5file.create_dataset(
            'frame_of_reference_delta', data=frame_of_reference_delta)
        structural_twist_handle = h5file.create_dataset(
            'structural_twist', data=structural_twist)
        bocos_handle = h5file.create_dataset(
            'boundary_conditions', data=boundary_conditions)
        beam_handle = h5file.create_dataset(
            'beam_number', data=beam_number)
        app_forces_handle = h5file.create_dataset(
            'app_forces', data=app_forces)
        node_app_forces_handle = h5file.create_dataset(
            'node_app_forces', data=node_app_forces)


def generate_aero_file():
    global x, y, z
    airfoil_distribution = np.zeros((num_node,), dtype=int)
    surface_distribution = np.zeros((num_elem,), dtype=int) - 1
    surface_m = np.zeros((n_surfaces, ), dtype=int)
    m_distribution = 'uniform'
    aero_node = np.zeros((num_node,), dtype=bool)
    twist = np.zeros((num_node,))
    chord = np.zeros((num_node,))
    elastic_axis = np.zeros((num_node,))

    working_elem = 0
    working_node = 0
    # right wing (surface 0, beam 0)
    i_surf = 0
    airfoil_distribution[working_node:working_node + num_node_main] = 0
    surface_distribution[working_elem:working_elem + num_elem_main] = i_surf
    surface_m[i_surf] = m_main
    aero_node[working_node:working_node + num_node_main] = True
    chord[working_node:working_node + num_node_main] = main_chord
    elastic_axis[working_node:working_node + num_node_main] = main_ea
    working_elem += num_elem_main
    working_node += num_node_main

    # left wing (surface 1, beam 1)
    i_surf = 1
    airfoil_distribution[working_node:working_node + num_node_main - 1] = 0
    surface_distribution[working_elem:working_elem + num_elem_main] = i_surf
    surface_m[i_surf] = m_main
    aero_node[working_node:working_node + num_node_main - 1] = True
    chord[working_node:working_node + num_node_main - 1] = main_chord
    elastic_axis[working_node:working_node + num_node_main - 1] = main_ea
    working_elem += num_elem_main
    working_node += num_node_main - 1

    with h5.File(route + '/' + case_name + '.aero.h5', 'a') as h5file:
        airfoils_group = h5file.create_group('airfoils')
        # add one airfoil
        naca_airfoil_main = airfoils_group.create_dataset('0', data=np.column_stack(
                                generate_naca_camber(P=main_airfoil_P, M=main_airfoil_M)))
        # chord
        chord_input = h5file.create_dataset('chord', data=chord)
        dim_attr = chord_input .attrs['units'] = 'm'

        # twist
        twist_input = h5file.create_dataset('twist', data=twist)
        dim_attr = twist_input.attrs['units'] = 'rad'

        # airfoil distribution
        airfoil_distribution_input = h5file.create_dataset('airfoil_distribution', data=airfoil_distribution)

        surface_distribution_input = h5file.create_dataset('surface_distribution', data=surface_distribution)
        surface_m_input = h5file.create_dataset('surface_m', data=surface_m)
        m_distribution_input = h5file.create_dataset('m_distribution', data=m_distribution.encode('ascii', 'ignore'))

        aero_node_input = h5file.create_dataset('aero_node', data=aero_node)
        elastic_axis_input = h5file.create_dataset('elastic_axis', data=elastic_axis)


def generate_naca_camber(M=0, P=0):
    m = M*1e-2
    p = P*1e-1

    def naca(x, m, p):
        if x < 1e-6:
            return 0.0
        elif x < p:
            return m/(p*p)*(2*p*x - x*x)
        elif x > p and x < 1+1e-6:
            return m/((1-p)*(1-p))*(1 - 2*p + 2*p*x - x*x)

    x_vec = np.linspace(0, 1, 1000)
    y_vec = np.array([naca(x, m, p) for x in x_vec])
    return x_vec, y_vec


def generate_solver_file():
    file_name = route + '/' + case_name + '.solver.txt'
    config = configparser.ConfigParser()
    config['SHARPy'] = {'case': case_name,
                        'route': route,
                        'flow': 'BeamLoader, AerogridLoader, SteadyVelocityFieldGenerator'}

    config['BeamLoader'] = {'unsteady': 'off'}
    config['AeroGridLoader'] = {'unsteady': 'off',
                                'aligned_grid': 'on',
                                'freestream_dir': '1, 0, 0'}

    with open(file_name, 'w') as configfile:
        config.write(configfile)


# def generate_flightcon_file():
#     file_name = route + '/' + case_name + '.flightcon.txt'
#     config = configparser.ConfigParser()
#     config['FlightCon'] = {'u_inf': u_inf,
#                            'alpha': alpha,
#                            'beta': beta,
#                            'rho_inf': rho}
#
#     with open(file_name, 'w') as configfile:
#         config.write(configfile)


if __name__ == '__main__':
    clean_test_files()
    generate_fem_file()
    generate_solver_file()
    generate_aero_file()
    # generate_flightcon_file()








