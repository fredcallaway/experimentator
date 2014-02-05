<sub>_This project is hosted on both [bitbucket](https://bitbucket.org/hharrison/experimentator) and [github](https://github.com/hsharrison/experimentator). The bitbucket repository is considered canonical; however the github repository is almost always up-to-date. Issues can be tracked on either website, but github is preferred._</sub>

experimentator
==============

`experimentator` is a Python package for designing, constructing, and running experiments in Python. Its original purpose was for Psychology experiments, in which participants  interact with the terminal or, more commonly, a graphical interface, but there is nothing domain-specific; `experimentator` will be useful for any kind of experiment run with the aid of a computer. The basic use case is that you have already written code to run a single trial and would like to run a set of experimental sessions in which inputs to your trial function are systematically varied and repeated.

`experimentator` requires Python 3.3 or later. It is not Python 2.7-compatible (if you wish it to be, consider contributing your time to the project to make it happen). Additionally, it requires the third-party libraries [`pandas`](http://pandas.pydata.org/) (`v0.13.0` or later) to access experimental data, and [`docopt`](http://docopt.org/) (`v0.6.1` or later) to use the command-line interface. The full install process, then is (assuming you are in a Python 3.3 `virtualenv`):

    pip install pandas>=0.13.0
    pip install docopt>=0.6.1

    hg clone https://bitbucket.org/hharrison/experimentator
    # or
    git clone https://github.com/hsharrison/experimentator

    cd experimentator
    python setup.py install


Overview
-----
In `experimentator`, an `Experiment` is defined as a set of experimental sections arranged in a tree-like hierarchy. The 'standard' levels of the hierarchy are `('participant', 'session', 'block, 'trial')`. Each level can contain any number of sections on the level immediately below. An experiment might consist of 20 participants, each of which contains 2 sessions, each of which contains 4 blocks, etc. A simple experiment containing, for example, 1 block per session and 1 session per participant, could simplify the levels to `('participant', 'trial')`. Alternatively, different names altogether could be assigned to the levels.

Traditionally, independent variables (IVs) are categorized as varying over participants (in a _between-subjects_ design) or over trials (in a _within-subjects_ design). To be more specific, however, a variable can be associated with any level. For the standard levels of the experimental hierarchy, a between-subjects variable changes every participant, however a within-subjects variable could take on a new value every session, every block, or every trial.

Each IV is associated with a keywork argument to the function that defines a trial (or whatever you name the lowest level of your experimental structure), called the 'run' callback. If your run callback is declared as:

    def run_trial(session_data, persistent_data, target='center', congruent=True)

then your experiment has two IVs, one named `target` and the other named `congruent`. Of course, if you don't need to vary a keyword argument, you could rely on its default in the method declaration, set the variable within the function, or use a config file (described later).

Side note: All callbacks in `experimentator` receive dictionaries `session_data` and `persistent_data` as positional arguments. `session_data` is an empty dictionary every time you load the experiment from disk, but within an experimental session it is persistent. Use it to store experimental state, for example a session score that persists from trial-to-trial or perhaps objects that reference external sound or video files. The term 'session' in `session_data` does not refer to the experiment section 'session', but rather a session of the Python interpreter. The dictionary `persistent_data` is a place to store data that will persist over the course of the entire experiment. This is used, for example, to store data from the experiment's config file, if there is one (see section on config files below). Do not manually store data in `persistent_data` that isn't picklable (e.g. `ctypes`).


Usage
-----
First, create an `Experiment` instance, as so:

    my_experiment = Experiment(config_file='config.ini',
                               experiment_file='experiment.dat')


`config_file` defines the structure of the experiment (syntax below), and `experiment_file` is a location to save the experiment instance (so that additional sessions can be run after closing the Python interpreter).

Once you create your experiment, assign a function as its 'run' callback to define a single trial.

    def run_trial(session_data, experiment_data, target='center', congruent=True, **_):
        ...
        return {'reaction_time': rt, 'choice': response}

    my_experiment.set_run_callback(run_trial)

The 'run' callback return its results in the form of a dictionary, which can be accessed later in the format of a `Pandas DataFrame` by the instance property `Experiment.data`. Every IV in the tree will be passed to the callback as a keyword argument, including those used only at a higher level. This includes section numbers (e.g., `participant=2, block=1, trial=12`). For this reason, all callback functions should include keyword argument expansion (`**_` here).

You can also define functions to run before, between, and after sections of your experiment using the methods `set_start_callback`, `set_inter_callback`, and `set_end_callback`. The only difference from the `set_run_callback` method is that these methods also require the level name. For example:

    def short_pause(session_data, experiment_data, **_):
        time.sleep(1)

    my_experiment.set_inter_callback('trial', short_pause)

These functions will also be passed all IVs defined at their level or above (`inter` functions are passed the variables for the _next_ section), so keyword expansion should be used here as well.

#### Context managers: An alternative to start and end callbacks

You can also use Python's context manager objects instead of or in addition to start and end callbacks, to define behavior that occurs at the beginning and end of every section at a particular level. You may be familiar with context managers as functions that are typically used in [Python's `with` statement](http://docs.python.org/3.3/reference/compound_stmts.html#with).

Context managers have two advantages over start and end callbacks. First, they can return values (in a `with` statement, the return variable is set using the `as` keyword) which in `experimentator` are stored in the `Experiment.session_data` dictionary. Second, you can use a [`try` statement](http://docs.python.org/3.3/reference/compound_stmts.html#try) in your context manager to ensure that your cleanup (the code that would otherwise be in your end callback) executes even if an error is encountered while running the section.

The easiest way to create a context manager is with the [`contextlib.contextmanager`](http://docs.python.org/3.3/library/contextlib.html#contextlib.contextmanager) decorator. In the context of `experimentator`, use it like this:

    from contextlib import contextmanager

    @contextmanager
    def session_context():
        window = open_window()  # A made-up example function.

        try:
            yield window

        finally:
            window.close()


    my_experiment.set_contextmanager('session', session_context)
    my_experiment.save()


To explain:
* Any code before the `yield` statement is executed before the section is run. This is the equivalent of a start callback.
* The `yield` statement marks where the section will be run. It is not necessary to yield any variables, but if you do, they are available to other functions as `my_experiment.session_data['as'][level]`. In this example, the variable `window` can be accessed during the session by `my_experiment.session_data['as']['session']`.
* Any code after the `yield` statement is executed after the section is run, the equivalent of an end callback.
* Use a `try`/`finally` statement to ensure code will be run in the case of an error occurring. Any code in a `finally` block is executed after the section ends, _or_ in case any error occurs during the `try` block. However, this isn't always necessary: if you don't have any code to run unconditionally, you can write a context manager without a `try`/`finally` statement.

For more on context managers, including other ways to create them, see [the documentation for `contextlib` in the standard library](http://docs.python.org/3.3/library/contextlib.html).


Config file format
-------
    [Experiment]
    levels = semicolon-separated list
    orderings = calls to experimentator.ordering classes, separated by semicolons

    [Independent Variables]
    variable_name = level; semicolon-separated list of values

In the `Experiment` section, all three lines should have the same number of items, separated by commas. The `levels` setting names the levels, and the `orderings` setting defines how they are ordered (and possibly repeated; more on ordering methods below).

Each setting in the `Independent Variables` section (that is, the name to the left of the `=`) is interpreted as a variable name. The entry string (to the right of the `=`) is interpreted as a semicolon-separated list. The first element should match one of the levels specified in the Experiment section. This is the level to associate this variable with--the level it varies over. The other elements are the possible values of the IV. These strings are evaluated by the Python interpreter, so proper syntax should be used for values that aren't simple numbers (this allows your IVs to take on values of dictionaries or lists, for example). This means, for example, that values that are strings should be enclosed in quotes.

Other sections of the config file are saved as dicts in the experiment's `persistent_data` attribute. Fonts and colors are parsed according to the formats below (purely for your convenience to use them in your experiment--`experimentator` does not use fonts or colors in any way), and are identified by either appearing in their own sections 'Fonts' and 'Colors' are on their own line with the label 'font' or 'color'. Everything else will be parsed as strings, so it is up to you to change types on elements of `persistent_data` after your experiment instance is created.

Colors are three integers separated by commas, and fonts are a string and then an integer. For example:

    [Colors]
    white = 255, 255, 255
    black = 0, 0, 0

    [Fonts]
    title = Times, 48
    text = Monaco, 12

    [Score]
    color = 255, 0, 255
    font = Garamond, 24
    points_to_win = 100

This example will produce the following `persistent data`:

    {'colors': {'white': (255, 255, 255), 'black': 0, 0, 0},
     'fonts': {'title': ('Times', 48), 'text': ('Monaco', 12)},
     'score': {'color': (255, 0, 255), 'font': ('Garamond', 24), 'points_to_win': '100'},
    }

Note that all section names are transformed to lowercase.


A more complete example
---

`config.ini`:

    [Experiment]
    levels = participant; block; trial
    orderings = Shuffle(6); Shuffle(3); Shuffle(50)

    [Independent Variables]
    target = trial; 'left'; 'center'; 'right'
    congruent = trial; False; True
    dual_task = participant; False; True


`dual_task.py`:

    from experimentator import Experiment

    def run_trial(session_data, experiment_data, target='center', congruent=True, dual_task=False, **_):
        # Code that works the display and records response.
        return dict(correct=correct, rt=rt)

    def initialize_display(session_data, experiment_data, **_):
        # Code that sets up the display.

    def close_display(session_data, experiment_data, **_):
        # Code that closes the display.

    def offer_break(session_data, experiment_data, **_):
        # Code that gives an opportunity to take a break.


    if __name__ == '__main__':
        dual_task_experiment = Experiment(config_file='config.ini',
                                          experiment_file='dual_task.dat')
        dual_task_experiment.set_run_callback(run_trial)
        dual_task_experiment.set_start_callback('participant', initialize_display)
        dual_task_experiment.set_inter_callback('block', offer_break)
        dual_task_experiment.set_end_callback('participant', close_display)
        dual_task_experiment.save()

This experiment has a mixed design, with one between-subjects IV, `dual_task`, and two within-subjects IVs, `target` and `congruent`. Each session will have 150 trials, organized into 3 blocks, with 12 participants. The `'block'` level in this experiment is only organizational (as it has no associated IVs) and merely facilitates calls to `offer_break`.

The technique of only creating the experiment instance in the `if __name__ == '__main__'` block is important, because later when you run a participant, `experimentator` will import `dual_task_experiment.py` to reload the callback functions. If `my_experiment.save()` is called during this reloading, it risks overwriting the original data file. This way, the experiment file (`dual_task.dat` in this case--but note that the file extension is irrelevant) will only be created when `python dual_task.py` is called directly. Note that after running an experimental session, the experiment file is automatically saved.


Running a session (finally)
-------

The `experimentator` module has a command-line interface for running sections of an already-created experiment. You must use the `-m` flag to tell python to access the package's command-line interface. Here the syntax, the output of `python -m experimentator --help` (assuming you are in a `virtualenv` where `python` points to Python 3.3):

    Usage:
      experimentator run <experiment_file> (--next <level>  [--not-finished] | (<level> <n>)...) [--demo] [--debug]
      experimentator  export <experiment_file> <data_file> [--debug]
      experimentator -h | --help
      experimentator --version


    Commands:
      run <experiment_file> --next <level>      Runs the first <level> that hasn't started. E.g.:
                                                  experimentator.py run experiment1.dat --next session

      run <experiment_file> (<level> <n>)...    Runs the section specified by any number of level=n pairs. E.g.:
                                                  experimentator.py run experiment1.dat participant 3 session 1

      export <experiment_file> <data_file>      Export the data in <experiment_file> to csv format as <data_file>.
                                                  Note: This will not produce readable csv files for experiments with
                                                        results in multi-element data structures (e.g., timeseries, dicts).

    Options:
      --not-finished     Run the next <level> that hasn't finished.
      --demo             Don't save data.
      --debug            Set logging level to DEBUG.
      -h, --help         Show this screen.
      --version          Print the installed version number of experimentator.


To continue the example above, you could run an experiment by calling `python -m experimentator run dual_task.dat --next participant`. Or, if something goes wrong and you want to re-run a particular participant, you could run `python -m experimentator run dual_task.dat participant 1`. Note that you must execute these commands from a directory containing _both_ the data file (`dual_task.dat` in this example) _and_ the original script (`dual_task.py`).

It is recommended that you create an alias for `python -m experimentator`. In Ubuntu, for example, add the following line to `~/.bash_aliases` (create it if it doesn't exist):

    alias exp='python -m experimentator'


Ordering methods
-----

Ordering methods are defined in `experimentator.orderings` as classes. Orderings handle the combinations of IV values to form unique conditions, the ordering of the unique conditions, and the duplication of unique conditions if specified with the `number` parameter. The following classes are available:

    Ordering(number=1)
The base class. Using this will create every section in the same order. The `number` parameter duplicates the entire order (as opposed to each condition separately). For example, with two IVs taking levels of `iv1 = ('A', 'B')` and `iv2 = ('a', 'b')`, `Ordering(2)` will probably produce the order `('Aa', 'Ab', 'Ba', 'Bb', 'Aa', 'Ab', 'Ba', 'Bb')`. The order is non-deterministic--it is usually predictable based on the order the IVs were defined but it is not guaranteed to be stable across Python versions or implementations (if you wish to be able to specify a particular order, submit an issue or a pull request, or go in and manually rearrange the sections after your experiment instance is created; see below for more on how to do this).

    Shuffle(number=1, avoid_repeats=False)
This ordering method randomly shuffles the sections, _after_ duplicating the unique sections. If `avoid_repeats==True`, there will be no identical conditions back-to-back.

#### Non-atomic orderings

Non-atomic orderings are orderings that are not independent between sections. For example, if you want to make sure that the possible block orders are evenly distributed within participants (a counterbalanced design), that means that each participant section can't decide independently how to order the blocks--the orderings must be managed by the parent level of the experimental hierarchy (in this example of counterbalanced blocks, the 'base section'--the experiment itself--must tell each participant what block order to use).

Non-atomic orderings work by creating a new independent variable `'order'` one level up. In the above example, when a participant section orders its blocks, it consults its IV `order`. The order, among participants, in which the various block orders appear depends on the ordering method at the participant level. Note that this happens automatically, so you should not define an IV called `order` or it will be overwritten.

     CompleteCounterbalance(number=1)
In a complete-counterbalance, every unique ordering of the conditions appears the same numbers of times. Be warned that the number of possible orderings can get very large very quickly. Therefore, this is only recommended with a small number of conditions.

The number of unique orderings (and therefore, values of the IV `'order'` one level up) can be determined by `factorial(number * n_conditions) // factorial(number)**n_conditions`. For example, there are 120 possible orderings of 5 conditions. With 3 conditions and `number=2`, there are 90 unique orderings.

The IV `'order'` created one level up takes integers as its value, which `CompleteCounterbalance` uses as keys to define the unique orders.

    Sorted(number=1, order='both')
This ordering method sorts the conditions based on the value of the IV defined at its level. To avoid ambiguity, it can only be used for levels with a single IV. The parameter `order` can be any of `('both', 'ascending', 'descending')`. For the final two, there is no need to create the IV `order` on level up, because all sections are sorted the same way. However, for the default `order='both'`, an IV `'order'` is created one level up, with possible values `'ascending'` and `'descending'`. That is, half the sections will be created in ascending order, and half in descending order.

    LatinSquare(number=1, uniform=True)
This orders your sections according to a [Latin square](http://en.wikipedia.org/wiki/Latin_square) with order equal to the number of unique conditions at the level. The values of the `'order'` IV one level up will be equal to the order of the Latin square. If `number > 1`, each ordering is duplicated _after_ computing the Latin square. For example, with `number=2` and 2x2 IVs (4 total conditions), then 4 unique orderings will be generated, each consisting of a 4-condition sequence repeated twice.

Note that the algorithm for computing Latin squares is not very efficient. Setting the keyword argument `uniform=False` will relax the requirement that the Latin square be sampled from a uniform distribution of Latin squares, allowing the algorithm to run faster. On the test PC, with `uniform=True` the computation time jumps from seconds to minutes between orders 5 and 6; with `uniform=False` the algorithm can generate a latin square up to about an order of 10 before jumping from seconds to minutes. Higher than that, computation time will increase rapidly.

#### Ordering methods in the config file

In the config file, ordering methods appear in the `[Experiment]` section, as a semicolon-separated list. Each item should be interpretable as a call to define an instance of an Ordering method in `experimentator.orderings`. However, if you are not using any arguments in your call, you can leave off the parentheses. For example:

    [Experiment]
    levels = participant, block, trial
    orderings = Shuffle(4), CompleteCounterbalance, Shuffle(3)


A final note: Manually tweaking the experiment
-----

Until the API becomes more flexible, it's useful to know the `Experiment.add_section` method. For example, if you're unhappy about having to define the number of participants in advance, keep in mind that you can always add more later using this method. It works like this:

    from experimentator import load_experiment
    exp = load_experiment('my_experiment.dat')

    exp.add_section()
    exp.save()

Any keyword arguments to `add_section` define IV values. Any IV values (at the level of the section you're adding) you don't define will be chosen randomly. You can also specify sections, for example `add_section(participant=1, ...)` adds a block (or whatever is the next level below participant) to the first participant.

You can also use the `ExperimentSection.children` attribute to inspect and rearrange sections. Use the `Experiment.section` method to get the `ExperimentSection` instance, and then the `ExperimentSection.children` attribute is a list of `ExperimentSection` instances one level donw. Note that section numbers are indexed by 1. Also, you can get to the base section (the root of the tree) via the `Experiment.base_section` attribute. For example:

    from experimentator import load_experiment
    exp = load_experiment('my_experiment.dat')

    for n in range(1,11):
        participant = exp.section(participant=n)
        # Add a block to the participant.
        exp.add_section(participant=n)
        # Move the last block of the participant to the beginning.
        blocks = participant.children
        participant.children = [blocks[-1], block[:-1]]
        # Remove all but the first 5 trials.
        participant.children[0].children[5:] = []

    exp.save()

This code creates a 'practice' block for each participant, with only 5 trials. Eventually, I hope to make this unnecessary by improving the experiment creation API. If you have any suggestions as to the API you would prefer for this sort of thing, let me know.


TODOs
------

* *More and better tests*
* Support for importing custom Ordering subclasses.
* Designs: fractional factorial, unbalanced designs
* Different settings by section (e.g., a block for practice trials)
* Design matrices (compatibility with [`patsy`](http://patsy.readthedocs.org/) and/or [`pyDOE`](http://pythonhosted.org//pyDOE/)?)
* A GUI!


License
-------

Copyright (c) 2013-2014 Henry S. Harrison under the MIT license. See ``LICENSE.txt``.
