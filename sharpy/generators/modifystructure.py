import numpy as np
import sharpy.utils.generator_interface as generator_interface
import sharpy.utils.settings as settings


@generator_interface.generator
class ModifyStructure(generator_interface.BaseGenerator):
    generator_id = 'ModifyStructure'

    settings_types = dict()
    settings_default = dict()
    settings_description = dict()
    settings_options = dict()

    settings_types['change_variable'] = 'list(str)'
    settings_default['change_variable'] = None
    settings_description['change_variable'] = 'Structural variable to modify'
    settings_options['change_variable'] = ['lumped_mass']

    settings_types['variable_index'] = 'list(int)'
    settings_default['variable_index'] = None
    settings_description['variable_index'] = 'Index of variable to change. For instance the 1st lumped mass.'

    settings_types['file_list'] = 'list(str)'
    settings_default['file_list'] = None
    settings_description['file_list'] = 'File path for each variable containing the changing info, in the appropriate ' \
                                        'format'

    def __init__(self):
        self.settings = None

        self.num_changes = None
        self.variables = []
        self.control_objects = {}

    def initialise(self, in_dict, structure):
        self.settings = in_dict
        settings.to_custom_types(self.settings, self.settings_types, self.settings_default, no_ctype=True,
                                 options=self.settings_options)

        self.num_changes = len(self.settings['change_variable'])

        if 'lumped_mass' in self.settings['change_variable']:
            self.control_objects['lumped_mass'] = LumpedMassControl()

        lumped_mass_variables = []
        for i in range(self.num_changes):
            var_type = self.settings['change_variable'][i]
            if var_type == 'lumped_mass':
                variable = ChangeLumpedMass(var_index=self.settings['variable_index'][i],
                                            file=self.settings['file_list'][i])
                variable.initialise(structure)

                self.variables.append(variable)
                lumped_mass_variables.append(i)
                self.control_objects['lumped_mass'].append(i)
            else:
                raise NotImplementedError('Variable {:s} not yet coded to be modified in runtime'.format(var_type))
        try:
            self.control_objects['lumped_mass'].set_unchanged_vars_to_zero(structure)
        except KeyError:
            pass

    def generate(self, params):
        data = params['data']
        ts = data.ts
        structure = data.structure
        # print('Time step: {:g}'.format(ts))

        for variable in self.variables:
            variable(structure, ts)

        # should only be called once per time step
        try:
            self.control_objects['lumped_mass'].execute_change(structure)
        except KeyError:
            pass

        # for future variables supported, have the control objects have the same signatures such that they may be
        # called in a loop


class ChangedVariable:

    def __init__(self, name, var_index, file):
        self.name = name
        self.variable_index = var_index
        self.file = file

        self.original = None
        self.target_value = None
        self.delta = None
        self.current_value = None  # initially

    def initialise(self, structure):

        self.get_original(structure)
        self.load_file()

        self.delta = self.target_value
        self.current_value = self.original  # initially

    def __call__(self, structure, ts):
        pass

    def get_original(self, structure):
        pass

    def load_file(self):
        self.target_value = np.loadtxt(self.file)


class ChangeLumpedMass(ChangedVariable):

    def __init__(self, var_index, file):
        super().__init__('lumped_mass', var_index=var_index, file=file)

    def __call__(self, structure, ts):
        try:
            delta = self.target_value[ts] - self.current_value
            structure.lumped_mass[self.variable_index] = delta[0]
            structure.lumped_mass_position[self.variable_index, :] = delta[1:4]
            ixx, iyy, izz, ixy, ixz, iyz = delta[-6:]
            inertia = np.block([[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]])
            structure.lumped_mass_inertia[self.variable_index, :, :] = inertia

            self.current_value += delta
        except IndexError:
            structure.lumped_mass[self.variable_index] = 0
            structure.lumped_mass_position[self.variable_index, :] = np.zeros(3)
            structure.lumped_mass_inertia[self.variable_index, :, :] = np.zeros((3, 3))

    def load_file(self):

        super().load_file()

        # if not enough column entries pad with original values
        n_values = len(self.original)
        if self.target_value.shape[1] != n_values:

            self.target_value = np.column_stack((self.target_value,
                                                 self.original[-(n_values - self.target_value.shape[1]):]
                                                 * np.ones((self.target_value.shape[0], n_values - self.target_value.shape[1])
                                                           )
                                                 ))

    def get_original(self, structure):
        m = structure.lumped_mass[self.variable_index]
        pos = structure.lumped_mass_position[self.variable_index, :]
        inertia = structure.lumped_mass_inertia[self.variable_index, :, :]

        self.original = np.hstack((m, pos, np.diag(inertia), inertia[0, 1], inertia[0, 2], inertia[1, 2]))


class LumpedMassControl:
    """Lumped Mass Control Class

    This class is instantiated when at least one lumped mass is modified.

    It allows control over unchanged lumped masses and calls the method to execute the change.
    """
    def __init__(self):
        self.lumped_mass_variables = []

    def set_unchanged_vars_to_zero(self, structure):
        """
        Sets the lumped masses variables of unchanged lumped masses to zero.

        This is to avoid the lumped mass changing during execution

        Args:
            structure (sharpy.structure.models.beam.Beam): SHARPy structure object

        """
        for i_lumped_mass in range(len(structure.lumped_mass)):
            if i_lumped_mass not in self.lumped_mass_variables:
                structure.lumped_mass[i_lumped_mass] *= 0
                structure.lumped_mass_position[i_lumped_mass] *= 0
                structure.lumped_mass_inertia[i_lumped_mass] *= 0

    @staticmethod
    def execute_change(structure):
        """Executes the change in the lumped masses.

        Called only once per time step when all the changed lumped mass variables have been processed.
        """
        # called once all variables changed
        structure.lump_masses()
        structure.generate_fortran()

    def append(self, i):
        self.lumped_mass_variables.append(i)
