"""
This module contains objects related to experimental design abstractions.
Public objects are imported in ``__init__.py``.

"""
import itertools
import collections
from copy import copy
import numpy as np

import experimentator.order as order
from collections import ChainMap

Level = collections.namedtuple('Level', ('name', 'design'))


class Design:
    """
    :class:`Design` instances specify the experimental design at one level of the experimental hierarchy.
    They guide the creation of :class:`~experimentator.section.ExperimentSection` instances
    by parsing design matrices or crossing independent variables (IVs).

    Parameters
    ----------
    ivs : dict or list of tuple, optional
        Independent variables can be specified in two ways:
           1. A dictionary mapping strings (IV names) to lists (levels of the IV).
              *Note: if you use this format, you cannot rely on the order of the IVs*
              (unless you use a :class:`collections.OrderedDict`).
           2. A list of (IV name, IV levels) tuples.
        If an IV takes continuous values, use ``None`` for its levels.
        This only works when specifying values using `design_matrix`.
    design_matrix : array-like, optional
        A :class:`numpy.ndarray` (or convertible, e.g. a list-of-lists)
        representing a design matrix specifying how IV values should be grouped to form conditions.
        Design matrices generated by `pyDOE <http://pythonhosted.org//pyDOE/index.html>`_ are compatible.
        Each column represents one IV, and each row represents one condition.
        Values of elements in this matrix are interpreted in two ways:
            1. If the levels of the IV were passed as ``None`` in `ivs`,
               then the values in the array are interpreted "at face value", i.e. as IV values.
            2. Otherwise, each element from the list of IV values is associated with
               a unique value in a column (in order of value).
               For example, if an IV has two levels (e.g. ``[True, False]``)
               then the corresponding column of `design_matrix` should have two unique values.
               If they are ``0`` and ``1``, they are associated with ``True`` and ``False``, respectively.
               Similarly, they could be ``1`` and ``2``, or any two non-equal values.
        Note that a design matrix also specifies the order of the conditions.
        For this reason, the default `ordering` changes
        from :class:`order.Shuffle <experiment.order.Shuffle>
        to :class:`order.Ordering <experimentator.order.Ordering>`,
        preserving the order of the conditions.
        When no `design_matrix` is passed, IVs are fully crossed.
    ordering : Ordering, optional
        An instance of an :class:`order.Ordering <experimentator.order.Ordering>` subclass
        defining the behavior for duplicating and ordering the conditions of the :class:`Design`.
        The default is :class:`order.Shuffle <experiment.order.Shuffle>` unless a `design_matrix` is passed.
    extra_data : dict, optional
        Items from this dictionary will be included in the ``data`` attribute
        of any :class:`~experimentator.section.ExperimentSection` instances
        created with this :class:`Design`.

    Attributes
    ----------
    iv_names : list of str
    iv_values : list of tuple
    design_matrix : array-like
    extra_data : dict
    ordering : :class:`experimentator.order.Ordering`
    heterogeneous_design_iv_name : str
        The IV name that triggers a heterogeneous (i.e., branching) tree structure when it is encountered.
        ``'design'`` by default.
    is_heterogeneous
    branches

    See Also
    --------
    experimentator.order
    DesignTree

    Examples
    --------
    >>> from experimentator.order import Shuffle
    >>> design = Design(ivs={'side': ['left', 'right'], 'difficulty': ['easy', 'hard']}, ordering=Shuffle(2))
    >>> design.first_pass()
    ((), ())
    >>> design.get_order()
    [{'difficulty': 'easy', 'side': 'left'},
     {'difficulty': 'hard', 'side': 'left'},
     {'difficulty': 'easy', 'side': 'left'},
     {'difficulty': 'hard', 'side': 'right'},
     {'difficulty': 'easy', 'side': 'right'},
     {'difficulty': 'easy', 'side': 'right'},
     {'difficulty': 'hard', 'side': 'left'},
     {'difficulty': 'hard', 'side': 'right'}]

    """
    heterogeneous_design_iv_name = 'design'

    def __init__(self, ivs=None, design_matrix=None, ordering=None, extra_data=None):
        if isinstance(ivs, dict):
            ivs = list(ivs.items())
        if ivs:
            iv_names, iv_values = zip(*ivs)
            self.iv_names = list(iv_names)
            self.iv_values = list(iv_values)
        else:
            self.iv_names = []
            self.iv_values = []

        self.design_matrix = design_matrix
        self.extra_data = extra_data or {}

        if ordering:
            self.ordering = ordering
        elif design_matrix is None:
            self.ordering = order.Shuffle()
        else:
            self.ordering = order.Ordering()

        if self.design_matrix is None and any(iv_values is None for iv_values in self.iv_values):
            raise TypeError('Must specify a design matrix if using continuous IVs (values=None)')

    @classmethod
    def from_dict(cls, spec):
        """
        Constructs a :class:`Design` instance from a dictionary-based specification
        (e.g., parsed from a YAML file).

        Parameters
        ----------
        spec : dict
            A dictionary containing some of the following keys (all optional):
                - ``'ivs'``, ``'design_matrix'``, ``'extra_data'``:, interpreted as
                  keyword arguments to the :class:`Design` constructor.
                - ``'order'`` or ``'ordering'``, determining the ``ordering`` keyword argument.
                    - If the value is a string, it is it interpreted as a class name from :mod:`experimentator.order`.
                    - If the value is a dictionary, the key ``'class'`` should contain the class name,
                      and the rest of the items are interpreted as keyword arguments to its constructor.
                    - If the value is a sequence, then the first element is interpreted as the class name
                      and the following as positional arguments.
                - ``'n'`` or ``'number'``, interpreted as the ``number`` argument to
                  the specified :class:`~experimentator.order.Ordering`.
                - Finally, any fields not otherwise used are passed to the :class:`Design` constructor
                  as the ``extra_data`` argument.

        Returns
        -------
        name : str
            Only returned if `spec` contains a field ``'name'``.
        design : :class:`Design`

        See Also
        --------
        DesignTree.from_spec

        Examples
        --------
        >>> design_spec = {
        ...'name': 'block',
        ...'ivs': {'speed': [1, 2, 3], 'size': [15, 30]},
        ...'ordering': 'Shuffle',
        ...'n': 3}
        >>> Design.from_dict(design_spec)
        Level(name='block', design=Design(ivs=[('speed', [1, 2, 3]), ('size', [15, 30])], design_matrix=None, ordering=Shuffle(number=3, avoid_repeats=False), extra_data={}))

        """
        inputs = spec.copy()

        ordering_spec = inputs.pop('ordering', inputs.pop('order', None))
        ordering_class = 'Ordering' if 'design_matrix' in inputs else 'Shuffle'
        ordering_args = ()
        number = inputs.pop('number', inputs.pop('n', None))
        ordering_kwargs = {'number': number} if number else {}

        name = inputs.pop('name', None)
        design_kwargs = {key: inputs.get(key)
                         for key in inputs
                         if key in ('ivs', 'design_matrix', 'extra_data')}
        inputs.pop('ivs', None)
        inputs.pop('design_matrix', None)
        inputs.pop('extra_data', None)
        design_kwargs['extra_data'] = inputs

        if isinstance(ordering_spec, str):
            ordering_class = ordering_spec

        elif isinstance(ordering_spec, dict):
            ordering_class = ordering_spec.pop('class', ordering_class)
            ordering_kwargs.update(ordering_spec)

        elif isinstance(ordering_spec, collections.Sequence):
            ordering_class = ordering_spec[0]
            ordering_args = ordering_spec[1:]

        ordering = getattr(order, ordering_class)(*ordering_args, **ordering_kwargs)

        self = cls(ordering=ordering, **design_kwargs)
        if name:
            return Level(name, self)
        else:
            return self

    def __repr__(self):
        return 'Design(ivs={}, design_matrix={}, ordering={}, extra_data={})'.format(
            list(zip(self.iv_names, self.iv_values)), self.design_matrix, self.ordering, self.extra_data)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__

    def get_order(self, data=None):
        """Order the conditions.

        Returns
        -------
        list of dict
            A list of dictionaries, each specifying a condition (a mapping from IV names to values).

        """
        condition_order = self.ordering.get_order(data)
        for condition in condition_order:
            condition.update(self.extra_data)
        return condition_order

    def first_pass(self):
        """Initialize design.

        Initializes the design by parsing the design matrix or crossing the IVs
        If a :class:`~experimentator.order.NonAtomicOrdering` is used,
        an additional IV will be returned which should be incorporated into the design
        one level up in the experimental hierarchy.
        For this reason, the `first_pass` methods in a hierarchy of :class:`Design` instances
        should be called in reverse order, from bottom up.
        Use a :class:`DesignTree` to ensure this occurs properly.

        Returns
        -------
        iv_name : str or tuple
            The name of the IV, for non-atomic orderings. Otherwise, an empty tuple.
        iv_values : tuple
            The possible values of the IV. Empty for atomic orderings.

        """
        if self.design_matrix is not None:
            if not np.shape(self.design_matrix)[1] == len(self.iv_names):
                raise TypeError("Size of design matrix doesn't match number of IVs")

            all_conditions = self._parse_design_matrix(self.design_matrix)

        else:
            all_conditions = self.full_cross(self.iv_names, self.iv_values)

        return self.ordering.first_pass(all_conditions)

    def update(self, names, values):
        """Add independent variable(s).

        Adds additional independent variables to a :class:`Design` instance.
        This will have no effect after :meth:`Design.first_pass` has been called.

        Parameters
        ----------
        names : list of str
            Names of IVs to add.
        values : list of list
            For each IV, a list of possible values.

        """
        self.iv_names.extend(names)
        self.iv_values.extend(values)

    @staticmethod
    def full_cross(iv_names, iv_values):
        """Factorial cross.

        Performs a full factorial cross of the independent variables.
        Yields dictionaries, each describing one condition, a mapping from IV names to IV values.
        One dictionary is yielded for every possible combination of IV values.

        Parameters
        ----------
        iv_names : list of str
            Names of IVs.
        iv_values : list of list
            Each element defines the possible values of an IV.
            Must be the same length as `iv_names`.
            Its elements must be hashable.

        """
        iv_combinations = itertools.product(*iv_values)

        yield from (dict(zip(iv_names, iv_combination)) for iv_combination in iv_combinations)

    def _parse_design_matrix(self, design_matrix):
        values_per_factor = [np.unique(column) for column in np.transpose(design_matrix)]
        if any(iv_values and not len(iv_values) == len(values)
               for iv_values, values in zip(self.iv_values, values_per_factor)):
            raise ValueError('Unique elements in design matrix do not match number of values in IV definition')

        conditions = []
        for row in design_matrix:
            condition = self.extra_data.copy()
            for iv_name, iv_values, factor_values, design_matrix_value in zip(
                    self.iv_names, self.iv_values, values_per_factor, row):
                if iv_values:
                    condition.update({iv_name: np.array(iv_values)[factor_values == design_matrix_value][0]})
                else:
                    condition.update({iv_name: design_matrix_value})
            conditions.append(condition)

        return conditions

    @property
    def is_heterogeneous(self):
        """
        True if this :class:`Design` is the last level before the tree structure diverges.

        """
        return self.heterogeneous_design_iv_name in self.iv_names

    @property
    def branches(self):
        """
        The IV names corresponding to named heterogeneous branches
        in the tree structure following this :class:`Design`.

        """
        return dict(zip(self.iv_names, self.iv_values)).get(self.heterogeneous_design_iv_name, ())


