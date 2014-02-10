import logging
import collections


class ExperimentSection():
    def __init__(self, context, tree):
        self.context = context
        self.tree = tree
        self.level = self.tree[0][0]
        self.is_bottom_level = len(self.tree) == 1

        self.children = collections.deque()
        self.has_started = False
        self.has_finished = False

        if self.is_bottom_level:
            self.next_level = None
            self.next_designs = None

        else:  # Not bottom level.
            self.next_level, self.next_designs = self.tree[1]

            # Create the section tree. Creating any section also creates the sections below it.
            for design in self.next_designs:
                self.append_design(design)

    def append_design(self, design, to_start=False):
        if to_start:
            for new_context in reversed(design.order(**self.context)):
                self.append_child(to_start=True, **new_context)

        else:
            for new_context in design.order(**self.context):
                self.append_child(**new_context)

    def append_child(self, to_start=False, **context):
        child_context = self.context.new_child()
        child_context.update(context)

        logging.debug('Generating {} with context {}.'.format(self.next_level, child_context))
        child = ExperimentSection(child_context, next(self.tree))
        if to_start:
            self.children.appendleft(child)
        else:
            self.children.append(child)

        self.number_children()

    def number_children(self):
        for i, child in enumerate(self.children):
            child.context.update({self.next_level: i + 1})

    def add_data(self, **kwargs):
        """
        Add data to all trials in a section. For example, add participant information to all entries under that
        participant.
        """
        self.context.update(kwargs)

    def generate_data(self):
        for child in self.children:
            if child.is_bottom_level:
                yield child.context
            else:
                yield from child.generate_data()

    def __len__(self):
        return len(self.children)

    def __getitem__(self, item):
        return self.children[item]