class DesignTree:
    """
    A container for :class:`Design` instances, describing the entire hierarchy of a basic
    :class:`~experimentator.experiment.Experiment`.
    :class:`DesignTree` instances are iterators; calling ``next`` on one
    will return another :class:`DesignTree` with the top level removed.
    In this way, the entire experimental hierarchy can be created by recursively calling ``next``.

    Parameters
    ----------
    levels_and_designs : OrderedDict or list of tuple
        This input defines the structure of the tree,
        and is either an :class:`~collections.OrderedDict` or a list of 2-tuples.
        Keys (or first element of each tuple) are level names.
        Values (or second element of each tuple) are design specifications,
        in the form of either a :class:`Design` instance, or a list of :class:`Design` instances to occur in sequence.

    **other_designs
        Named design trees, can be other :class:`DesignTree` instances
        or suitable `levels_and_designs` inputs (i.e., :class:`~collections.OrderedDict` or list of tuples).
        These designs allow for heterogeneous design structures
        (i.e. not every section at the same level has the same :class:`Design`).
        To make a heterogeneous :class:`DesignTree`,
        use an IV named ``'design'`` at the level where the heterogeneity should occur.
        Values of this IV should be strings,
        each corresponding to the name of a :class:`DesignTree` from` other_designs`.
        The value of the IV ``'design'`` at each section
        determines which :class:`DesignTree` is used for children of that section.

    Attributes
    ----------
    levels_and_designs : list of tuple
    other_designs : dict
    branches : dict
        Only those items from `other_designs` that follow directly from this tree.

    Notes
    -----
    Calling ``next`` on the last level of a heterogeneous :class:`DesignTree`
    will return a dictionary of named :class:`DesignTree` instances
    (rather than a single :class:`DesignTree` instance).
    The keys are the possible values of the IV ``'design'``
    and the values are the corresponding :class:`DesignTree` instances.

    """
    def __init__(self, levels_and_designs, **other_designs):
        self.other_designs = other_designs

        if isinstance(levels_and_designs, collections.OrderedDict):
            levels_and_designs = list(levels_and_designs.items())

        # Check for singleton Designs.
        for i, (level, design) in enumerate(levels_and_designs):
            if isinstance(design, Design):
                levels_and_designs[i] = (level, [design])

        # Convert to namedtuples.
        self.levels_and_designs = [Level(*level) for level in levels_and_designs]

        # Handle heterogeneous trees.
        bottom_level_design = self.levels_and_designs[-1].design[0]
        if bottom_level_design.is_heterogeneous:
            self.branches = {name: branch for name, branch in other_designs.items()
                             if branch in bottom_level_design.branches and isinstance(branch, DesignTree)}
            for branch_name in bottom_level_design.branches:
                if branch_name not in self.branches:
                    designs_to_pass = other_designs.copy()
                    del designs_to_pass[branch_name]
                    tree = DesignTree(other_designs[branch_name], **designs_to_pass)
                    self.branches[branch_name] = tree

        else:
            self.branches = {}

        top_level_iv_names, _ = self.first_pass(self.levels_and_designs)
        if top_level_iv_names:
            raise ValueError('Cannot have a non-atomic ordering at the top level of a DesignTree. ' +
                             'The recommended workaround is to insert a "dummy level" with no IVs and number=1.')

    @classmethod
    def from_spec(cls, spec):
        """
        Constructs a :class:`DesignTree` instance from a specification (e.g., parsed from a YAML file).

        spec : dict or list
            The :class:`DesignTree` specification.
            A dictionary with keys as tree names and values as lists of dictionaries.
            Each dictionary should specify a :class:`Design` according to :meth:`Design.from_dict`.
            The main tree should be named ``'main'``.
            Other names are used for generating heterogeneous trees
            (see :class:`DesignTree` docs).
            A homogeneous tree can be specified as a dictionary with only a single key ``'main'``,
            or directly as a list of dictionaries

        Returns
        -------
        :class:`DesignTree`

        """
        if isinstance(spec, dict):
            # The normal case.
            main_tree = list(cls._design_specs_to_designs(spec.pop('main')))
            other_trees = {name: list(cls._design_specs_to_designs(specs)) for name, specs in spec.items()}
        else:
            # Only a main design.
            main_tree = list(cls._design_specs_to_designs(spec))
            other_trees = {}

        return cls(main_tree, **other_trees)

    @staticmethod
    def _design_specs_to_designs(specs):
        for spec in specs:
            if isinstance(spec, dict):
                name_and_design = Design.from_dict(spec)
                if isinstance(name_and_design, Design):
                    yield None, name_and_design
                else:
                    yield name_and_design

            else:
                name = None
                designs = []
                for design_spec in spec:
                    name_and_design = Design.from_dict(design_spec)
                    if isinstance(name_and_design, Design):
                        designs.append(name_and_design)
                    else:
                        if name and name_and_design[0] != name:
                            raise ValueError('Designs at the same level must have the same name')
                        name = name_and_design[0]
                        designs.append(name_and_design[1])

                yield name, designs

    def __repr__(self):
        if self.levels_and_designs[0].name == '_base':
            levels_and_designs = self.levels_and_designs[1:]
        else:
            levels_and_designs = self.levels_and_designs
        return 'DesignTree({}{}{})'.format(
            levels_and_designs, ', ' if self.other_designs else '',
            ', '.join('{}={}'.format(*other_design) for other_design in self.other_designs.items()))

    def __next__(self):
        if len(self) == 1:
            raise StopIteration

        if len(self.levels_and_designs) == 1:
            return self.branches

        next_design = copy(self)
        next_design.levels_and_designs = next_design.levels_and_designs[1:]
        return next_design

    def __len__(self):
        length = len(self.levels_and_designs)
        if self.branches:
            length += len(list(self.branches.values())[0])
        return length

    def __getitem__(self, item):
        return self.levels_and_designs[item]

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__

    @staticmethod
    def first_pass(levels_and_designs):
        """
        Make a first pass of all designs in a design tree, from bottom to top.
        This calls :meth:`Design.first_pass` on every :class:`Design` instance in the tree,
        in the proper order, updating designs when a new IV is returned.
        This is necessary for non-atomic orderings,
        which create an additional IV for the :class:`Design` one level up.

        Returns
        -------
        iv_names, iv_values
            IVs for a non-atomic sort at the top level of the tree, if any (there shouldn't be).

        """
        for (level, designs), (level_above, designs_above) in \
                zip(reversed(levels_and_designs[1:]), reversed(levels_and_designs[:-1])):

            # Call first_pass and add new IVs.
            new_iv_names = []
            new_iv_values = []
            for design in designs:
                iv_name, iv_values = design.first_pass()
                if iv_name:
                    new_iv_names.append(iv_name)
                    new_iv_values.append(iv_values)
            for design in designs_above:
                design.update(new_iv_names, new_iv_values)

        # And call first pass of the top level.
        iv_names, iv_values = (), ()
        for design in levels_and_designs[0].design:
            iv_names, iv_values = design.first_pass()

        return iv_names, iv_values

    def add_base_level(self):
        """
        Adds a section to the top of the tree called ``'_base'``.
        This makes the :class:`DesignTree` suitable for constructing an :class:`~experimentator.experiment.Experiment`.

        Notes
        -----
        The :class:`~experimentator.experiment.Experiment` constructor calls this automatically,
        and this shouldn't be called when appending a tree to an existing
        :class:`~experimentator.experiment.Experiment`,
        so there is no reason to manually call this method.

        """
        levels_and_designs = [Level('_base', Design())]
        levels_and_designs.extend(self.levels_and_designs)
        self.levels_and_designs = levels_and_designs
